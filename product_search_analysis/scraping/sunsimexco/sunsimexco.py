"""Source: sunsimexco.com.kh (electronics shop in Cambodia), source "sunsimexco".

The site is built with Inertia.js: every page carries its data as JSON in the
`data-page` attribute, so this module reads that JSON instead of the HTML.

For every listing in config.SUNSIMEXCO_LISTINGS it reads the listing pages
(100 products each, following the "next" link: ...&page=2, &page=3, ...) and
  - skips products shown as "Call for price" (no exact price)
  - skips products with no specification / description
  - opens the detail page of the remaining products to read the brand
The specification shown on the detail page is the product's `description`,
which the listing JSON already contains. robots.txt allows everything.

Scrape -> save to the database -> export CSV/JSONL (run from the project folder):
    python -m product_search_analysis.scraping.sunsimexco.sunsimexco
Or step by step with the normal pipeline:
    python -m product_search_analysis.collect --source sunsimexco --per-category 500
    python -m product_search_analysis.export --source sunsimexco
"""
import argparse
import json
import re
import time

import requests
from bs4 import BeautifulSoup

from product_search_analysis.config import (
    CATEGORIES,
    SUNSIMEXCO_DELAY_SECONDS,
    SUNSIMEXCO_LISTINGS,
    SUNSIMEXCO_MAX_PAGES,
    USER_AGENT,
)

BASE_URL = "https://sunsimexco.com.kh"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
SPEC_RE = re.compile(r"^([A-Za-z][\w /&().+*-]{0,40}?)\s*:\s*(.+)$")  # "Power Consumption: 55w" -> key, value
HEADING_RE = re.compile(r"^(specifications?|features?|description)\s*:?$", re.IGNORECASE)


# ---------- network ----------

def download(url: str) -> str | None:
    """GET a page after waiting SUNSIMEXCO_DELAY_SECONDS. None on errors."""
    time.sleep(SUNSIMEXCO_DELAY_SECONDS)
    try:
        response = requests.get(url, headers=HEADERS, timeout=60)
    except requests.RequestException as error:
        print(f"Network error on {url}: {error}")
        return None
    if response.status_code != 200:
        print(f"HTTP {response.status_code} on {url}")
        return None
    return response.content.decode("utf-8", errors="replace")


# ---------- parsing (pure functions, tested in test/test_sunsimexco.py) ----------

def page_data(html: str) -> dict:
    """The Inertia page JSON: <div id="app" data-page="{...}">."""
    element = BeautifulSoup(html, "lxml").select_one("[data-page]")
    return json.loads(element["data-page"]) if element else {}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_prices(html_price: str | None) -> tuple[float | None, float | None]:
    """"<span style='text-decoration: line-through'>$139.00</span> $119.00" -> (119.0, 139.0).

    Returns (current price, old price). "Call for price" -> (None, None).
    """
    soup = BeautifulSoup(html_price or "", "lxml")
    old_element = soup.select_one('[style*="line-through"]')
    old_text = old_element.get_text() if old_element else ""
    if old_element:
        old_element.decompose()
    current = PRICE_RE.search(soup.get_text())
    old = PRICE_RE.search(old_text)
    as_float = lambda match: float(match.group(1).replace(",", "")) if match else None  # noqa: E731
    return as_float(current), as_float(old)


def spec_lines(description_html: str | None) -> list[str]:
    """Specification HTML -> one line per bullet / paragraph, without the 'Specification:' heading."""
    soup = BeautifulSoup(description_html or "", "lxml")
    elements = soup.select("li, p, tr")
    if elements:
        lines = [clean(e.get_text(" ")) for e in elements if not e.find(["li", "p", "tr"])]
    else:
        lines = [clean(line) for line in soup.get_text("\n").splitlines()]
    return [line for line in lines if line and not HEADING_RE.match(line)]


