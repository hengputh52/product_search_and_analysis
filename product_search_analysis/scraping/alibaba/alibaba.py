"""Source: alibaba.com search results (source "alibaba").

Alibaba's search page is built by JavaScript after it loads, so plain `requests`
gets an empty page. This module opens it in a headless Chromium (Playwright),
scrolls each results page so lazy-loaded products appear, reads the product cards
with BeautifulSoup, then clicks the pagination's 'next' button. It reads the search results only: product-detail pages answer
scripts with a slider-verification page, so they are not opened.

Setup (once, inside the venv):
    pip install playwright
    python -m playwright install chromium

Scrape -> save to the database -> export CSV/JSONL (run from the project folder):
    python -m product_search_analysis.scraping.alibaba.alibaba --per-category 50
Search URLs, page/scroll limits and delay are in config.py (ALIBABA_*).
"""
import argparse
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from product_search_analysis.config import (
    ALIBABA_DELAY_SECONDS,
    ALIBABA_MAX_PAGES,
    ALIBABA_MAX_SCROLLS,
    ALIBABA_SEARCHES,
    CATEGORIES,
    DATA_DIR,
    KHR_PER_USD,
)

BASE_URL = "https://www.alibaba.com"
FAILED_PAGES_DIR = DATA_DIR / "raw" / "alibaba"  # pages we couldn't read (gitignored)
BLOCKED_MARKERS = ("punish", "slide to verify", "captcha", "unusual traffic")

PRODUCT_LINK_RE = re.compile(r"/product-detail/[^?#]*?_(\d+)\.html")
# "US$5.50-6.80", "$12.99", "KHR 22,000 - 30,000"
PRICE_RE = re.compile(
    r"(US\s?\$|\$|KHR)\s?([\d,]+(?:\.\d+)?)(?:\s*[-~]\s*(?:US\s?\$|\$|KHR)?\s?([\d,]+(?:\.\d+)?))?"
)
MOQ_RE = re.compile(r"Min\.?\s*(?:order|\.?\s*order)\s*:?\s*([\d,]+\s*[A-Za-z()/]+)", re.IGNORECASE)
RATING_RE = re.compile(r"\b([0-5]\.\d)\s*/\s*5(?:\.0)?\b")
# button / badge labels on the card that aren't product information
UI_LABELS = {"select", "certified", "compare", "add to compare", "chat now", "contact supplier", "add to cart"}


# ---------- parsing (pure functions, tested in test/test_alibaba.py) ----------

def product_id_of(href: str) -> str | None:
    """'//www.alibaba.com/product-detail/Wireless-Keyboard_1600123456789.html?x=1' -> '1600123456789'"""
    match = PRODUCT_LINK_RE.search(href or "")
    return match.group(1) if match else None


def parse_price(text: str) -> tuple[float | None, str | None]:
    """First price in `text` -> (lowest price in USD, the price text as shown)."""
    match = PRICE_RE.search(text or "")
    if not match:
        return None, None
    low = float(match.group(2).replace(",", ""))
    if match.group(1).upper() == "KHR":
        low = round(low / KHR_PER_USD, 2)
    return low, match.group(0).strip()


def find_card(link, pid: str):
    """The biggest element around `link` that contains links to this product only."""
    card = link
    for parent in link.parents:
        if parent.name in ("body", "html", "[document]"):
            break
        ids = {product_id_of(a.get("href")) for a in parent.select('a[href*="/product-detail/"]')}
        if ids - {None} != {pid}:
            break  # this parent already holds a neighbouring product
        card = parent
    return card


