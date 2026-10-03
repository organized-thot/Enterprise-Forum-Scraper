import logging
import os
from scraper import SCRAPER_MAP
from settings import MASTER_LIST_DIR
from helpers.stats import get_error, get_warnings

UPDATE_DB_PATH = '/Users/PathakUmesh/forums.db'
LOGGER = logging.getLogger(__name__)


class Scraper:
    def __init__(self, kwargs):
        self.counter = 1
        self.kwargs = kwargs

    def is_blank(self):
        values = [
            value for value in self.kwargs.values()
            if value
        ]
        return len(values) == 0

    def print_list_template(self):
        print('Following scrapers are available')
        for index, scraper in enumerate(SCRAPER_MAP.keys(), 1):
            print(f'{index}. {scraper}')

    def do_scrape(self):
        if self.is_blank():
            print(
                "Require parameter:\n"
                "- -t/--template: template name\n"
                "- -o/--output: output folder"
            )
            return
        if self.kwargs.get('list'):
            self.print_list_template()
            return

        template = self.kwargs.get('template')

        help_message = """
            Usage: collector.py -scrape [-t TEMPLATE] [-o OUTPUT] [-s START_DATE]\n
            Arguments:
            -t | --template TEMPLATE:     Template forum to scrape
            -o | --output OUTPUT:         Output folder path

            Optional:
            -s | --start_date START_DATE: Scrape threads that are newer than supplied date
            -l | --list:                  List available scrapers (tempalte namess)
            --get_users                   Scrape forum users
            --no_proxy                    Disable proxies
            --proxy_countries             Comma-delimited list of proxy countries
            --use_vip                     Use VIP proxies

            """

        if not template:
            print(help_message)
            return

        scraper = SCRAPER_MAP.get(template.lower())
        if not scraper:
            print('Not found template!')
            self.print_list_template()
            return

        output_folder = self.kwargs.get('output')
        if not output_folder and template not in ('shadownet', 'telegram'):
            print(help_message)
            return

        master_list_folder = self.kwargs.get('master_list_path',
                                             f'{MASTER_LIST_DIR}/{template}/')

        # ------------make folder if not exist -----------------
        if template not in ('shadownet', 'telegram'):
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            if not os.path.exists(master_list_folder):
                os.makedirs(master_list_folder)

        stats = None
        scraper_obj = scraper(self.kwargs)
        if self.kwargs.get('rescan'):
            scraper_obj.do_rescan()
        # elif self.kwargs.get("start_date"):
        #     try:
        #         scraper_obj.do_scrape_from_date()
        #     except Exception as err:
        #         print(
        #             "Error running do scrape from date: %s" % err
        #         )
        #         stats = scraper_obj.do_scrape()
        else:
            if template != 'shadownet':
                stats = scraper_obj.do_scrape()
            else:
                stats = scraper_obj.start()

            if stats:
                err = get_error(stats)
                warnings = get_warnings(stats)

                if err:
                    LOGGER.error(f'{err[0]}: {err[1]}')
                    stats['result/error'] = err
                elif warnings:
                    stats['result/warnings'] = warnings
                    for warn in warnings:
                        LOGGER.warning(f'{warn[0]}: {warn[1]}')
                else:
                    LOGGER.info('Finished successfully')

        return stats


import sys
from cli_parser import CliParser

def main():
    cli = CliParser(arguments=[
        {"args": ["--template"], "kwargs": {"help": "template name"}},
        {"args": ["--list"], "kwargs": {"action": "store_true", "help": "list scrapers"}},
        {"args": ["--output"], "kwargs": {"help": "output path"}},
        {"args": ["--rescan"], "kwargs": {"action": "store_true", "help": "rescan"}}
    ])
    kwargs = cli.get_args()
    Scraper(kwargs).do_scrape()


if __name__ == '__main__':
    main()
