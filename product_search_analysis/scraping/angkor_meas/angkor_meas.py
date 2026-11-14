"""Source: angkormeas.com (a phone shop in Cambodia, WooCommerce), source "angkor_meas".

For every listing in config.ANGKOR_MEAS_LISTINGS it reads the listing page,
follows the "next" link (/page/2/, /page/3/, ...) until the last page, and for
each product:
  - from the listing card: title, current price, old (sale) price, stock, image
  - from the product page: description (variants and their prices, what's in the
    box, colours), brand and the full-size image
Products the shop shows in a listing but files under another category (e.g. a
tablet on the smartphone listing) are skipped.
robots.txt allows these pages for general crawlers.

Scrape -> save to the database -> export CSV/JSONL (run from the project folder):
    python -m product_search_analysis.scraping.angkor_meas.angkor_meas
Or step by step with the normal pipeline:
    python -m product_search_analysis.collect --source angkor_meas --per-category 500
    python -m product_search_analysis.export --source angkor_meas
"""
import argparse
import re
import time
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

from product_search_analysis.config import (
    ANGKOR_MEAS_DELAY_SECONDS,
    ANGKOR_MEAS_LISTINGS,
    ANGKOR_MEAS_MAX_PAGES,
    CATEGORIES,
    USER_AGENT,
)

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")  # \s* also covers the non-breaking space after "$"
SPEC_RE = re.compile(r"^([A-Za-z][\w /&().+-]{0,30}?)\s*:\s*(.+)$")  # "Color: Black, Blue" -> key, value


# ---------- network ----------

def download(url: str) -> str | None:
    """GET a page after waiting ANGKOR_MEAS_DELAY_SECONDS. None on errors."""
    time.sleep(ANGKOR_MEAS_DELAY_SECONDS)
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as error:
        print(f"Network error on {url}: {error}")
        return None
    if response.status_code != 200:
        print(f"HTTP {response.status_code} on {url}")
        return None
    return response.content.decode("utf-8", errors="replace")


# ---------- parsing (pure functions, tested in test/test_angkor_meas.py) ----------

def parse_price(text: str | None) -> float | None:
    """'$ 1,389' -> 1389.0"""
    match = PRICE_RE.search(text or "")
    return float(match.group(1).replace(",", "")) if match else None


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def category_slug(listing_url: str) -> str:
    """'https://angkormeas.com/cate/smartphone/' -> 'smartphone'"""
    return urlsplit(listing_url).path.rstrip("/").rsplit("/", 1)[-1]


def parse_listing_item(item, category: str) -> dict:
    """One <li class="product"> card -> partial product (the product page adds the rest)."""
    classes = item.get("class", [])
    post_id = next((c[len("post-"):] for c in classes if re.fullmatch(r"post-\d+", c)), None)
    link = item.select_one("a.woocommerce-LoopProduct-link") or item.select_one("a[href]")
    title = clean(item.select_one(".woocommerce-loop-product__title, h2").get_text(" "))
    image = item.select_one("img")

    price_box = item.select_one(".price")
    current = (price_box.select_one("ins .amount") or price_box.select_one(".amount")) if price_box else None
    old = price_box.select_one("del .amount") if price_box else None

    specs = {
        "Price (as shown)": clean(current.get_text(" ")) if current else None,
        "Old price": clean(old.get_text(" ")) if old else None,
        "Stock": "in stock" if "instock" in classes else "out of stock" if "outofstock" in classes else None,
        "Condition": "Used" if title.lower().startswith("used") else None,
    }
    return {
        "product_id": f"angkor_meas:{post_id or category_slug(link['href'])}",
        "title": title,
        "description": title,  # replaced by the product page's description
        "brand": None,         # read from the product page
        "category": category,
        "price": parse_price(current.get_text(" ") if current else None),
        "specs": {k: v for k, v in specs.items() if v},
        "features": [],
        "image_url": image.get("src") if image else None,
        "source_url": link["href"],
        "rating": None,  # the shop shows no ratings
        "source": "angkor_meas",
    }


def parse_listing_page(html: str, category: str, page_url: str) -> tuple[list[dict], int, str | None]:
    """Listing page -> (products filed under this listing's category, number skipped, next page URL)."""
    soup = BeautifulSoup(html, "lxml")
    wanted_class = f"product_cat-{category_slug(page_url.split('/page/')[0])}"
    products, skipped = [], 0
    for item in soup.select("li.product"):
        if wanted_class in item.get("class", []):
            products.append(parse_listing_item(item, category))
        else:
            skipped += 1  # e.g. a tablet shown on the smartphone listing
    next_link = soup.select_one("a.next.page-numbers")
    return products, skipped, (urljoin(page_url, next_link["href"]) if next_link else None)


def description_lines(block) -> list[str]:
    """Each <li>/<p> of the description as one line, without the text of nested lists."""
    lines = []
    for element in block.select("li, p"):
        parts = [child.get_text(" ") if isinstance(child, Tag) else str(child)
                 for child in element.children
                 if not (isinstance(child, Tag) and child.name in ("ul", "ol"))]
        line = clean(" ".join(parts))
        if line:
            lines.append(line)
    if not lines:  # plain text description
        lines = [clean(line) for line in block.get_text("\n").splitlines() if clean(line)]
    return lines


