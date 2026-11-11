# Build ShopBot Data Collection — Step by Step

You will build a small Python program that:

1. **downloads** consumer-electronics products from the free *Amazon Reviews 2023* dataset,
2. **cleans** them (removes HTML, extra spaces, bad rows, duplicates),
3. **saves** them into your PostgreSQL database on Neon.

The whole project is **7 small files**. Build them in order. Every step ends
with a **✅ Check** command. Don't go to the next step until the check passes.

```
product_search_and_analysis/
├── .env                    ← your secrets (already exists)
├── requirements.txt        ← Step 1
├── db/schema.sql           ← Step 5
├── data/                   ← already exists — Step 8 writes the exported files here
│   ├── README.md           ←   explains the files for collaborators
│   ├── products.csv        ←   Step 8 (generated)
│   └── products.jsonl      ←   Step 8 (generated)
├── product_search_analysis/ ← the Python package
│   ├── __init__.py         ← Step 2 (empty file)
│   ├── config.py           ← Step 2  settings
│   ├── cleaning.py         ← Step 3  clean + validate + dedupe
│   ├── scraping/
│   │   ├── __init__.py     ← Step 4 (empty file)
│   │   └── amazon.py       ← Step 4  download products
│   ├── db.py               ← Step 5  save to PostgreSQL
│   ├── collect.py          ← Step 6  run everything
│   └── export.py           ← Step 8  database → data/ files
└── test/test_cleaning.py   ← Step 3
```

How the pieces connect:

```
collect.py  ──1──►  scraping/amazon.py   (download raw products)
            ──2──►  cleaning.py         (clean, drop bad rows, remove duplicates)
            ──3──►  db.py               (save to Neon PostgreSQL)

export.py   ──────►  db.py ──► data/products.csv + data/products.jsonl   (for collaborators)

  every file reads settings (paths, categories, DATABASE_URL) from config.py
```

> Run every command from the project folder, in the VS Code terminal (Git Bash).

---

## Step 1 — Python environment

**Goal:** an isolated Python with the 4 libraries we need.

Create **`requirements.txt`**:

```text
# requirements.txt
httpx            # download data over HTTP
psycopg[binary]  # talk to PostgreSQL
python-dotenv    # read the .env file
pytest           # run tests
```

Then in the terminal:

```bash
python -m venv .venv                 # skip if the .venv folder already exists
source .venv/Scripts/activate        # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Your `.env` should contain at least:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST.neon.tech/neondb?sslmode=require
PRODUCTS_PER_CATEGORY=150
LOG_LEVEL=INFO
```

**✅ Check**

```bash
python -c "import httpx, psycopg, dotenv, pytest; print('ok')"
```

Expected: `ok`

---

## Step 2 — Settings (`product_search_analysis/config.py`)

**Goal:** one place for every setting, so no other file has hard-coded values.

Create an **empty** file `product_search_analysis/__init__.py` (this makes `product_search_analysis` a Python package).

Create **`product_search_analysis/config.py`**:

```python
# product_search_analysis/config.py
"""All settings in one place. Secrets come from .env, everything else is a constant."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # the project folder
load_dotenv(ROOT / ".env")

# --- from .env ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
PRODUCTS_PER_CATEGORY = int(os.getenv("PRODUCTS_PER_CATEGORY", "150"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- constants ---
CATEGORIES = ["laptop", "smartphone", "headphones", "tv", "tablet"]
MIN_DESCRIPTION_LENGTH = 20

# --- folders and files ---
SCHEMA_FILE = ROOT / "db" / "schema.sql"  # table definition (Step 5)
DATA_DIR = ROOT / "data"                  # exported products for collaborators (Step 8)

# --- Amazon Reviews 2023 dataset (Hugging Face, free, no key) ---
AMAZON_BASE_URL = (
    "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023"
    "/resolve/main/raw/meta_categories"
)
# our category -> (file to read, Amazon category path it must start with)
AMAZON_CATEGORY_RULES = {
    "laptop": ("meta_Electronics.jsonl", "Electronics > Computers & Accessories > Computers & Tablets > Laptops"),
    "tablet": ("meta_Electronics.jsonl", "Electronics > Computers & Accessories > Computers & Tablets > Tablets"),
    "tv": ("meta_Electronics.jsonl", "Electronics > Television & Video > Televisions"),
    "headphones": ("meta_Electronics.jsonl", "Electronics > Headphones, Earbuds & Accessories > Headphones & Earbuds"),
    "smartphone": ("meta_Cell_Phones_and_Accessories.jsonl", "Cell Phones & Accessories > Cell Phones"),
}
# safety stop: never read more than this many lines of one file
MAX_LINES_PER_FILE = 2_000_000
```

