"""Scrape amazon.com search results, save them to the database and export them.

Run from the project folder (scrape -> save to DB -> export CSV/JSON/JSONL):
    python -m product_search_analysis.scraping.amazon.amazon_scraping                      # 20 products (~1 page)
    python -m product_search_analysis.scraping.amazon.amazon_scraping --per-category 200   # ~10 pages
Or step by step with the normal pipeline:
    python -m product_search_analysis.collect --source amazon_web --per-category 20
    python -m product_search_analysis.export --source amazon_web
Search URLs, page limit and delay are in config.py (AMAZON_WEB_*).
"""
import argparse
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from product_search_analysis.config import (
    AMAZON_WEB_COOKIES,
    AMAZON_WEB_DELAY_SECONDS,
    AMAZON_WEB_MAX_PAGES,
    AMAZON_WEB_SEARCHES,
    DATA_DIR,
    KHR_PER_USD,
)

custom_headers = {
    # Firefox fingerprint: a different browser identity from Chrome. Firefox does NOT send
    # the sec-ch-ua client hints, so they are left out on purpose - adding them here would be
    # an inconsistent mix (Firefox UA + Chrome-only headers) that looks like a bot.
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',  # no 'br': requests can't decode it without the brotli package
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://www.google.com/'
}

visited_urls = set()
FAILED_PAGES_DIR = DATA_DIR / "raw" / "amazon_web"  # pages we couldn't read (gitignored)
ASIN_RE = re.compile(r"(?:/|%2F)dp(?:/|%2F)([A-Z0-9]{10})")  # also matches sponsored links (url-encoded)
# Amazon's answers to requests it thinks come from a bot: a captcha page, or the
# "Sorry! Something went wrong!" dog page with HTTP 503.
BLOCK_STATUS = {429, 503}
BLOCK_MARKERS = ("captcha", "continue shopping", "sorry! something went wrong")


class Blocked(Exception):
    """Amazon sent a robot-check page. `products` holds what was scraped before that."""

    def __init__(self, url, status):
        super().__init__(f"Amazon blocked the request (HTTP {status}): {url[:100]}")
        self.products = []


def check_blocked(response, url, saved_name):
    """Raise Blocked if Amazon answered with a robot-check page (saved to data/raw/amazon_web/)."""
    lowered = response.text.lower()
    if response.status_code in BLOCK_STATUS or any(marker in lowered for marker in BLOCK_MARKERS):
        FAILED_PAGES_DIR.mkdir(parents=True, exist_ok=True)
        (FAILED_PAGES_DIR / saved_name).write_text(response.text, encoding="utf-8")
        raise Blocked(url, response.status_code)


def get_product_info(url):
    time.sleep(AMAZON_WEB_DELAY_SECONDS)
    response = requests.get(url, headers=custom_headers, cookies=AMAZON_WEB_COOKIES)  # cookies: USD + English
    check_blocked(response, url, "blocked_product_page.html")
    if response.status_code != 200:
        print(f"Error in getting webpage: {url}")
        return None

    soup = BeautifulSoup(response.text, "lxml")

    title_element = soup.select_one("#productTitle")
    title = title_element.text.strip() if title_element else None

    # the product's own price box first; a plain 'span.a-offscreen' often hits a
    # monthly payment or a "related products" price that appears earlier on the page
    price_element = (
        soup.select_one('#corePriceDisplay_desktop_feature_div .priceToPay span.a-offscreen')
        or soup.select_one('#corePriceDisplay_desktop_feature_div span.a-offscreen')
        or soup.select_one('#corePrice_feature_div span.a-offscreen')
        or soup.select_one('#apex_desktop span.a-offscreen')
        or soup.select_one('span.a-offscreen')
    )
    price = price_element.text.strip() if price_element else None

    rating_element = soup.select_one("#acrPopover")
    rating_text = rating_element.attrs.get("title") if rating_element else None
    rating = rating_text.replace("out of 5 stars", "") if rating_text else None

    image_element = soup.select_one("#landingImage")
    image = image_element.attrs.get("src") if image_element else None

    description_element = soup.select_one("#productDescription")
    description = description_element.text.strip() if description_element else None

    # bullet points; used as the description when the page has none
    feature_elements = soup.select("#feature-bullets li span.a-list-item")
    features = [f.text.strip() for f in feature_elements if f.text.strip()]

    return {
        "title": title,
        "price": price,
        "rating": rating,
        "image": image,
        "description": description,
        "features": features,
        "url": url
    }


def explain_empty_page(html, page):
    """A real search page with no product links: save it to data/raw/amazon_web/ to look at."""
    FAILED_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = FAILED_PAGES_DIR / f"search_page{page}.html"
    path.write_text(html, encoding="utf-8")
    print(f"No products on page {page}: page loaded ({len(html):,} chars) but the selector "
          f"found no links - Amazon's HTML may have changed. Saved to {path}")


