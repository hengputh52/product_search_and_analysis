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
├── search/            tokenizer, inverted index, Boolean queries
├── ranking/           TF-IDF, BM25, dense, hybrid ranking + benchmark
└── scraping/
    ├── amazon/        Amazon Reviews 2023 reader (amazon.py) + amazon.com scraper (amazon_scraping.py)
    └── notebookcheck/ crawler (polite, cached) + HTML parser
db/schema.sql          products table definition
data/                  exported datasets (see data/README.md)
test/                  pytest tests (cleaning, scrapers, search, ranking)
run_search.py          try Boolean search (edit the settings, then run it)
run_ranking.py         try ranked retrieval: tfidf, bm25, dense, hybrid
```

## Search and ranking

Searching works on an index built from the database. Build it once, and again after collecting new products:

```bash
python -m product_search_analysis.search.index      # -> data/index/inverted_index.pkl (git-ignored)
```

### Boolean search: `run_search.py`

Exact matching with `AND`, `OR`, `NOT`, `"exact phrase"` and `( )`, e.g. `(speaker OR headphones) AND bluetooth NOT sony`.
Results are not ranked; they come in product-id order. Open [run_search.py](run_search.py), edit the settings at the top
and run it (VS Code ▶ or `python run_search.py`):

```python
QUERIES = ["bluetooth speaker", '"power bank" NOT case']
MAX_RESULTS = 10
REBUILD_INDEX = False   # True = rebuild the index from the database first
```

### Ranked retrieval: `run_ranking.py`

Results come best first, with a score. Queries are plain text. Open [run_ranking.py](run_ranking.py), edit the settings
and run it (VS Code ▶ or `python run_ranking.py`):

```python
QUERIES = ["bluetooth speaker", "wireless earbuds for running"]
METHOD = "bm25"         # "tfidf" | "bm25" | "dense" | "hybrid" | "compare"
MAX_RESULTS = 10
REBUILD_INDEX = False
```

| `METHOD` | What it does |
|---|---|
| `tfidf`, `bm25` | Ranked by matching words. |
| `dense`, `hybrid` | Ranked by meaning (sentence embeddings), so questions like "something to listen to music while running" work. `hybrid` fuses BM25 and dense. Needs the one-time setup below. |
| `compare` | Runs every available method side by side for each query. |

Example (`METHOD = "bm25"`):

```
Query: bluetooth speaker
  bm25:
    1.   7.5970  [speaker] ANCOON Speakers Bluetooth Wireless: 80W(Peak) Loud Speaker w  (no price)
    2.   7.3601  [computer-accessories] Speaker Razer Leviathan Mini Bluetooth Speaker - NASA Packag  ($44.00)
```

### Dense and hybrid setup (once)

```bash
pip install sentence-transformers                   # large: installs PyTorch
python -m product_search_analysis.ranking.dense     # -> data/index/embeddings.npz; first run downloads the model
```

Rebuild the embeddings whenever you rebuild the index, so both cover the same products.

### Command line and benchmark

```bash
# one query, one method
python -m product_search_analysis.ranking.retrieve "bluetooth speaker" --method bm25 --top-k 5

# score every method on the 28 test queries in product_search_analysis/ranking/benchmark_queries.json
python -m product_search_analysis.ranking.benchmark                      # all methods (needs dense)
python -m product_search_analysis.ranking.benchmark --methods tfidf bm25
```

The benchmark prints P@5, P@10, MRR and nDCG@10 per method (0 to 1, higher is better) and saves the report to
`data/benchmark/benchmark_<date_time>.md` and `.json`. Relevance is judged automatically from each product's
category (plus required title words for some queries), so use the numbers to compare methods, not as exact quality.
To add a test query, add an entry to `benchmark_queries.json`.

See [data/README.md](data/README.md) for the export's column definitions and [BUILD_GUIDE.md](BUILD_GUIDE.md) for a step-by-step build walkthrough.

## Data & license notes

- Amazon Reviews 2023 is licensed for **research use only**. Keep this repo private and don't redistribute the data.
- The notebookcheck crawler waits 2 seconds between requests and identifies itself with a research user agent. Downloaded pages are cached in `data/raw/`, which is git-ignored.
