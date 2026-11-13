from types import SimpleNamespace

import pytest

from product_search_analysis.cleaning import clean_product, is_valid
from product_search_analysis.scraping.amazon import amazon_scraping
from product_search_analysis.scraping.amazon.amazon_scraping import (
    get_product_info,
    parse_price_usd,
    parse_rating,
    to_product,
)

PRODUCT_HTML = """
<span id="productTitle">   Bose QuietComfort 45 Headphones - Triple Black   </span>
<span class="a-offscreen">$279.00</span>
<span id="acrPopover" title="4.6 out of 5 stars"></span>
<img id="landingImage" src="big.jpg">
<div id="feature-bullets"><ul>
  <li><span class="a-list-item">World-class noise cancellation</span></li>
  <li><span class="a-list-item">Up to 24 hours of battery life</span></li>
</ul></div>
"""
URL = "https://www.amazon.com/Bose-QuietComfort-45/dp/B098FKXT8L/ref=sr_1_1"


def fake_download(monkeypatch, html):
    """Make get_product_info read `html` instead of calling Amazon, without waiting."""
    monkeypatch.setattr(amazon_scraping.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(amazon_scraping.requests, "get",
                        lambda url, **kwargs: SimpleNamespace(status_code=200, text=html))


def test_get_product_info(monkeypatch):
    fake_download(monkeypatch, PRODUCT_HTML)
    info = get_product_info(URL)
    assert info["title"] == "Bose QuietComfort 45 Headphones - Triple Black"
    assert info["price"] == "$279.00"
    assert info["rating"] == "4.6 "
    assert info["features"] == ["World-class noise cancellation", "Up to 24 hours of battery life"]


def test_to_product_is_ready_for_the_database(monkeypatch):
    fake_download(monkeypatch, PRODUCT_HTML)
    product = to_product(get_product_info(URL), "headphones")
    assert product["product_id"] == "amazon_web:B098FKXT8L"
    assert product["source_url"] == "https://www.amazon.com/dp/B098FKXT8L"
    assert product["rating"] == 4.6
    assert product["description"] == "World-class noise cancellation Up to 24 hours of battery life"

    cleaned = clean_product(product)
    assert cleaned["price"] == 279.0
    assert is_valid(cleaned)


def test_sponsored_link_asin():
    info = {"url": "https://www.amazon.com/sspa/click?url=%2FPhone%2Fdp%2FB0AAAAAAA2%2Fref", "title": "Phone",
            "description": "A phone with a long enough description", "features": [], "price": None,
            "rating": None, "image": None}
    assert to_product(info, "smartphone")["product_id"] == "amazon_web:B0AAAAAAA2"


def test_captcha_page_stops_the_scraper(monkeypatch, tmp_path):
    monkeypatch.setattr(amazon_scraping, "FAILED_PAGES_DIR", tmp_path)
    fake_download(monkeypatch, "<html><body>Click the button below to continue shopping</body></html>")
    with pytest.raises(amazon_scraping.Blocked):
        get_product_info(URL)


def test_503_dog_page_keeps_products_scraped_before_it(monkeypatch, tmp_path):
    """Amazon's 'Sorry! Something went wrong!' page (HTTP 503) stops the run; earlier products are kept."""
    monkeypatch.setattr(amazon_scraping, "FAILED_PAGES_DIR", tmp_path)
    monkeypatch.setattr(amazon_scraping, "visited_urls", set())
    monkeypatch.setattr(amazon_scraping, "AMAZON_WEB_SEARCHES", {"headphones": "https://www.amazon.com/s?k=hp"})
    monkeypatch.setattr(amazon_scraping.time, "sleep", lambda seconds: None)
    listing = ('<div data-asin="B098FKXT8L"><a href="/Bose/dp/B098FKXT8L/r"><h2>Bose</h2></a></div>'
               '<div data-asin="B0BLOCKED1"><a href="/Sony/dp/B0BLOCKED1/r"><h2>Sony</h2></a></div>')
    dog_page = SimpleNamespace(status_code=503, text="<html>Sorry! Something went wrong!</html>")
    pages = {"https://www.amazon.com/s?k=hp": SimpleNamespace(status_code=200, text=listing),
             "https://www.amazon.com/Bose/dp/B098FKXT8L/r": SimpleNamespace(status_code=200, text=PRODUCT_HTML)}
    monkeypatch.setattr(amazon_scraping.requests, "get", lambda url, **kwargs: pages.get(url, dog_page))

    products = amazon_scraping.fetch_products(per_category=10)
    assert [p["product_id"] for p in products] == ["amazon_web:B098FKXT8L"]
    assert (tmp_path / "blocked_product_page.html").exists()


def test_parse_listing_new_layout(monkeypatch):
    """Amazon now puts the <h2> inside the link: <a href><h2>..</h2></a>."""
    listing = '<div data-asin="B098FKXT8L"><a href="/Bose/dp/B098FKXT8L/ref=sr_1_1"><h2>Bose QC45</h2></a></div>'
    pages = {"https://www.amazon.com/s?k=headphones": listing}
    monkeypatch.setattr(amazon_scraping.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(amazon_scraping.requests, "get",
                        lambda url, **kwargs: SimpleNamespace(status_code=200, text=pages.get(url, PRODUCT_HTML)))
    monkeypatch.setattr(amazon_scraping, "visited_urls", set())
    results = amazon_scraping.parse_listing("https://www.amazon.com/s?k=headphones", max_pages=1)
    assert [r["url"] for r in results] == ["https://www.amazon.com/Bose/dp/B098FKXT8L/ref=sr_1_1"]


def test_parse_rating():
    assert parse_rating("4.5 ") == 4.5
    assert parse_rating(None) is None


def test_riel_price_is_converted_to_usd(monkeypatch):
    fake_download(monkeypatch, PRODUCT_HTML.replace("$279.00", "KHR1,116,000.00"))
    cleaned = clean_product(to_product(get_product_info(URL), "headphones"))
    assert cleaned["price"] == round(1_116_000 / amazon_scraping.KHR_PER_USD, 2)
    assert cleaned["specs"]["Price (as shown)"] == "KHR1,116,000.00"


def test_parse_price_usd():
    assert parse_price_usd("$1,279.00") == 1279.0
    assert parse_price_usd("KHR 4,000") == round(4000 / amazon_scraping.KHR_PER_USD, 2)
    assert parse_price_usd("€279,00") is None  # unknown currency: leave empty
    assert parse_price_usd(None) is None


def test_main_price_box_wins_over_first_price(monkeypatch):
    html = ('<span class="a-offscreen">KHR 76,447.35</span>' + PRODUCT_HTML.replace(
        '<span class="a-offscreen">$279.00</span>',
        '<div id="corePriceDisplay_desktop_feature_div"><span class="priceToPay">'
        '<span class="a-offscreen">$279.00</span></span></div>'))
    fake_download(monkeypatch, html)
    assert get_product_info(URL)["price"] == "$279.00"


def test_requests_ask_for_usd_and_english(monkeypatch):
    sent = {}

    def fake_get(url, **kwargs):
        sent.update(kwargs)
        return SimpleNamespace(status_code=200, text=PRODUCT_HTML)

    monkeypatch.setattr(amazon_scraping.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(amazon_scraping.requests, "get", fake_get)
    get_product_info(URL)
    assert sent["cookies"] == {"i18n-prefs": "USD", "lc-main": "en_US"}
    assert sent["headers"]["Accept-Language"].startswith("en-US")
