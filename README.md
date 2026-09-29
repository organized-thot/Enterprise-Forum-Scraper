# forumparser

`forumparser` is a Python-based framework designed for scraping, parsing, and processing structured data from various online sources, including web forums, darknet market sites, messaging platforms (such as Telegram), and paste bins.

It provides a modular pipeline to handle the entire lifecycle of forum intelligence collection: raw page/content scraping, HTML parsing into standardized JSON representations, deduplication and merging, tarball archiving, and cloud synchronization.

---

## Table of Contents

- [Features](#features)
- [System Architecture & Workflow](#system-architecture--workflow)
- [Directory Structure](#directory-structure)
- [Prerequisites & Installation](#prerequisites--installation)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
  - [Central Entry Point (`collector.py`)](#central-entry-point-collectorpy)
  - [Scraping](#scraping)
  - [Parsing](#parsing)
  - [Post-Processing](#post-processing)
  - [Automated Processing & Controller Service](#automated-processing--controller-service)
- [Adding New Scrapers & Parsers](#adding-new-scrapers--parsers)

---

## Features

- **Extensible Scraper & Parser Architecture**: Map-driven scrapers (`scraper/`) and parsers (`templates/`) support hundreds of forum templates and dark web sites.
- **Unified Command-Line Interface**: Run scraping, parsing, scanning, or post-processing tasks through `collector.py`.
- **Scheduled Automated Ingestion**: `scrapercontroller.py` and `scraperprocessor.py` integrate with the Data Viper API to periodically pull, process, and update target sites based on scheduled times.
- **Robust Pipeline Post-Processing**: Automated merging with `jq`, deduplication, tar.gz compression of HTML sources and combined JSONs, and optional offsite syncing via `rclone`.
- **Flexible Anti-Bot & Proxy Options**: Integration with proxy providers, captcha solvers (e.g. Anti-Captcha, Unicaps), cloudscraper, and headless browser automatons (Selenium).

---

## System Architecture & Workflow

The typical pipeline execution follows these four stages:

1. **Scraping Stage (`collector.py -scrape` / `run_scrapper.py`)**:
   - Invokes the appropriate site scraper from `scraper/`.
   - Downloads HTML pages, thread content, or user metadata into an output directory (e.g., `output/<site_name>`).
   - Tracks processed post/topic IDs in master list files to allow incremental rescanning.

2. **Parsing Stage (`collector.py -parse` / `forumparse.py`)**:
   - Invokes the parser template from `templates/`.
   - Reads raw files from the scraper output directory and extracts structured fields (e.g., author, timestamp, post content, topic titles).
   - Outputs extracted data as formatted JSON files into a parse directory (e.g., `parse/<site_name>`).

3. **Post-Processing Stage (`collector.py -post` / `post_processing.py`)**:
   - Concatenates and formats all JSON files into a single combined JSON dataset (`combo/<site>-<date>.json`).
   - Archives raw HTML files and the combined JSON into `.tar.gz` archives (`archive/`).
   - Moves the final combined JSON file to an import folder (`import/`) for downstream ingestion.
   - Cleans up original scraped HTML and parsed intermediate JSON files.
   - Optionally syncs archives offsite using `rclone`.

4. **Automated Daemon / Orchestration (`scrapercontroller.py` & `scraperprocessor.py`)**:
   - `scrapercontroller.py` periodically fetches active scrapers and schedule metadata from the Data Viper API (`/api/scraper`).
   - Spawns subprocesses running `scraperprocessor.py` for scheduled targets.

---

## Directory Structure

```text
.
├── collector.py           # Main CLI tool and central entrypoint
├── cli_parser.py          # Argument parsing helper for CLI options
├── run_scrapper.py        # Driver module for launching scraper instances
├── forumparse.py          # Driver module for launching parser instances
├── post_processing.py     # Data merging, JQ formatting, archiving, and cloud sync utility
├── scrapercontroller.py   # Daemon scheduler for automated scraper runs
├── scraperprocessor.py    # Processor orchestrating scraping, parsing, and post-processing
├── config.py              # Configuration arguments definition
├── settings.py            # Environment settings and paths configuration
├── base_logger.py         # Logging helper setup
├── utils.py               # Shared utility functions
├── scraper/               # Individual scraper scripts for each forum/target site
├── templates/             # Individual parser templates for each site structure
├── dbtools/               # Database utilities (e.g., gathering tools)
├── helpers/               # Helper routines (e.g. error messages, stats tracking)
├── noscrape/              # Database scanning and port check utilities
├── extensions/            # Browser extensions for Selenium/automation
├── tools/                 # Miscellaneous scripts (post-processing helpers, shell scripts)
└── requirements.txt       # Python package dependencies
```

---

## Prerequisites & Installation

### Requirements

- **Python**: 3.8+ (3.12 compatible)
- **System Tools**:
  - `jq`: Required for JSON processing during post-processing.
  - `tar`: Required for archiving HTML and JSON outputs.
  - `rclone` *(Optional)*: Required if cloud sync functionality is enabled.

### Installation

1. Clone the repository and navigate into the project directory:
   ```bash
   git clone <repository_url>
   cd forumparser
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration

Configuration variables can be customized using environment variables or a `.env` file in the root directory (refer to `env.example` or `env-sample`).

### Key Settings (`settings.py` / `.env`)

| Variable | Default Value | Description |
|---|---|---|
| `DV_BASE_URL` | `https://api.dataviper.io` | API base URL for Data Viper orchestration service |
| `API_TOKEN` | *None* | API key for authenticating with the Data Viper API |
| `OUTPUT_DIR` | `output` | Directory where raw scraped HTML/content is saved |
| `PARSE_DIR` | `parse` | Directory where parsed JSON files are written |
| `MASTER_LIST_DIR` | `master-list` | Directory for tracking scraped topic/post IDs |
| `COMBO_DIR` | `combo` | Directory for merged JSON files before archiving |
| `AVATAR_DIR` | `avartar` | Directory where user avatar images are stored |
| `ARCHIVE_DIR` | `archive` | Directory where final `.tar.gz` archives are created |
| `IMPORT_DIR` | `import` | Target directory for final combined JSON datasets |
| `OFFSITE_DEST` | `b2:/ViperStorage/forums/2020/file` | Cloud storage destination for `rclone` sync |
| `LOG_DIR` | `log` | Directory for log outputs |
| `PYTHON_BIN` | `python` | Python executable binary path for subprocesses |

---

## Usage Guide

### Central Entry Point (`collector.py`)

`collector.py` serves as the primary CLI interface.

```bash
python collector.py [ACTION] [OPTIONS]
```

Primary Action Flags:
- `-scrape` / `--scrape`: Execute a scraping task.
- `-parse` / `--parse`: Execute a parsing task.
- `-scan` / `--scan`: Run DB/IP scanning via `NoScrape`.
- `-post` / `--post`: Run post-processing.

---

### Scraping

To view available scrapers:
```bash
python collector.py -scrape -l
```

To scrape a forum template:
```bash
python collector.py -scrape -t <template_name> -o <output_directory>
```

#### Optional Scraping Flags:
- `-s`, `--start_date YYYY-MM-DD`: Scrape threads/posts newer than the specified date.
- `-rs`, `--rescan`: Perform a rescan run.
- `--users`: Scrape forum user profiles.
- `--no_proxy`: Disable proxy usage.
- `--proxy_countries`: Comma-delimited list of target proxy country codes (e.g. `us,gb`).
- `--use_vip`: Use VIP proxy pools.

#### Example:
```bash
python collector.py -scrape -t breachforums -o output/breachforums -s 2023-01-01
```

---

### Parsing

To view available parser templates:
```bash
python collector.py -parse -l
```

To parse scraped raw HTML files into JSON format:
```bash
python collector.py -parse -t <template_name> -i <input_path> -o <output_path>
```

#### Optional Parsing Flags:
- `-s`, `--start_date YYYY-MM-DD`: Parse items newer than the specified date.
- `-c`, `--checkonly`: Limit files missing author or date information.
- `-site`, `--sitename`: Specify custom site name for the dataset.

#### Example:
```bash
python collector.py -parse -t breachforums -i output/breachforums -o parse/breachforums
```

---

### Post-Processing

Post-processing merges parsed JSON files, validates output, creates `.tar.gz` archives, and moves datasets to the import directory.

Run standalone via `post_processing.py`:
```bash
python post_processing.py -site <sitename> -template <template_name> -date <YYYY_MM_DD> [--sync]
```

Or via `collector.py`:
```bash
python collector.py -post -site <sitename> -template <template_name> -date <YYYY_MM_DD>
```

---

### Automated Processing & Controller Service

For automated deployments integrated with the Data Viper management API:

1. **Run a single scraper job by ID**:
   ```bash
   python scraperprocessor.py -s <scraper_id>
   ```
   This will retrieve scraper configuration, run the scraper, execute the matching parser, and run post-processing automatically.

2. **Run the continuous scheduler service**:
   ```bash
   python scrapercontroller.py
   ```
   This process runs indefinitely, fetching scheduled active scrapers from the API and spawning background processes when jobs are due.

---

## Adding New Scrapers & Parsers

1. **Create Scraper**:
   - Add a new module under `scraper/` (e.g., `scraper/mysite.py`).
   - Inherit from `BaseScrapper` (defined in `scraper/base_scrapper.py`).
   - Implement scraping logic and register the class in `scraper/__init__.py` under `SCRAPER_MAP`.

2. **Create Parser Template**:
   - Add a new template module under `templates/` (e.g., `templates/mysite_template.py`).
   - Inherit from `BaseTemplate` (defined in `templates/base_template.py`).
   - Implement parsing logic for extracting forum threads, posts, authors, and timestamps.
   - Register the class in `templates/__init__.py` under `PARSER_MAP`.