def to_product(item: dict, category: str) -> tuple[dict | None, str | None]:
    """One product from the listing JSON -> (product in our format, None) or (None, reason skipped)."""
    price, old_price = parse_prices(item.get("html_price"))
    if price is None:
        return None, "call for price"
    lines = spec_lines(item.get("description") or item.get("excerpt"))
    if not lines:
        return None, "no specification"

    specs = {}
    for line in lines:
        match = SPEC_RE.match(line)
        if match:
            specs.setdefault(match.group(1).strip(), match.group(2).strip())
    specs.update({
        "SKU": item.get("sku"),
        "Subcategory": item.get("subcategory_name"),
        "Old price": f"${old_price:,.2f}" if old_price else None,
        "Discount (%)": item.get("discounted_percentage") or None,
        "Price (as shown)": f"${price:,.2f}",
    })
    return {
        "product_id": f"sunsimexco:{item['id']}",
        "title": clean(item.get("name") or ""),
        "description": " | ".join(lines),
        "brand": None,  # read from the detail page
        "category": category,
        "price": price,
        "specs": {k: v for k, v in specs.items() if v not in (None, "")},
        "features": lines,
        "image_url": item.get("image_url"),
        "source_url": f"{BASE_URL}/products/{item['slug']}",
        "rating": None,  # the shop shows no ratings
        "source": "sunsimexco",
    }, None


def parse_listing_page(html: str) -> tuple[list[dict], str | None]:
    """Listing page -> (raw product dicts from the JSON, URL of the next page or None)."""
    products = page_data(html).get("props", {}).get("products") or {}
    return products.get("data") or [], (products.get("links") or {}).get("next")


def parse_brand(html: str) -> str | None:
    """Detail page -> brand name, e.g. 'AKIRA'."""
    product = page_data(html).get("props", {}).get("product") or {}
    product = product.get("data", product)
    brand = product.get("brand")
    return clean(brand.get("name") or "") or None if isinstance(brand, dict) else None


# ---------- entry point used by collect.py ----------

def fetch_products(per_category: int) -> list[dict]:
    """Return up to `per_category` priced products with a specification for each listing."""
    unknown = [c for c in SUNSIMEXCO_LISTINGS if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Add {unknown} to CATEGORIES in config.py before scraping them")

    products, seen = [], set()
    for category, url in SUNSIMEXCO_LISTINGS.items():
        found, page = 0, 1
        skipped = {"call for price": 0, "no specification": 0}
        while url and page <= SUNSIMEXCO_MAX_PAGES and found < per_category:
            print(f"{category}: page {page} {url}", flush=True)
            html = download(url)
            if html is None:
                break
            items, url = parse_listing_page(html)
            if not items:
                print(f"{category}: no products on page {page}, stopping")
                break
            for item in items:
                if found >= per_category:
                    break
                product, reason = to_product(item, category)
                if product is None:
                    skipped[reason] += 1
                    continue
                if product["product_id"] in seen:
                    continue
                seen.add(product["product_id"])
                detail = download(product["source_url"])
                product["brand"] = parse_brand(detail) if detail else None
                products.append(product)
                found += 1
            print(f"{category}: {found} products kept so far, skipped {skipped}", flush=True)
            page += 1
    return products


def main():
    from product_search_analysis import collect, export  # here because collect.py imports this file

    parser = argparse.ArgumentParser(description="Scrape sunsimexco.com.kh, save to the database, export.")
    parser.add_argument("--per-category", type=int, default=10_000,
                        help=f"max products per listing (default: all, up to {SUNSIMEXCO_MAX_PAGES} pages)")
    args = parser.parse_args()

    summary = collect.run("sunsimexco", per_category=args.per_category, dry_run=False)
    print(summary)
    if summary["inserted"] == 0:
        print("Nothing new was saved, so no export was made.")
        return
    export.export(source="sunsimexco", categories=list(SUNSIMEXCO_LISTINGS))


if __name__ == "__main__":
    main()
