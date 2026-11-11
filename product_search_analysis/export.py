"""Export products from PostgreSQL to data/products.csv and data/products.jsonl.

Run:  python -m product_search_analysis.export
"""
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
