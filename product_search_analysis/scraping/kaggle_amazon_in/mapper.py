"""Pure functions: turn one row of the Kaggle Amazon India CSV into our product format."""
import re

from product_search_analysis.config import INR_PER_USD, KAGGLE_AMAZON_IN_CATEGORY_RULES, MAX_REVIEW_TEXT_CHARS

TITLE_SPLIT_RE = re.compile(r"\s*\|\s*")
SPEC_BULLET_RE = re.compile(r"^([A-Za-z][A-Za-z /&()-]{1,30}):\s*(.+)$")  # "Display: 16.56cm HD+" -> key, value


def match_category(category_path: str) -> str | None:
    """'Electronics|WearableTechnology|SmartWatches' -> 'smartwatch' (None = not a device we want)."""
    for prefix, category in KAGGLE_AMAZON_IN_CATEGORY_RULES:
        if category_path.startswith(prefix):
            return category
    return None


def parse_inr(text: str) -> float | None:
    """'₹1,099' -> 1099.0, '' -> None"""
    digits = re.sub(r"[^\d.]", "", text or "")
    return float(digits) if digits else None


def parse_rating(text: str) -> float | None:
    """'4.2' -> 4.2; the dataset has one broken value '|' -> None"""
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def split_title(product_name: str) -> tuple[str, list[str]]:
    """'Redmi A1 (2GB RAM) | 5000mAh Battery | Android 12' -> ('Redmi A1 (2GB RAM)', ['5000mAh Battery', 'Android 12'])"""
    parts = [p for p in TITLE_SPLIT_RE.split(product_name) if p]
    return (parts[0] if parts else ""), parts[1:]


def map_row(row: dict, category: str) -> dict:
    """Convert one CSV row into our product format (not cleaned yet)."""
    title, title_bullets = split_title(row["product_name"])
    bullets = [b.strip() for b in row["about_product"].split("|") if b.strip()]

    specs = {}
    for bullet in bullets:  # "Processor: MediaTek Helio A22" becomes a spec
        match = SPEC_BULLET_RE.match(bullet)
        if match:
            specs[match.group(1).strip()] = match.group(2).strip()
    specs.update({
        "Price (INR)": row["discounted_price"],
        "List Price (INR)": row["actual_price"],
        "Discount": row["discount_percentage"],
        "Rating Count": row["rating_count"],
        "Review Titles": row["review_title"],
        "Review Excerpts": row["review_content"][:MAX_REVIEW_TEXT_CHARS],
    })

    price_inr = parse_inr(row["discounted_price"])
    return {
        "product_id": f"amazon_in:{row['product_id']}",
        "title": title,
        "description": " ".join(bullets),
        "brand": title.split()[0] if title else "",  # dataset has no brand column; first word is the brand
        "category": category,
        "price": round(price_inr / INR_PER_USD, 2) if price_inr is not None else None,  # USD
        "specs": specs,
        "features": title_bullets + bullets,
        "image_url": row["img_link"],
        "source_url": f"https://www.amazon.in/dp/{row['product_id']}",
        "rating": parse_rating(row["rating"]),
        "source": "kaggle_amazon_in",
    }
