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