# The product's long description. Elementor gives every block on the page the class
# "elementor-widget-container" (header, menu, footer, ...), so only the one inside the
# "woocommerce-product-content" widget is the description. The others are WooCommerce defaults.
LONG_DESCRIPTION_SELECTORS = (
    ".elementor-widget-woocommerce-product-content .elementor-widget-container",
    ".woocommerce-Tabs-panel--description",
    "#tab-description",
)


def spec_table(block) -> dict:
    """Spec sheet tables ('Display' | 'Size' | '6.8 inches') -> {'Display - Size': '6.8 inches'}."""
    specs = {}
    for table in block.select("table"):
        section = clean(table.select_one("th").get_text(" ")) if table.select_one("th") else ""
        for row in table.select("tr"):
            label_cell, value_cell = row.select_one("td.ttl"), row.select_one("td.nfo")
            if value_cell is None:
                cells = row.select("td")
                if len(cells) < 2:
                    continue
                label_cell, value_cell = cells[-2], cells[-1]
            for br in value_cell.find_all("br"):
                br.replace_with("; ")
            value = clean(value_cell.get_text(" ")).replace(" ; ", "; ").strip("; ")
            if not value:
                continue
            label = clean(label_cell.get_text(" ")) if label_cell else ""
            key = " - ".join(part for part in (section, label or "Other") if part)
            specs[key] = f"{specs[key]}; {value}" if key in specs else value
    return specs


def add_product_page(product: dict, html: str) -> dict:
    """Fill in description, features, specs, brand and the full-size image from the product page."""
    soup = BeautifulSoup(html, "lxml")
    short = soup.select_one(".woocommerce-product-details__short-description")
    lines = description_lines(short) if short else []  # variants + prices, in the box, colours

    long_block = next((b for s in LONG_DESCRIPTION_SELECTORS if (b := soup.select_one(s))), None)
    sheet = spec_table(long_block) if long_block else {}
    if long_block and not sheet:  # a written description instead of a spec sheet
        lines += description_lines(long_block)

    specs = dict(product["specs"])
    for line in lines:
        match = SPEC_RE.match(line)
        if match:
            specs.setdefault(match.group(1).strip(), match.group(2).strip())
    specs.update(sheet)
    # the spec sheet goes into the description too, so it is searchable
    lines_for_description = lines + [f"{key}: {value}" for key, value in sheet.items()]
    for row in soup.select("table.woocommerce-product-attributes tr"):  # "Additional information" tab
        label, value = row.select_one("th"), row.select_one("td")
        if label and value:
            specs[clean(label.get_text(" "))] = clean(value.get_text(" "))

    brand = soup.select_one('.product_meta a[href*="/brand/"]')
    image = soup.select_one(".woocommerce-product-gallery__image img")
    big_image = (image.get("data-large_image") or image.get("src")) if image else None

    return {
        **product,
        "description": " | ".join(lines_for_description) or product["description"],
        "features": lines,
        "specs": specs,
        "brand": clean(brand.get_text(" ")) if brand else product["brand"],
        "image_url": big_image or product["image_url"],
    }


# ---------- entry point used by collect.py ----------

def fetch_products(per_category: int) -> list[dict]:
    """Return up to `per_category` products for each listing in config.ANGKOR_MEAS_LISTINGS."""
    unknown = [c for c in ANGKOR_MEAS_LISTINGS if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Add {unknown} to CATEGORIES in config.py before scraping them")

    products, seen = [], set()
    for category, url in ANGKOR_MEAS_LISTINGS.items():
        found, page = 0, 1
        while url and page <= ANGKOR_MEAS_MAX_PAGES and found < per_category:
            print(f"{category}: page {page} {url}", flush=True)
            html = download(url)
            if html is None:
                break
            page_products, skipped, url = parse_listing_page(html, category, url)
            if skipped:
                print(f"{category}: skipped {skipped} product(s) filed under another category")
            if not page_products and not skipped:
                print(f"{category}: no products on page {page}, stopping")
                break
            for product in page_products:
                if product["product_id"] in seen or found >= per_category:
                    continue
                seen.add(product["product_id"])
                product_html = download(product["source_url"])
                if product_html:
                    product = add_product_page(product, product_html)
                else:
                    print(f"  could not open {product['source_url']}, keeping the listing data only")
                products.append(product)
                found += 1
            print(f"{category}: {found} products so far", flush=True)
            page += 1
    return products


def main():
    from product_search_analysis import collect, export  # here because collect.py imports this file

    parser = argparse.ArgumentParser(description="Scrape angkormeas.com, save to the database, export.")
    parser.add_argument("--per-category", type=int, default=10_000,
                        help=f"max products per listing (default: all, up to {ANGKOR_MEAS_MAX_PAGES} pages)")
    args = parser.parse_args()

    summary = collect.run("angkor_meas", per_category=args.per_category, dry_run=False)
    print(summary)
    if summary["inserted"] == 0:
        print("Nothing new was saved, so no export was made.")
        return
    export.export(source="angkor_meas", categories=list(ANGKOR_MEAS_LISTINGS))


if __name__ == "__main__":
    main()
