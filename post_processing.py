#!/usr/bin/env python3

"""
Post processing utility
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile

from settings import (
    OUTPUT_DIR,
    PARSE_DIR,
    COMBO_DIR,
    ARCHIVE_DIR,
    IMPORT_DIR,
    OFFSITE_DEST
)
from scraper import SCRAPER_MAP


def parse_args():
    """ Parses cmdline arguments """

    parser = argparse.ArgumentParser(description="Post processing utility")
    parser.add_argument("-site", help="A site name", required=True)
    parser.add_argument("-template", help="Template name for this site", required=True)
    parser.add_argument("-date", help="A datestamp", required=True)
    parser.add_argument("-of", help="Output folder", default=OUTPUT_DIR)
    parser.add_argument("-pf", help="Parse folder", default=PARSE_DIR)
    parser.add_argument("-cf", help="Combo folder", default=COMBO_DIR)
    parser.add_argument("-af", help="Archive folder", default=ARCHIVE_DIR)
    parser.add_argument("-mf", help="Import folder", default=IMPORT_DIR)
    parser.add_argument(
        "--sync", help="Sync with cloud", action="store_true", default=False
    )

    args, _ = parser.parse_known_args()
    return args


def check_input_dirs(html_dir, parse_dir, combo_dir, archive_dir, import_dir):
    """ Checks input data """

    def is_dir_exists(path):
        return os.path.exists(path) and os.path.isdir(path)

    if not is_dir_exists(html_dir):
        print_erorr_message_and_raise_exception(
            "ERROR STAGE 0: Scraper output directory does not exist: %s" % html_dir
        )
    if not is_dir_exists(parse_dir):
        print_erorr_message_and_raise_exception(
            "ERROR STAGE 0: Parsing output directory does not exist: %s" % parse_dir
        )
    if not is_dir_exists(combo_dir):
        print("WARNING: JSON combo directory does not exist: %s" % combo_dir)
        os.makedirs(combo_dir)
    if not is_dir_exists(archive_dir):
        print("WARNING: Archive directory does not exist: %s" % archive_dir)
        os.makedirs(archive_dir)
    if not is_dir_exists(import_dir):
        warning_message = "Warning: Import directory does not exist: %s" % import_dir
        print(warning_message)
        os.makedirs(import_dir)


def make_tarfile(output_filename, source):
    """ Creates a .tar.gz archive """

    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source)

    if os.path.isdir(source):
        for f in os.listdir(source):
            print(os.path.join(source, f))
    else:
        print(source)


def exit_func(exit_code=2, exception=None):
    if not exception:
        sys.exit(exit_code)
    else:
        raise exception


def validate_output_json_file(combined_json_file):
    validate_output_file("output_json", combined_json_file)


def validate_json_archive_file(combined_json_archive):
    validate_output_file("json_archive", combined_json_archive)


def validate_output_file(file_label, output_file_name):
    if not os.path.exists(output_file_name):
        print_erorr_message_and_raise_exception(
            f"ERROR: cannot find the {file_label} file at ({output_file_name}). Aborting."
        )
    if os.path.getsize(output_file_name) == 0:
        print_erorr_message_and_raise_exception(
            f"ERROR:  The {file_label} file at ({output_file_name}) is empty. Aborting."
        )


def print_erorr_message_and_raise_exception(error_message):
    print(error_message)
    exit_func(2, RuntimeError(error_message))


def run(kwargs=None):
    """ Main program flow """

    if kwargs:
        args = None
        site = kwargs["site"]
        template = kwargs["template"]
        date = kwargs["date"]
        sync = kwargs.get("sync", False)
        output_folder = kwargs.get("of", OUTPUT_DIR)
        parse_folder = kwargs.get("pf", PARSE_DIR)
        combo_folder = kwargs.get("cf", COMBO_DIR)
        archive_folder = kwargs.get("af", ARCHIVE_DIR)
        import_folder = kwargs.get("mf", IMPORT_DIR)
    else:
        # parse cmdline arguments
        args = parse_args()
        site = args.site
        template = args.template
        date = args.date
        sync = args.sync
        output_folder = args.of
        parse_folder = args.pf
        combo_folder = args.cf
        archive_folder = args.af
        import_folder = args.mf

    scraper = SCRAPER_MAP.get(template)
    if not scraper:
        err_msg = "ERROR: Invalid site template"
        print(err_msg)
        exit_func(2, RuntimeError(err_msg))

    site_type = getattr(scraper, "site_type", None)
    if not site_type:
        err_msg = f"ERROR: {site} has no site_type set"
        print(err_msg)
        exit_func(2, RuntimeError(err_msg))

    # prepare paths
    if site_type in ("shadownet", "telegram"):
        html_dir = os.path.join(output_folder, site_type, site)
        parse_dir = os.path.join(parse_folder, site_type, site)
    else:
        html_dir = os.path.join(output_folder, site)
        parse_dir = os.path.join(parse_folder, site)

    archive_dir = os.path.join(archive_folder, site_type, "original")
    import_dir = os.path.join(import_folder, site_type)

    # check input dirs
    print("Checking paths...")
    check_input_dirs(
        html_dir=html_dir,
        parse_dir=parse_dir,
        combo_dir=combo_folder,
        archive_dir=archive_dir,
        import_dir=import_dir,
    )

    # check if the parse dir contain at least one file
    if not os.listdir(parse_dir):
        err_msg = f"{parse_dir} is Empty"
        print(err_msg)
        exit_func(0)

    ##############################################
    # merge parsed files
    ##############################################
    print("Combining JSON files...")
    combined_json_file = os.path.abspath(os.path.join(combo_folder, f"{site}-{date}.json"))
    
    # Pure Python replacement for: find . -name \*.json -exec cat {} + | jq -c . | sort -us -o combined_json_file
    import json
    all_objects = []
    decoder = json.JSONDecoder()
    
    def skip_whitespace(s, pos):
        while pos < len(s) and s[pos].isspace():
            pos += 1
        return pos
    
    for root, dirs, files in os.walk(parse_dir):
        for filename in files:
            if filename.endswith('.json'):
                filepath = os.path.join(root, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    pos = 0
                    while pos < len(content):
                        pos = skip_whitespace(content, pos)
                        if pos >= len(content):
                            break
                        obj, pos = decoder.raw_decode(content, idx=pos)
                        all_objects.append(obj)
    
    # Deduplicate by canonical JSON string representation
    seen = set()
    unique_objects = []
    for obj in all_objects:
        obj_str = json.dumps(obj, sort_keys=True, separators=(',', ':'))
        if obj_str not in seen:
            seen.add(obj_str)
            unique_objects.append(obj)
    
    # Sort by canonical JSON representation
    unique_objects.sort(key=lambda obj: json.dumps(obj, sort_keys=True, separators=(',', ':')))
    
    # Write combined file (each object as compact JSON line)
    with open(combined_json_file, 'w', encoding='utf-8') as f:
        for obj in unique_objects:
            f.write(json.dumps(obj, separators=(',', ':')) + '\n')
    
    # Validate output
    try:
        validate_output_json_file(combined_json_file)
    except Exception as err:
        exit_func(2, err)

    validate_output_json_file(combined_json_file)
    ##############################################
    # archive scraped HTML and combined JSON
    ##############################################
    print("Archiving HTML files...")
    html_archive = os.path.join(
        archive_folder, site_type, "original", f"{site}-html-{date}.tar.gz"
    )
    try:
        make_tarfile(html_archive, html_dir)
    except OSError as err:
        print("ERROR: Failed to create HTML archive: %s" % err)
        exit_func(2, err)

    print("Archiving the combined JSON file...")
    combined_json_archive = os.path.join(
        archive_folder, site_type, f"{site}-{date}.tar.gz"
    )
    try:
        make_tarfile(combined_json_archive, combined_json_file)
    except OSError as err:
        print("ERROR: Failed to create JSON archive: %s" % err)
        exit_func(2, err)

    validate_json_archive_file(combined_json_archive)

    ##############################################
    # move combined JSON to import dir
    ##############################################
    print("Moving the combined JSON file to import folder...")
    import_dir = os.path.join(import_folder, site_type)
    try:
        shutil.move(combined_json_file, import_dir)
    except OSError as err:
        print("ERROR: Failed to move JSON to import directory: %s" % err)
        exit_func(2, err)

    ##############################################
    # delete scraped HTML and parsed JSON files
    ##############################################
    print("Deleting source HTML and JSON files...")
    if not os.path.exists(html_archive):
        print_erorr_message_and_raise_exception(
            "ERROR: missing archive file %s" % html_archive
        )
    elif os.path.getsize(html_archive) == 0:
        print_erorr_message_and_raise_exception(
            "ERROR: empty archive file %s" % html_archive
        )
    else:
        shutil.rmtree(html_dir)
        shutil.rmtree(parse_dir)

    ##############################################
    # send archives offset
    ##############################################
    if sync:
        print("Running rclone tool...")
        try:
            result = subprocess.run(
                ["rclone", "copy", archive_folder, OFFSITE_DEST, "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            print(
                "ERROR: Failed to copy archive directory offset: retcode=%d, "
                "err=%s" % (err.returncode, err.stderr)
            )
            exit_func(2, err)
    print("Done")


if __name__ == "__main__":
    run()
