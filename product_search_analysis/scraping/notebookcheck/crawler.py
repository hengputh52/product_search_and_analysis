"""Network side: polite downloading of notebookcheck.net pages, with a local cache."""
import logging
import time

import httpx

from product_search_analysis.config import (
    NOTEBOOKCHECK_CACHE_DIR,
    NOTEBOOKCHECK_DELAY_SECONDS,
    USER_AGENT,
)
from product_search_analysis.scraping.notebookcheck.parser import review_id

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3

_client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
_last_request_at = 0.0


def download(url: str) -> str:
    """GET a page, waiting NOTEBOOKCHECK_DELAY_SECONDS between requests and retrying on errors."""
    global _last_request_at
    for attempt in range(1, MAX_ATTEMPTS + 1):
        wait = NOTEBOOKCHECK_DELAY_SECONDS - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()
        try:
            response = _client.get(url)
        except httpx.TransportError as error:
            if attempt == MAX_ATTEMPTS:
                raise
            log.warning("Network error (%s) on %s, retrying", error.__class__.__name__, url)
            time.sleep(5 * attempt)
            continue
        if response.status_code in RETRY_STATUS and attempt < MAX_ATTEMPTS:
            log.warning("HTTP %s on %s, retrying", response.status_code, url)
            time.sleep(5 * attempt)
            continue
        response.raise_for_status()
        log.debug("GET %s -> %s", url, response.status_code)
        return response.text
    raise RuntimeError("unreachable")


def download_review(url: str) -> str:
    """Review pages don't change, so keep a copy in data/raw/notebookcheck/ and reuse it."""
    cache_file = NOTEBOOKCHECK_CACHE_DIR / f"{review_id(url)}.html"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    html = download(url)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(html, encoding="utf-8")
    return html