**✅ Check**

```bash
python -c "from product_search_analysis import config; print(config.CATEGORIES, bool(config.DATABASE_URL))"
```

Expected: `['laptop', 'smartphone', 'headphones', 'tv', 'tablet'] True`
(`False` means `DATABASE_URL` is missing from `.env` — fine for now, needed in Step 5.)

---

## Step 3 — Cleaning (`product_search_analysis/cleaning.py`) + tests

**Goal:** turn messy text into clean text, drop bad products, remove duplicates.
These are *pure functions* (no internet, no database), so they're easy to test.

Create **`product_search_analysis/cleaning.py`**:

```python
# product_search_analysis/cleaning.py
"""Pure functions: clean text, clean a product, validate, deduplicate."""
import html
import re

from product_search_analysis.config import CATEGORIES, MIN_DESCRIPTION_LENGTH

TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")  # an HTML tag like <b> or </p>
SPACES_RE = re.compile(r"\s+")             # any run of spaces/tabs/newlines


def normalize_text(value) -> str:
    """'<p>Hello&amp;  world</p>' -> 'Hello& world'"""
    if value is None:
        return ""
    text = TAG_RE.sub(" ", str(value))      # remove HTML tags
    text = html.unescape(text)              # &amp; -> &, &nbsp; -> space
    return SPACES_RE.sub(" ", text).strip() # collapse spaces


def parse_price(value):
    """9.99 -> 9.99, '$1,299.00' -> 1299.0, None/'n/a' -> None"""
    if value is None:
        return None
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def clean_product(raw: dict) -> dict:
    """Apply normalize_text to every text field."""
    specs = {}
    for key, value in (raw.get("specs") or {}).items():
        if isinstance(value, (str, int, float)) and normalize_text(value):
            specs[normalize_text(key)] = normalize_text(value)

    features = [normalize_text(f) for f in raw.get("features") or []]

    return {
        "product_id": raw["product_id"],
        "title": normalize_text(raw.get("title")),
        "description": normalize_text(raw.get("description")),
        "brand": normalize_text(raw.get("brand")),
        "category": normalize_text(raw.get("category")).lower(),
        "price": parse_price(raw.get("price")),
        "specs": specs,
        "features": [f for f in features if f],
        "image_url": raw.get("image_url") or "",
        "source_url": raw.get("source_url") or "",
        "rating": raw.get("rating"),
        "source": raw["source"],
    }


def is_valid(product: dict) -> bool:
    """Keep only products with a title, a real description and a known category."""
    return (
        bool(product["title"])
        and len(product["description"]) >= MIN_DESCRIPTION_LENGTH
        and product["category"] in CATEGORIES
    )


def deduplicate(products: list[dict]) -> list[dict]:
    """Keep the first product for each title (case-insensitive)."""
    seen = set()
    unique = []
    for p in products:
        key = p["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique
```

Create **`test/test_cleaning.py`**:

```python
# test/test_cleaning.py
from product_search_analysis.cleaning import deduplicate, normalize_text, parse_price


def test_normalize_text_removes_html_and_spaces():
    assert normalize_text("<p>Noise&nbsp;Cancelling\n  <b>Headphones</b></p>") == "Noise Cancelling Headphones"


def test_normalize_text_handles_none():
    assert normalize_text(None) == ""


def test_parse_price():
    assert parse_price("$1,299.00") == 1299.0
    assert parse_price("n/a") is None


def test_deduplicate_ignores_case():
    products = [{"title": "Pixel 9"}, {"title": "PIXEL 9"}, {"title": "Galaxy S25"}]
    assert [p["title"] for p in deduplicate(products)] == ["Pixel 9", "Galaxy S25"]
```

