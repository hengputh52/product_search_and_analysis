"""Pure functions: turn notebookcheck.net HTML into data. No network access here."""
import json
import re

from bs4 import BeautifulSoup

from product_search_analysis.config import USD_PER_EUR

# A review URL: ".../Some-Title-review.1445346.0.html" ("review" but not "preview")
REVIEW_URL_RE = re.compile(r"^https://www\.notebookcheck\.net/[^?#]*(?<!p)review[^?#]*\.\d+\.0\.html$", re.IGNORECASE)
ARTICLE_URL_RE = re.compile(r"^https://www\.notebookcheck\.net/[^?#]+\.\d+\.0\.html$")
REVIEW_ID_RE = re.compile(r"\.(\d+)\.0\.html$")
CURRENCY = r"(USD|US\$|\$|EUR|Euro|€)"
PRICE_RE = re.compile(rf"{CURRENCY}?\s*(\d[\d.,]*)\s*{CURRENCY}?", re.IGNORECASE)  # "$1,299" or "1200 EUR"
TABLET_RE = re.compile(r"\b(tablet|ipad|pad|tab)\b", re.IGNORECASE)
HEADPHONES_RE = re.compile(r"headphone|earbud|earphone|headset|airpods|\bbuds\b|\bin-ear\b|\bover-ear\b", re.IGNORECASE)

# Scored reviews show their device class next to the score, e.g. "Gaming - Weighted Average".
# That label is the most reliable category, so it wins over the listing the review came from.
CLASS_TO_CATEGORY = {
    "Smartphone": "smartphone",
    "Tablet": "tablet",
    "Mini PC": "mini_pc",
    **{laptop_class: "laptop" for laptop_class in (
        "Office", "Gaming", "Subnotebook", "Multimedia", "Workstation",
        "Convertible", "Netbook", "Ultrabook", "Budget",
    )},
}
DEVICE_CLASS_RE = re.compile(r"^\s*(.+?)\s+-\s+Weighted Average")

# listing category -> (pattern, more specific category) checked against name + headline
NAME_RULES = {
    "laptop": [(TABLET_RE, "tablet")],      # detachables / 2-in-1 tablets
    "smartphone": [(TABLET_RE, "tablet")],
    "audio": [(HEADPHONES_RE, "headphones")],
}


def has_articles(listing_html: str) -> bool:
    """False once we've paged past the last listing page (no articles at all)."""
    soup = BeautifulSoup(listing_html, "html.parser")
    return any(
        ARTICLE_URL_RE.match(a["href"])
        for container in soup.select("div.introa_content")
        for a in container.find_all("a", href=True)
    )


def find_review_links(listing_html: str) -> list[str]:
    """Return review URLs from the main list of a category page (sidebars ignored)."""
    soup = BeautifulSoup(listing_html, "html.parser")
    links = []
    for container in soup.select("div.introa_content"):  # the main article list
        for a in container.find_all("a", href=True):
            href = a["href"]
            if REVIEW_URL_RE.match(href) and href not in links:
                links.append(href)
    return links


def review_id(url: str) -> str:
    """'...-review.1445346.0.html' -> '1445346'"""
    match = REVIEW_ID_RE.search(url)
    return match.group(1) if match else url


def parse_price(text: str) -> tuple[float | None, str | None]:
    """'1200 EUR' -> (1200.0, 'EUR'), '$1,299' -> (1299.0, 'USD'), '' -> (None, None)"""
    match = PRICE_RE.search(text or "")
    if not match or not (match.group(1) or match.group(3)):
        return None, None  # no number, or a number without a currency
    number = match.group(2).rstrip(".,")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", number):  # "1.299" = European thousands separator
        number = number.replace(".", "")
    amount = float(number.replace(",", ""))
    symbol = (match.group(1) or match.group(3)).lower()
    currency = "EUR" if symbol in ("eur", "euro", "€") else "USD"
    return amount, currency


def price_usd(text: str) -> float | None:
    """'$1,299' -> 1299.0, '1200 Euro' -> 1329.72 (converted with USD_PER_EUR), '' -> None"""
    amount, currency = parse_price(text)
    if amount is None or amount < 5:
        return None  # no price, or junk like '0 360' / '3 Euro' for a Mac Studio
    return amount if currency == "USD" else round(amount * USD_PER_EUR, 2)


def guess_category(text: str, listing_category: str) -> str:
    """Refine the listing's category using the product name + review headline.

    e.g. a tablet inside the Laptop listing -> 'tablet';
         'Sony WH-1000XM6 headphones review' inside Audio -> 'headphones'.
    """
    for pattern, category in NAME_RULES.get(listing_category, []):
        if pattern.search(text):
            return category
    return listing_category


def _product_jsonld(soup: BeautifulSoup) -> dict | None:
    """The schema.org 'Product' block that review pages embed for search engines."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
    return None


def _specs(table) -> dict[str, str]:
    """Rows of the reviewed device's 'Specifications' table."""
    specs = {}
    for row in table.select("div.specs_element"):
        label = row.find("div", class_="specs")
        value = row.find("div", class_="specs_details")
        if label and value:
            specs[label.get_text(" ", strip=True)] = value.get_text(" ", strip=True)
    return specs


def _device_class(soup: BeautifulSoup) -> str | None:
    """'<span>Gaming</span> - Weighted Average' -> 'Gaming' (only scored reviews have it)."""
    node = soup.find(string=re.compile("Weighted Average"))
    if node is None:
        return None
    match = DEVICE_CLASS_RE.match(node.parent.get_text(" ", strip=True))  # label is in a child <span>
    return match.group(1) if match else None


def parse_review_page(html: str, url: str, listing_category: str) -> dict | None:
    """Turn one review page into our product format. Returns None if it isn't a full review."""
    soup = BeautifulSoup(html, "html.parser")
    product = _product_jsonld(soup)
    table = soup.select_one("div.specs_whole")  # the first specs table = the reviewed device
    if not product or table is None:
        return None  # news piece ("gaming review", "review verdict"), ranking, comparison...

    review = product.get("review") or {}
    score = (review.get("reviewRating") or {}).get("ratingValue")  # 0-100; smartwatches have none
    device_class = _device_class(soup)
    specs = _specs(table)
    if device_class:
        specs["Device Class"] = device_class
    if score is not None:
        specs["Notebookcheck Rating"] = f"{score}%"
    brand = product.get("brand") or ""
    image = soup.find("meta", property="og:image")
    name = product.get("name", "")
    category = CLASS_TO_CATEGORY.get(device_class) or guess_category(
        f"{name} {review.get('headline', '')}", listing_category
    )

    return {
        "product_id": f"notebookcheck:{review_id(url)}",
        "title": name,
        "description": product.get("description") or review.get("reviewBody", ""),
        "brand": brand.get("name", "") if isinstance(brand, dict) else brand,
        "category": category,
        "price": price_usd(specs.get("Price", "")),  # always USD; original text stays in specs["Price"]
        "specs": specs,
        "features": [],
        "image_url": image["content"] if image else "",
        "source_url": url,
        "rating": round(score / 20, 2) if score is not None else None,  # 0-100 -> 0-5 like Amazon
        "source": "notebookcheck",
    }