def card_to_product(card, pid: str, href: str, category: str) -> dict:
    """One search-result card -> product dict in our format (not cleaned yet)."""
    lines = [line for line in card.stripped_strings if line.lower() not in UI_LABELS]
    text = " ".join(lines)

    link_texts = [a.get_text(" ", strip=True) for a in card.select('a[href*="/product-detail/"]')]
    image = card.select_one("img")
    title = max(link_texts, key=len, default="") or (image.get("alt", "") if image else "")

    price, price_text = parse_price(text)
    moq = MOQ_RE.search(text)
    rating = RATING_RE.search(text)
    supplier = card.select_one('a[href*=".en.alibaba.com"], a[href*="/company_profile"]')
    image_url = (image.get("src") or image.get("data-src")) if image else None

    specs = {
        "Price (as shown)": price_text,
        "Min. order": moq.group(1).strip() if moq else None,
        "Supplier": supplier.get_text(" ", strip=True) if supplier else None,
    }
    return {
        "product_id": f"alibaba:{pid}",
        "title": title,
        "description": text,  # search cards have no description: use everything the card shows
        "brand": None,        # Alibaba lists suppliers, not brands (supplier is in specs)
        "category": category,
        "price": price,
        "specs": {k: v for k, v in specs.items() if v},
        "features": [],
        "image_url": urljoin("https:", image_url) if image_url else None,
        "source_url": urljoin(BASE_URL, href).split("?")[0],
        "rating": float(rating.group(1)) if rating else None,
        "source": "alibaba",
    }


def parse_search_html(html: str, category: str) -> list[dict]:
    """Rendered search page -> one product per /product-detail/ link, in page order."""
    soup = BeautifulSoup(html, "lxml")
    products = {}
    for link in soup.select('a[href*="/product-detail/"]'):
        pid = product_id_of(link.get("href"))
        if pid and pid not in products:
            products[pid] = card_to_product(find_card(link, pid), pid, link["href"], category)
    return list(products.values())


def is_blocked(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in BLOCKED_MARKERS)


# ---------- browser ----------

PRODUCT_LINKS = 'a[href*="/product-detail/"]'
# product ids currently on the page, in page order (computed in the browser)
PRODUCT_IDS_JS = """() => [...new Set(
    [...document.querySelectorAll('a[href*="/product-detail/"]')]
        .map(a => (a.href.match(/_(\\d+)\\.html/) || [])[1]).filter(Boolean)
)]"""
LOAD_MORE_RE = re.compile(r"^\s*(load|show|view) more", re.IGNORECASE)
NEXT_RE = re.compile(r"^\s*(next|next page|\u203a|\u00bb|>)\s*$", re.IGNORECASE)
STOP_AFTER_IDLE_SCROLLS = 3  # stop scrolling a page when this many scrolls in a row add no products


def scroll_to_end(page) -> None:
    """Scroll to the last loaded product, whether the page or an inner results box scrolls.

    mouse.wheel alone scrolls whatever is under the pointer, and the pointer starts at the
    top-left corner (the header), so the results list may never move.
    """
    page.locator(PRODUCT_LINKS).last.scroll_into_view_if_needed()
    size = page.viewport_size or {"width": 1280, "height": 720}
    page.mouse.move(size["width"] / 2, size["height"] / 2)  # pointer over the results
    page.mouse.wheel(0, 4000)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")


def scroll_current_page(page, category: str, page_no: int) -> None:
    """Scroll down until this results page stops loading more products (lazy loading)."""
    last_count, idle = 0, 0
    for _ in range(ALIBABA_MAX_SCROLLS):
        count = len(page.evaluate(PRODUCT_IDS_JS))
        idle = idle + 1 if count == last_count else 0
        if idle >= STOP_AFTER_IDLE_SCROLLS:
            break
        last_count = count
        load_more = page.get_by_role("button", name=LOAD_MORE_RE)
        if load_more.count():  # some layouts use a "Load more" button instead of auto-loading
            load_more.first.click()
        scroll_to_end(page)
        page.wait_for_timeout(int(ALIBABA_DELAY_SECONDS * 1000))
    print(f"{category}: page {page_no}: {last_count} products on the page", flush=True)


def find_next_button(page):
    """The pagination's enabled 'next' control, or None. Tries labels first, then class names."""
    candidates = [
        page.get_by_role("button", name=NEXT_RE),
        page.get_by_role("link", name=NEXT_RE),
        page.locator('[aria-label*="next" i]'),
        page.locator('[class*="pagination" i] [class*="next" i], [class*="pager" i] [class*="next" i]'),
    ]
    for locator in candidates:
        for i in range(locator.count()):
            button = locator.nth(i)
            classes = (button.get_attribute("class") or "").lower()
            disabled = (button.get_attribute("aria-disabled") == "true"
                        or button.get_attribute("disabled") is not None or "disabled" in classes)
            if button.is_visible() and not disabled:
                return button
    return None