**✅ Check**

```bash
python -m pytest -q
```

Expected: `4 passed`

---

## Step 4 — Download products (`product_search_analysis/scraping/amazon.py`)

**Goal:** read the dataset and return products in *our* format.

The dataset files are huge (5 GB), so we **stream** them line by line and
**stop early** once every category has enough products. Each line is one
product as JSON, for example:

```text
{"title": "...", "price": 9.99, "average_rating": 4.2, "features": [...],
 "description": [...], "categories": ["Electronics", "Headphones, Earbuds & Accessories", ...],
 "details": {"Brand": "...", ...}, "images": [{"hi_res": "https://..."}], "parent_asin": "B07C4YHF4L", ...}
```

Create an **empty** file `product_search_analysis/scraping/__init__.py`.

Create **`product_search_analysis/scraping/amazon.py`**:

```python
# product_search_analysis/scraping/amazon.py
"""Source: Amazon Reviews 2023 (Hugging Face). Streams JSON lines, no full download."""
import json
import logging

import httpx

from product_search_analysis.config import AMAZON_BASE_URL, AMAZON_CATEGORY_RULES, MAX_LINES_PER_FILE

log = logging.getLogger(__name__)


def stream_records(filename: str):
    """Yield one product (dict) per line of a remote .jsonl file."""
    url = f"{AMAZON_BASE_URL}/{filename}"
    with httpx.stream("GET", url, follow_redirects=True, timeout=60) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.strip():
                yield json.loads(line)


def find_category(record: dict, rules: dict) -> str | None:
    """Return our category if the record's Amazon category path matches a rule."""
    path = " > ".join(record.get("categories") or [])
    for category, prefix in rules.items():
        if path.startswith(prefix):
            return category
    return None


def to_product(record: dict, category: str) -> dict:
    """Convert one Amazon record into our product format (not cleaned yet)."""
    images = record.get("images") or [{}]
    details = record.get("details") or {}
    description = " ".join(record.get("description") or [])
    features = record.get("features") or []
    return {
        "product_id": f"amazon:{record['parent_asin']}",
        "title": record.get("title"),
        "description": description or ". ".join(features),
        "brand": details.get("Brand") or details.get("Manufacturer") or record.get("store"),
        "category": category,
        "price": record.get("price"),
        "specs": details,
        "features": features,
        "image_url": images[0].get("hi_res") or images[0].get("large"),
        "source_url": f"https://www.amazon.com/dp/{record['parent_asin']}",
        "rating": record.get("average_rating"),
        "source": "amazon",
    }


def fetch_products(per_category: int) -> list[dict]:
    """Return up to `per_category` priced products for each of our categories."""
    # group the rules by file, so each file is streamed only once
    files: dict[str, dict[str, str]] = {}
    for category, (filename, prefix) in AMAZON_CATEGORY_RULES.items():
        files.setdefault(filename, {})[category] = prefix

    products = []
    for filename, rules in files.items():
        counts = {category: 0 for category in rules}
        log.info("Reading %s for %s", filename, list(rules))

        for line_number, record in enumerate(stream_records(filename), start=1):
            category = find_category(record, rules)
            if category and record.get("price") and counts[category] < per_category:
                products.append(to_product(record, category))
                counts[category] += 1

            if line_number % 100_000 == 0:
                log.info("  %s lines read, found so far: %s", f"{line_number:,}", counts)
            if all(n >= per_category for n in counts.values()) or line_number >= MAX_LINES_PER_FILE:
                break

        log.info("Done with %s: %s", filename, counts)
    return products
```

**✅ Check** (downloads a little data — takes ~10–60 s):

```bash
python -c "from product_search_analysis.scraping import amazon; ps = amazon.fetch_products(2); print(len(ps)); print(ps[0]['category'], '|', ps[0]['title'][:60], '|', ps[0]['price'])"
```

Expected: `10` (2 × 5 categories), then one product line.

---

## Step 5 — Database (`db/schema.sql` + `product_search_analysis/db.py`)

**Goal:** create the `products` table and save products into it.

Create **`db/schema.sql`**:

```sql
-- db/schema.sql
CREATE TABLE IF NOT EXISTS products (
  product_id    TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  description   TEXT NOT NULL,
  brand         TEXT,
  category      TEXT NOT NULL,
  price         NUMERIC,
  specs         JSONB  DEFAULT '{}',
  features      TEXT[] DEFAULT '{}',
  image_url     TEXT,
  source_url    TEXT,
  rating        NUMERIC,
  source        TEXT NOT NULL,
  collected_at  TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
CREATE INDEX IF NOT EXISTS idx_products_brand    ON products (brand);
```

Create **`product_search_analysis/db.py`**:

```python
# product_search_analysis/db.py
"""Everything that talks to PostgreSQL."""
import psycopg
from psycopg.types.json import Jsonb

from product_search_analysis.config import DATABASE_URL, SCHEMA_FILE

INSERT_SQL = """
INSERT INTO products (product_id, title, description, brand, category, price,
                      specs, features, image_url, source_url, rating, source)
VALUES (%(product_id)s, %(title)s, %(description)s, %(brand)s, %(category)s, %(price)s,
        %(specs)s, %(features)s, %(image_url)s, %(source_url)s, %(rating)s, %(source)s)
ON CONFLICT (product_id) DO UPDATE SET
  title = EXCLUDED.title, description = EXCLUDED.description, brand = EXCLUDED.brand,
  category = EXCLUDED.category, price = EXCLUDED.price, specs = EXCLUDED.specs,
  features = EXCLUDED.features, image_url = EXCLUDED.image_url,
  source_url = EXCLUDED.source_url, rating = EXCLUDED.rating, collected_at = now()
"""


def connect():
    """Open a connection. Use it with `with connect() as conn:` (auto commit + close)."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing in .env")
    return psycopg.connect(DATABASE_URL)


def create_tables(conn) -> None:
    """Run db/schema.sql (safe to run many times)."""
    conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


def save_products(conn, products: list[dict]) -> int:
    """Insert products; existing product_ids are updated instead of duplicated."""
    rows = [{**p, "specs": Jsonb(p["specs"])} for p in products]
    with conn.cursor() as cur:
        cur.executemany(INSERT_SQL, rows)
    return len(rows)


def count_products(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
```

**✅ Check** (needs `DATABASE_URL` in `.env`):

```bash
python -c "from product_search_analysis import db; conn = db.connect(); db.create_tables(conn); conn.commit(); print('rows:', db.count_products(conn)); conn.close()"
```

