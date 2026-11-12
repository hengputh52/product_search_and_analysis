import argparse
import json
import logging

from product_search_analysis import config, db
from product_search_analysis.cleaning import clean_product, deduplicate, is_valid
from product_search_analysis.scraping import kaggle_amazon_in, notebookcheck
from product_search_analysis.scraping.amazon import amazon

# --source name -> module with fetch_products(per_category)
SOURCES = {"amazon": amazon, "notebookcheck": notebookcheck, "kaggle_amazon_in": kaggle_amazon_in}


def run(source: str, per_category: int, dry_run: bool) -> dict:
    raw = SOURCES[source].fetch_products(per_category)        # 1. download
    cleaned = [clean_product(r) for r in raw]                 # 2. clean
    valid = [p for p in cleaned if is_valid(p)]
    unique = deduplicate(valid)

    summary = {
        "source": source,
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
    parser.add_argument("--source", choices=sorted(SOURCES), default="amazon")
    parser.add_argument("--per-category", type=int, default=config.PRODUCTS_PER_CATEGORY)
    parser.add_argument("--dry-run", action="store_true", help="download + clean only, don't save")
    args = parser.parse_args()

    logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # hide one log line per HTTP request

    print(json.dumps(run(args.source, args.per_category, args.dry_run), indent=2))


if __name__ == "__main__":
    main()