def go_to_next_page(page, category: str, page_no: int) -> bool:
    """Click 'next' and wait until different products are shown. False when there is no next page."""
    from playwright.sync_api import Error as PlaywrightError

    button = find_next_button(page)
    if button is None:
        FAILED_PAGES_DIR.mkdir(parents=True, exist_ok=True)
        path = FAILED_PAGES_DIR / f"{category}_page{page_no}_no_next_button.html"
        path.write_text(page.content(), encoding="utf-8")
        print(f"{category}: no 'next page' button found after page {page_no} (last page, or the button "
              f"looks different). Page saved to {path}")
        return False

    before = ",".join(page.evaluate(PRODUCT_IDS_JS))
    time.sleep(ALIBABA_DELAY_SECONDS)
    button.click()
    try:
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_function(  # new products: the list of ids on the page changed
            "before => { const ids = (" + PRODUCT_IDS_JS + ")(); "
            "return ids.length > 0 && ids.join(',') !== before; }",
            arg=before, timeout=30_000)
    except PlaywrightError:
        print(f"{category}: clicked 'next' after page {page_no} but no new products appeared, stopping")
        return False
    return True


def explain_empty_page(html: str, name: str) -> None:
    FAILED_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = FAILED_PAGES_DIR / f"{name}.html"
    path.write_text(html, encoding="utf-8")
    if is_blocked(html):
        print(f"No products: BLOCKED by Alibaba (verification page). Saved to {path}")
    else:
        print(f"No products: page loaded ({len(html):,} chars) but no /product-detail/ links found. Saved to {path}")


def scrape_search(page, url: str, category: str, wanted: int, seen: set) -> list[dict]:
    """Open one search, then for each results page: scroll, read the products, click 'next'."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    try:
        page.wait_for_selector(PRODUCT_LINKS, timeout=30_000)
    except PlaywrightTimeout:
        explain_empty_page(page.content(), category)
        return []

    products = []
    for page_no in range(1, ALIBABA_MAX_PAGES + 1):
        scroll_current_page(page, category, page_no)
        for product in parse_search_html(page.content(), category):
            if product["product_id"] not in seen and len(products) < wanted:
                seen.add(product["product_id"])
                products.append(product)
        print(f"{category}: {len(products)} products so far", flush=True)
        if len(products) >= wanted or page_no == ALIBABA_MAX_PAGES:
            break
        if not go_to_next_page(page, category, page_no):
            break
    return products


# ---------- entry point used by collect.py ----------

def fetch_products(per_category: int) -> list[dict]:
    """Return up to `per_category` products for each search in config.ALIBABA_SEARCHES."""
    unknown = [c for c in ALIBABA_SEARCHES if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Add {unknown} to CATEGORIES in config.py before scraping them")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("Playwright is missing. Run:\n  pip install playwright\n  python -m playwright install chromium")

    products, seen = [], set()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(locale="en-US")
        for number, (category, url) in enumerate(ALIBABA_SEARCHES.items()):
            if number:
                time.sleep(ALIBABA_DELAY_SECONDS)
            found = scrape_search(page, url, category, per_category, seen)
            products += found
            print(f"{category}: {len(found)} products in total", flush=True)
        browser.close()
    return products


def main():
    from product_search_analysis import collect, export  # here because collect.py imports this file

    parser = argparse.ArgumentParser(description="Scrape alibaba.com search results, save to the database, export.")
    parser.add_argument("--per-category", type=int, default=20,
                        help=f"max products per search (default 20). At most {ALIBABA_MAX_PAGES} result pages per search")
    args = parser.parse_args()

    summary = collect.run("alibaba", per_category=args.per_category, dry_run=False)
    print(summary)
    if summary["inserted"] == 0:
        print("Nothing new was saved, so no export was made.")
        return
    export.export(source="alibaba", categories=list(ALIBABA_SEARCHES))


if __name__ == "__main__":
    main()
