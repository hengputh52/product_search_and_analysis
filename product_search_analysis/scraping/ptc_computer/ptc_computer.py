"""Source: ptc-computer.com.kh (a computer shop in Cambodia), source "ptc_computer".

For every listing in config.PTC_COMPUTER_LISTINGS it reads the listing page,
follows the pagination's "next" link (?page=2, ?page=3, ...) until the last page,
and reads each product card: title, price (USD), old price, SKU, brand, stock,
image and the spec list shown on the card. Product pages are not opened: the
cards already hold everything. The site has no robots.txt.

Scrape -> save to the database -> export CSV/JSONL (run from the project folder):
    python -m product_search_analysis.scraping.ptc_computer.ptc_computer
Or step by step with the normal pipeline:
    python -m product_search_analysis.collect --source ptc_computer --per-category 500
    python -m product_search_analysis.export --source ptc_computer
"""
import argparse
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from product_search_analysis.config import (
    CATEGORIES,
    PTC_COMPUTER_DELAY_SECONDS,
    PTC_COMPUTER_LISTINGS,
    PTC_COMPUTER_MAX_PAGES,
    USER_AGENT,
)

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
PRICE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")
PRODUCT_NUMBER_RE = re.compile(r"\((\d+)")      # onclick="addToCompare(3856)" -> 3856
SPEC_RE = re.compile(r"^([A-Za-z][\w /&().+-]{0,30}):\s*(.+)$")  # "CPU: Intel Core i5" -> key, value


# ---------- network ----------

def download(url: str) -> str | None:
    """GET a page after waiting PTC_COMPUTER_DELAY_SECONDS. None on errors."""
    time.sleep(PTC_COMPUTER_DELAY_SECONDS)
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as error:
        print(f"Network error on {url}: {error}")
        return None
    if response.status_code != 200:
        print(f"HTTP {response.status_code} on {url}")
        return None
    return response.content.decode("utf-8", errors="replace")  # the site is UTF-8 (® ™ in specs)


# ---------- parsing (pure functions, tested in test/test_ptc_computer.py) ----------

def parse_price(text: str | None) -> float | None:
    """'$1,889' -> 1889.0"""
    match = PRICE_RE.search(text or "")
    return float(match.group(1).replace(",", "")) if match else None


def text_of(element) -> str:
    return element.get_text(" ", strip=True) if element else ""


def spec_lines(card) -> list[str]:
    """The card's spec list ('- CPU: Intel Core i5', ...) as clean lines."""
    block = card.select_one("#product_sort_description") or card.select_one("h3:nth-of-type(2) a")
    if not block:
        return []
    for br in block.find_all("br"):
        br.replace_with("\n")
    lines = [line.strip(" -–\t") for line in block.get_text("").splitlines()]
    return [re.sub(r"\s+", " ", line) for line in lines if line.strip(" -–\t")]


def parse_brand(card, title: str) -> str | None:
    """Brand logo link '/brand/dell-laptop-desktop-cambodia' -> 'Dell' (spelled as in the title)."""
    link = card.select_one('a[href*="/brand/"]')
    if not link:
        return None
    slug_word = link["href"].rstrip("/").rsplit("/", 1)[-1].split("-")[0]
    for word in title.split():
        if word.lower() == slug_word.lower():
            return word
    return slug_word.capitalize()


def parse_card(card, category: str) -> dict | None:
    """One .product-card -> product dict in our format (not cleaned yet)."""
    title_link = card.select_one("h3 a")
    if not title_link:
        return None
    title = text_of(title_link)
    url = title_link["href"]

    compare = card.select_one('[onclick*="addToCompare"]')
    number = PRODUCT_NUMBER_RE.search(compare["onclick"]) if compare else None
    product_key = number.group(1) if number else url.rstrip("/").rsplit("/", 1)[-1]

    price_element = card.select_one('span.fw-600[style*="18px"]')
    old_price = text_of(card.select_one("del"))
    image = card.select_one(".product_gallery img") or card.select_one("img.img-fit")
    lines = spec_lines(card)

    specs = {}
    for line in lines:
        match = SPEC_RE.match(line)
        if match:
            specs[match.group(1).strip()] = match.group(2).strip()
    specs.update({
        "SKU": text_of(card.select_one('[onclick*="enableCopy"]')),
        "Stock": text_of(card.select_one(".text-capitalize")),
        "Price (as shown)": text_of(price_element),
        "Old price": old_price,
    })

    return {
        "product_id": f"ptc_computer:{product_key}",
        "title": title,
        "description": " | ".join(lines) or title,
        "brand": parse_brand(card, title),
        "category": category,
        "price": parse_price(text_of(price_element)),
        "specs": {k: v for k, v in specs.items() if v},
        "features": lines,
        "image_url": (image.get("data-src") or image.get("src")) if image else None,
        "source_url": url,
        "rating": None,  # the stars on the cards are decoration, not ratings
        "source": "ptc_computer",
    }


def parse_listing_page(html: str, category: str, page_url: str) -> tuple[list[dict], str | None]:
    """Listing page -> (products, URL of the next page or None on the last page)."""
    soup = BeautifulSoup(html, "lxml")
    products = [p for p in (parse_card(card, category) for card in soup.select(".product-card")) if p]
    next_link = soup.select_one('.pagination a[rel="next"]')
    return products, (urljoin(page_url, next_link["href"]) if next_link else None)


# ---------- entry point used by collect.py ----------

def fetch_products(per_category: int) -> list[dict]:
    """Return up to `per_category` products for each listing in config.PTC_COMPUTER_LISTINGS."""
    unknown = [c for c in PTC_COMPUTER_LISTINGS if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Add {unknown} to CATEGORIES in config.py before scraping them")

    products, seen = [], set()
    for category, url in PTC_COMPUTER_LISTINGS.items():
        found, page = 0, 1
        while url and page <= PTC_COMPUTER_MAX_PAGES and found < per_category:
            print(f"{category}: page {page} {url}", flush=True)
            html = download(url)
            if html is None:
                break
            page_products, url = parse_listing_page(html, category, url)
            if not page_products:
                print(f"{category}: no products on page {page}, stopping")
                break
            for product in page_products:
                if product["product_id"] not in seen and found < per_category:
                    seen.add(product["product_id"])
                    products.append(product)
                    found += 1
            page += 1
        print(f"{category}: {found} products", flush=True)
    return products


def main():
    from product_search_analysis import collect, export  # here because collect.py imports this file

    parser = argparse.ArgumentParser(description="Scrape ptc-computer.com.kh, save to the database, export.")
    parser.add_argument("--per-category", type=int, default=10_000,
                        help=f"max products per listing (default: all, up to {PTC_COMPUTER_MAX_PAGES} pages)")
    args = parser.parse_args()

    summary = collect.run("ptc_computer", per_category=args.per_category, dry_run=False)
    print(summary)
    if summary["inserted"] == 0:
        print("Nothing new was saved, so no export was made.")
        return
    export.export(source="ptc_computer", categories=list(PTC_COMPUTER_LISTINGS))


if __name__ == "__main__":
    main()
