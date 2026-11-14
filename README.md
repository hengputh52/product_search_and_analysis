# ShopBot — Product Search & Analysis

Collects consumer-electronics products, cleans them, and stores them in a PostgreSQL (Neon) database. The data is then exported to CSV and JSONL files so collaborators can use it without database access.

**Sources**

- **Amazon Reviews 2023** (McAuley Lab, via Hugging Face): laptops, smartphones, tablets, headphones, TVs
- **notebookcheck.net** (scraped review pages): the categories above plus smartwatches, wearables, audio, mini PCs, desktops, monitors, cameras, gaming handhelds and e-readers

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash (macOS/Linux: .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env               # then fill in DATABASE_URL
```

| `.env` variable | Purpose |
|---|---|
| `DATABASE_URL` | Neon / PostgreSQL connection string |
| `PRODUCTS_PER_CATEGORY` | Max products to collect per category (default `150`) |
| `LOG_LEVEL` | Logging level (default `INFO`) |

## Usage

```bash
# Collect: download → clean → save to the database
python -m product_search_analysis.collect --source amazon
python -m product_search_analysis.collect --source notebookcheck --per-category 50
python -m product_search_analysis.collect --source amazon_web --per-category 20   # live amazon.com scraping
python -m product_search_analysis.collect --source alibaba --per-category 20      # alibaba.com (needs Playwright)
python -m product_search_analysis.collect --source ptc_computer --per-category 500 # ptc-computer.com.kh
python -m product_search_analysis.collect --source angkor_meas --per-category 500  # angkormeas.com
python -m product_search_analysis.collect --source sunsimexco --per-category 500   # sunsimexco.com.kh
python -m product_search_analysis.collect --dry-run          # download + clean only, no DB writes

# Export the database to data/products_<date_time>.csv and .jsonl (new files every run)
python -m product_search_analysis.export
python -m product_search_analysis.export --source amazon_web # only one source

# Recalculate USD prices in the database after changing a rate in config.py (USD_PER_EUR, KHR_PER_USD)
python -m product_search_analysis.convert_prices --dry-run   # drop --dry-run to apply

# Run the tests
pytest
```

The `products` table is created automatically from [db/schema.sql](db/schema.sql) on the first collection run.

## Project layout

```
product_search_analysis/
├── config.py          settings, categories, source URLs
├── collect.py         pipeline entry point (fetch → clean → save)
├── cleaning.py        text normalization, validation, de-duplication
├── db.py              PostgreSQL connection and inserts
├── export.py          database → timestamped CSV/JSONL in data/
└── scraping/
    ├── amazon/        Amazon Reviews 2023 reader (amazon.py) + amazon.com scraper (amazon_scraping.py)
    └── notebookcheck/ crawler (polite, cached) + HTML parser
db/schema.sql          products table definition
data/                  exported datasets (see data/README.md)
test/                  pytest tests for cleaning and the notebookcheck parser
```

See [data/README.md](data/README.md) for the export's column definitions and [BUILD_GUIDE.md](BUILD_GUIDE.md) for a step-by-step build walkthrough.

## Data & license notes

- Amazon Reviews 2023 is licensed for **research use only**. Keep this repo private and don't redistribute the data.
- The notebookcheck crawler waits 2 seconds between requests and identifies itself with a research user agent. Downloaded pages are cached in `data/raw/`, which is git-ignored.
