"""Export products from PostgreSQL to new, timestamped files in data/:
    data/products_<YYYY-MM-DD_HHMMSS>.csv     main columns, opens in Excel
    data/products_<YYYY-MM-DD_HHMMSS>.jsonl   every field, one product per line
Every run creates new files; existing files are never overwritten.

Run:  python -m product_search_analysis.export
      python -m product_search_analysis.export --source amazon_web   # only one source
      python -m product_search_analysis.export --source amazon_web --category speaker
      (file names then include the filters: products_amazon_web_speaker_<date_time>.csv)
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from product_search_analysis import db
from product_search_analysis.config import DATA_DIR

CSV_COLUMNS = ["product_id", "category", "brand", "title", "price", "rating", "description",
               "image_url", "source_url", "source"]


def fetch_all(conn, source: str | None = None, categories: list[str] | None = None) -> list[dict]:
    """Read products from the database as a list of dicts, optionally only one source / some categories."""
    sql = (
        "SELECT product_id, title, description, brand, category, price, specs, features,"
        " image_url, source_url, rating, source FROM products"
    )
    conditions, params = [], []
    if source:
        conditions.append("source = %s")
        params.append(source)
    if categories:
        conditions.append("category = ANY(%s)")
        params.append(categories)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    cursor = conn.execute(sql + " ORDER BY category, product_id", params)
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# Mode "x" = create a NEW file; raises FileExistsError instead of overwriting.

def write_csv(products: list[dict], path: Path) -> None:
    # utf-8-sig so Excel shows special characters (™, é) correctly
    with open(path, "x", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(products)


def write_jsonl(products: list[dict], path: Path) -> None:
    with open(path, "x", encoding="utf-8") as f:
        for p in products:
            f.write(json.dumps(p, ensure_ascii=False, default=float) + "\n")


def export(source: str | None = None, categories: list[str] | None = None) -> list[Path]:
    """Write new CSV and JSONL files to data/ and return their paths."""
    DATA_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")  # e.g. 2026-11-12_143005
    name = "_".join(["products", *([source] if source else []), *(categories or []), stamp])
    paths = [DATA_DIR / f"{name}.{ext}" for ext in ("csv", "jsonl")]

    with db.connect() as conn:
        products = fetch_all(conn, source, categories)
    for write, path in zip((write_csv, write_jsonl), paths):
        write(products, path)
    print(f"Exported {len(products)} products to new files:")
    for path in paths:
        print(f"  {path.name}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Export products from the database to CSV and JSONL.")
    parser.add_argument("--source", help="export only this source, e.g. amazon_web (default: all)")
    parser.add_argument("--category", action="append",
                        help="export only this category, e.g. speaker (repeat for several; default: all)")
    args = parser.parse_args()
    export(args.source, args.category)


if __name__ == "__main__":
    main()
