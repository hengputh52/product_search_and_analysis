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