def parse_listing(listing_url, max_pages=20, page=1, max_products=None):
    global visited_urls
    time.sleep(AMAZON_WEB_DELAY_SECONDS)
    response = requests.get(listing_url, headers=custom_headers, cookies=AMAZON_WEB_COOKIES)
    print(f"Page {page}/{max_pages} - status {response.status_code}")
    check_blocked(response, listing_url, f"blocked_search_page{page}.html")
    soup_search = BeautifulSoup(response.text, "lxml")
    # old layout: <h2><a href>..</a></h2>   new layout: <a href><h2>..</h2></a>
    link_elements = soup_search.select("[data-asin] h2 a, [data-asin] a:has(> h2)")
    if not link_elements:
        explain_empty_page(response.text, page)
    page_data = []

    try:
        for link in link_elements:
            if max_products is not None and len(page_data) >= max_products:
                return page_data
            full_url = urljoin(listing_url, link.attrs.get("href"))
            # remember products by ASIN: sponsored links get a new URL every time they appear
            asin_match = ASIN_RE.search(full_url)
            key = asin_match.group(1) if asin_match else full_url
            if key not in visited_urls:
                visited_urls.add(key)
                print(f"Scraping product from {full_url[:100]}", flush=True)
                product_info = get_product_info(full_url)
                if product_info:
                    page_data.append(product_info)

        next_page_el = soup_search.select_one('a.s-pagination-next')
        need_more = max_products is None or len(page_data) < max_products
        if next_page_el and page < max_pages and need_more:
            next_page_url = next_page_el.attrs.get('href')
            next_page_url = urljoin(listing_url, next_page_url)
            print(f'Scraping next page: {next_page_url}', flush=True)
            remaining = None if max_products is None else max_products - len(page_data)
            page_data += parse_listing(next_page_url, max_pages, page + 1, remaining)
    except Blocked as blocked:
        blocked.products = page_data + blocked.products  # keep what this page already scraped
        raise

    return page_data


# ---------- database format ----------

def parse_price_usd(text):
    """'$279.00' -> 279.0, 'KHR 2,070,251.60' -> 517.56 (converted), anything else -> None"""
    if not text:
        return None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    amount = float(match.group().replace(",", ""))
    if text.strip().startswith("$"):
        return amount
    if text.strip().upper().startswith("KHR"):
        return round(amount / KHR_PER_USD, 2)
    return None


def parse_rating(text):
    """'4.5 ' -> 4.5, None -> None"""
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def to_product(info, category):
    """Convert one get_product_info() result into the database format. None if it can't be saved."""
    match = ASIN_RE.search(info["url"])
    if not match or not info["title"]:
        return None  # no product id, or a captcha page instead of the product
    asin = match.group(1)
    return {
        "product_id": f"amazon_web:{asin}",
        "title": info["title"],
        "description": info["description"] or " ".join(info["features"]),
        "brand": None,
        "category": category,
        "price": parse_price_usd(info["price"]),  # USD; riel converted with config.KHR_PER_USD
        "specs": {"Price (as shown)": info["price"]} if info["price"] else {},
        "features": info["features"],
        "image_url": info["image"],
        "source_url": f"https://www.amazon.com/dp/{asin}",
        "rating": parse_rating(info["rating"]),
        "source": "amazon_web",
    }


def fetch_products(per_category):
    """Used by collect.py: scrape every search in config.AMAZON_WEB_SEARCHES."""
    products = []
    for category, search_url in AMAZON_WEB_SEARCHES.items():
        try:
            infos = parse_listing(search_url, max_pages=AMAZON_WEB_MAX_PAGES, max_products=per_category)
            blocked = None
        except Blocked as error:
            infos, blocked = error.products, error
        for info in infos:
            product = to_product(info, category)
            if product:
                products.append(product)
            else:
                print(f"Skipped (no title): {info['url'][:100]}")
        if blocked:
            # every further request would be blocked too, so stop here and save what we have
            print(f"STOPPED: {blocked}. Robot-check page saved in {FAILED_PAGES_DIR}. "
                  f"Keeping {len(products)} products scraped before the block. "
                  "Wait a few hours and try again with a smaller --per-category.")
            break
    return products


def main():
    # imported here because collect.py imports this file
    from product_search_analysis import collect, export

    parser = argparse.ArgumentParser(description="Scrape amazon.com, save to the database, export.")
    parser.add_argument("--per-category", type=int, default=20,
                        help="max products per search (default 20, about 1 page). "
                             f"Pages are capped at config.AMAZON_WEB_MAX_PAGES = {AMAZON_WEB_MAX_PAGES}")
    args = parser.parse_args()

    summary = collect.run("amazon_web", per_category=args.per_category, dry_run=False)  # scrape -> clean -> save to DB
    print(summary)
    if summary["inserted"] == 0:
        print("Nothing new was saved, so no export was made.")
        return
    export.export(source="amazon_web")  # DB -> data/products_amazon_web_<date_time>.csv/.json/.jsonl


if __name__ == '__main__':
    main()