Expected: `rows: 0` (or a number, if you've already saved products).

---

## Step 6 — Run everything (`product_search_analysis/collect.py`)

**Goal:** one command that does download → clean → save and prints a summary.

Create **`product_search_analysis/collect.py`**:

```python
# product_search_analysis/collect.py
"""Command line entry point:  python -m product_search_analysis.collect [--per-category N] [--dry-run]"""
import argparse
import json
import logging

from product_search_analysis import config, db
from product_search_analysis.cleaning import clean_product, deduplicate, is_valid
from product_search_analysis.scraping import amazon


def run(per_category: int, dry_run: bool) -> dict:
    raw = amazon.fetch_products(per_category)                 # 1. download
    cleaned = [clean_product(r) for r in raw]                 # 2. clean
    valid = [p for p in cleaned if is_valid(p)]
    unique = deduplicate(valid)

    summary = {
        "fetched": len(raw),
        "invalid": len(cleaned) - len(valid),
        "duplicates": len(valid) - len(unique),
        "kept": len(unique),
        "inserted": 0,
    }
    if not dry_run:                                           # 3. save
        with db.connect() as conn:
            db.create_tables(conn)
            summary["inserted"] = db.save_products(conn, unique)
            summary["total_in_db"] = db.count_products(conn)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect products into PostgreSQL.")
    parser.add_argument("--per-category", type=int, default=config.PRODUCTS_PER_CATEGORY)
    parser.add_argument("--dry-run", action="store_true", help="download + clean only, don't save")
    args = parser.parse_args()

    logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # hide one log line per HTTP request

    print(json.dumps(run(args.per_category, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
```

**✅ Check 1 — dry run (no database):**

```bash
python -m product_search_analysis.collect --per-category 5 --dry-run
```

Expected: a summary with `"fetched": 25` and `"inserted": 0`.

**✅ Check 2 — the real collection:**

```bash
python -m product_search_analysis.collect
```

This collects up to 150 × 5 = 750 products. It streams several hundred MB,
so it can take a few minutes. Watch the log lines for progress.
Expected: `"inserted"` ≈ 700+, and `"total_in_db"` the same.

---

## Step 7 — Look at your data

In the Neon console → **SQL Editor**:

```sql
SELECT category, COUNT(*), ROUND(AVG(price), 2) AS avg_price
FROM products GROUP BY category ORDER BY category;

SELECT title, brand, price, rating FROM products WHERE category = 'tv' LIMIT 5;
```

🎉 Stage 1 is done: you have a clean product dataset in PostgreSQL.

---

## Step 8 — Export the data so collaborators can see it (`product_search_analysis/export.py`)

**Goal:** write the products from PostgreSQL into files inside the repo, so
anyone can view them on GitHub or in VS Code — no database login needed.

The `data/` folder already exists (with a `README.md` describing the files),
and `config.DATA_DIR` from Step 2 points to it — so `export.py` just imports
that path instead of building its own.

| File | Contents | Good for |
|---|---|---|
| `data/products.csv` | one row per product, main columns only | GitHub shows it as a searchable table; opens in Excel |
| `data/products.jsonl` | every field, incl. `specs` and `features` | full data for code / later stages |

Create **`product_search_analysis/export.py`**:

```python
# product_search_analysis/export.py
"""Export products from PostgreSQL to data/products.csv and data/products.jsonl."""
import csv
import json

from product_search_analysis import db
from product_search_analysis.config import DATA_DIR

CSV_COLUMNS = ["product_id", "category", "brand", "title", "price", "rating", "source_url"]


def fetch_all(conn) -> list[dict]:
    """Read every product from the database as a list of dicts."""
    cursor = conn.execute(
        "SELECT product_id, title, description, brand, category, price, specs, features,"
        " image_url, source_url, rating, source FROM products ORDER BY category, product_id"
    )
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def write_csv(products: list[dict]) -> None:
    # utf-8-sig so Excel shows special characters (™, é) correctly
    with open(DATA_DIR / "products.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(products)


def write_jsonl(products: list[dict]) -> None:
    with open(DATA_DIR / "products.jsonl", "w", encoding="utf-8") as f:
        for p in products:
            # default=float turns the database's Decimal prices into normal numbers
            f.write(json.dumps(p, ensure_ascii=False, default=float) + "\n")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with db.connect() as conn:
        products = fetch_all(conn)
    write_csv(products)
    write_jsonl(products)
    print(f"Exported {len(products)} products to {DATA_DIR}")


if __name__ == "__main__":
    main()
```

**✅ Check**

```bash
python -m product_search_analysis.export
```

Expected: `Exported 7xx products to .../data`. Open `data/products.csv` in VS Code.

**Share it:** commit the `data/` folder and push. Re-run the export after every
new collection so the files stay up to date.

```bash
git add data/ && git commit -m "Update product data export" && git push
```

> ⚠️ **Keep the repo private.** The Amazon dataset is for research use and must
> not be redistributed publicly. For a public repo, export only a small sample
> (e.g. add `LIMIT 50` to the query) or don't commit `data/`.

---

## What to add later (only when you need it)

Each of these is an independent upgrade — do them one at a time:

| Upgrade | Why | Where |
|---|---|---|
| Retry on network errors | a dropped connection shouldn't kill a long run | `scraping/amazon.py` → wrap `stream_records` in a retry loop |
| Second source (e.g. Best Buy API) | more / different products | new file `scraping/bestbuy.py` with the same `fetch_products(per_category)` function, then a `--source` option in `collect.py` |
| More tests | confidence when changing code | `test/` — test `to_product()` with one sample record |
| Read data for later stages | Stage 2 (search index) needs the products | add `find_all(category=None)` to `db.py` |

## License note

Amazon Reviews 2023 (McAuley Lab, UC San Diego) is released for research use.
Cite: *Hou et al., "Bridging Language and Items for Retrieval and Recommendation", 2024.*
Don't redistribute the raw data; product text and images belong to Amazon and the sellers.
