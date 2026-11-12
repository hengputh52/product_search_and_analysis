"""Source: Kaggle "Amazon Sales Dataset" (karkavelrajaj) - Amazon India, January 2023.

Reads the local CSV (no network). Keeps only electronic devices listed in
config.KAGGLE_AMAZON_IN_CATEGORY_RULES; cables, chargers, kitchen items etc. are skipped.
License: CC BY-NC-SA 4.0 (non-commercial, give credit, share alike).
"""
import csv
import logging

from product_search_analysis.config import KAGGLE_AMAZON_IN_FILE
from product_search_analysis.scraping.kaggle_amazon_in.mapper import map_row, match_category

log = logging.getLogger(__name__)


def fetch_products(per_category: int) -> list[dict]:
    """Return up to `per_category` products per device category from the CSV."""
    if not KAGGLE_AMAZON_IN_FILE.exists():
        raise FileNotFoundError(
            f"{KAGGLE_AMAZON_IN_FILE} not found. Download it with:\n"
            "  kaggle datasets download -d karkavelrajaj/amazon-sales-dataset -p data/raw/kaggle --unzip"
        )

    products = []
    counts: dict[str, int] = {}
    seen_ids = set()  # the CSV lists some products twice
    with open(KAGGLE_AMAZON_IN_FILE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            category = match_category(row["category"])
            if category is None or row["product_id"] in seen_ids:
                continue
            if counts.get(category, 0) >= per_category:
                continue
            seen_ids.add(row["product_id"])
            products.append(map_row(row, category))
            counts[category] = counts.get(category, 0) + 1

    log.info("kaggle_amazon_in: %s", counts)
    return products
