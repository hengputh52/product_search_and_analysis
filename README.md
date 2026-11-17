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

## Processing and Indexing

``` To test query, go to run_search.py and enter query in 
QUERIES = [
    "iphone x",
    # '"power bank" NOT case',
    # "(earbuds OR headphones) AND noise",
] ```.
After that run python .\run_search.py. you may see result as below

For example: 
``` QUERIES = ["iphone x"] ``` and see output like this
``` Query: iphone x  ->  25 results
  amazon:B00840RRPE            Bose QuietComfort 3 Acoustic Noise Cancelling Headphones, Black
  amazon:B0855NZDMP            iLight Mini Smartphone XS, World's Smallest 10+ Android Phone 4G LTE,
  amazon:B0BF45JLWL            Wireless Earbuds, Bluetooth 5.1 Earphones for Sports, with Wireless Ch
  amazon:B0BVYFCKWW            2 Pack Light^ing Wired Earbuds Headphones Earphone Built-in Microphone
  amazon:B0C65FBHHL            Apple Headphones Wired iPhone Earbuds with Lightning Connector [Apple
  amazon:B0C66M4DYY            2 Pack iPhone Earbuds [Apple MFi Certified] Wired in-Ear Stereo Noise
  amazon:B0C69JB9SM            2 Packs-Apple Earbuds for iPhone Headphones Wired Earphones [Apple MFi
  amazon_web:B0CJBQBB7F        charmast Portable Charger Built-in Cables, 20000mAh Power Bank 6-Outpu
  angkor_meas:14496            Apple Adaptor 5W
  angkor_meas:14542            Leather Case iPhone X (Original: OFF 50%)
  ... and 15 more
```
  
See [data/README.md](data/README.md) for the export's column definitions and [BUILD_GUIDE.md](BUILD_GUIDE.md) for a step-by-step build walkthrough.

## Data & license notes

- Amazon Reviews 2023 is licensed for **research use only**. Keep this repo private and don't redistribute the data.
- The notebookcheck crawler waits 2 seconds between requests and identifies itself with a research user agent. Downloaded pages are cached in `data/raw/`, which is git-ignored.
