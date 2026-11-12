"""Source: notebookcheck.net reviews (web scraping).

For every device type in config.NOTEBOOKCHECK_LISTINGS (laptop, smartphone,
smartwatch, mini PC, audio, ...) it pages through the listing, opens each
review, and reads the product name, brand, rating, price and specification table.
"""
import logging

from product_search_analysis.config import NOTEBOOKCHECK_LISTINGS, NOTEBOOKCHECK_MAX_LISTING_PAGES
from product_search_analysis.scraping.notebookcheck import crawler, parser

log = logging.getLogger(__name__)


def listing_page_url(listing_url: str, page: int) -> str:
    """Page 0 is the plain URL; later pages add ns_page=N."""
    if page == 0:
        return listing_url
    separator = "&" if "?" in listing_url else "?"
    return f"{listing_url}{separator}ns_page={page}"


def fetch_products(per_category: int) -> list[dict]:
    """Return up to `per_category` reviewed products from each listing in the config."""
    products = []
    seen = set()  # a review can appear under several tags; keep it once
    for listing_category, listing_url in NOTEBOOKCHECK_LISTINGS.items():
        found = 0
        for page in range(NOTEBOOKCHECK_MAX_LISTING_PAGES):
            html = crawler.download(listing_page_url(listing_url, page))
            if not parser.has_articles(html):
                break  # past the last listing page
            for url in parser.find_review_links(html):
                if url in seen:
                    continue
                seen.add(url)
                product = parser.parse_review_page(crawler.download_review(url), url, listing_category)
                if product:
                    products.append(product)
                    found += 1
                if found >= per_category:
                    break
            if found >= per_category:
                break
        log.info("%s: %d products (read %d listing pages)", listing_category, found, page + 1)
    return products
