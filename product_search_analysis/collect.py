import argparse
import json
import logging

from product_search_analysis import config, db
from product_search_analysis.cleaning import clean_product, deduplicate, is_valid
from product_search_analysis.scraping import kaggle_amazon_in, notebookcheck
from product_search_analysis.scraping.alibaba import alibaba
from product_search_analysis.scraping.amazon import amazon, amazon_scraping
from product_search_analysis.scraping.ptc_computer import ptc_computer
from product_search_analysis.scraping.angkor_meas import angkor_meas
from product_search_analysis.scraping.sunsimexco import sunsimexco

# --source name -> module with fetch_products(per_category)
SOURCES = {
    "amazon": amazon,
    "amazon_web": amazon_scraping,
    "alibaba": alibaba,
    "ptc_computer": ptc_computer,
    "angkor_meas": angkor_meas,
    "sunsimexco": sunsimexco,
    "notebookcheck": notebookcheck,
    "kaggle_amazon_in": kaggle_amazon_in,
}


def invalid_reason(product: dict) -> str:
    """Why is_valid() rejected a product (same rules as cleaning.is_valid)."""
    reasons = []
    if not product["title"]:
        reasons.append("no title")
    if len(product["description"]) < config.MIN_DESCRIPTION_LENGTH:
        reasons.append(f"description shorter than {config.MIN_DESCRIPTION_LENGTH} characters")
    if product["category"] not in config.CATEGORIES:
        reasons.append(f"category '{product['category']}' not in CATEGORIES")
    return ", ".join(reasons)


def save_invalid(source: str, products: list[dict]) -> None:
    """Write rejected products to data/raw/invalid_<source>.jsonl (overwritten each run) to look at."""
    if not products:
        return
    path = config.DATA_DIR / "raw" / f"invalid_{source}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p in products:
            f.write(json.dumps({"reason": invalid_reason(p), **p}, ensure_ascii=False, default=str) + "\n")
    print(f"{len(products)} invalid products (not saved to the database) written to {path}")


def run(source: str, per_category: int, dry_run: bool) -> dict:
    raw = SOURCES[source].fetch_products(per_category)        # 1. download
    cleaned = [clean_product(r) for r in raw]                 # 2. clean
    valid = [p for p in cleaned if is_valid(p)]
    save_invalid(source, [p for p in cleaned if not is_valid(p)])
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