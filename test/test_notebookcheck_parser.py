import json

from product_search_analysis.scraping.notebookcheck import listing_page_url
from product_search_analysis.scraping.notebookcheck.parser import (
    find_review_links,
    guess_category,
    has_articles,
    parse_price,
    parse_review_page,
)

LISTING_HTML = """
<div class="nbc_menubar"><a href="https://www.notebookcheck.net/Sidebar-Phone-review.111.0.html">x</a></div>
<div class="introa_content">
  <a href="https://www.notebookcheck.net/Asus-TUF-Gaming-16-review.1445346.0.html">TUF</a>
  <a href="https://www.notebookcheck.net/Asus-TUF-Gaming-16-review.1445346.0.html">TUF again</a>
  <a href="https://www.notebookcheck.net/Windows-11-Insider-Preview-Build.1447000.0.html">news</a>
</div>
"""

PRODUCT_JSONLD = {
    "@type": "Product",
    "name": "Asus TUF Gaming 16 FX610J",
    "description": "We review the Asus TUF Gaming 16 with a Core i5 and RTX 5050.",
    "brand": {"@type": "Brand", "name": "Asus"},
    "review": {"reviewRating": {"ratingValue": 78, "bestRating": 100}},
}
REVIEW_HTML = f"""
<meta property="og:image" content="https://img/tuf.jpg">
<script type="application/ld+json">{json.dumps(PRODUCT_JSONLD)}</script>
<div class="specs_whole">
  <div class="specs_element"><div class="specs">Processor</div><div class="specs_details">Intel Core i5-14450HX</div></div>
  <div class="specs_element"><div class="specs">Price</div><div class="specs_details">1,199 USD</div></div>
</div>
"""


def test_find_review_links_uses_main_list_only_and_skips_previews():
    assert find_review_links(LISTING_HTML) == ["https://www.notebookcheck.net/Asus-TUF-Gaming-16-review.1445346.0.html"]


def test_parse_price():
    assert parse_price("1200 EUR") == (1200.0, "EUR")
    assert parse_price("$1,299") == (1299.0, "USD")
    assert parse_price("") == (None, None)


def test_guess_category_refines_by_name_and_headline():
    assert guess_category("Samsung Galaxy Tab S12", "smartphone") == "tablet"
    assert guess_category("Lenovo ThinkPad X1", "laptop") == "laptop"
    assert guess_category("Sony WH-1000XM6 Sony WH-1000XM6 headphones review", "audio") == "headphones"
    assert guess_category("JBL Charge 6 speaker review", "audio") == "audio"
    assert guess_category("Apple Mac mini M5 review", "mini_pc") == "mini_pc"  # no rules -> listing


def test_has_articles_detects_the_end_of_a_listing():
    assert has_articles(LISTING_HTML) is True
    assert has_articles('<div class="introa_content"></div>') is False


def test_listing_page_url():
    topic = "https://www.notebookcheck.net/Topics.92152.0.html?tag=25"
    assert listing_page_url(topic, 0) == topic                       # first page = plain URL
    assert listing_page_url(topic, 2) == topic + "&ns_page=2"
    assert listing_page_url("https://x/Laptop.315784.0.html", 1) == "https://x/Laptop.315784.0.html?ns_page=1"


def test_parse_review_page():
    url = "https://www.notebookcheck.net/Asus-TUF-Gaming-16-review.1445346.0.html"
    product = parse_review_page(REVIEW_HTML, url, "laptop")
    assert product["product_id"] == "notebookcheck:1445346"
    assert product["brand"] == "Asus"
    assert product["price"] == 1199.0
    assert product["rating"] == 3.9  # 78 / 100 -> 3.9 / 5
    assert product["specs"]["Processor"] == "Intel Core i5-14450HX"
    assert product["image_url"] == "https://img/tuf.jpg"


def test_parse_review_page_returns_none_for_non_reviews():
    assert parse_review_page("<html>news article</html>", "https://x/y.1.0.html", "laptop") is None


def test_parse_review_page_skips_news_pieces_without_specs_table():
    # short "gaming review" / "review verdict" news pieces have a Product block but no specs table
    html = f'<script type="application/ld+json">{json.dumps(PRODUCT_JSONLD)}</script>'
    assert parse_review_page(html, "https://x/y.1.0.html", "smartphone") is None


def test_parse_review_page_keeps_unscored_reviews():
    # smartwatch reviews have a specs table but no score
    watch = {**PRODUCT_JSONLD, "name": "Huawei Watch GT 7", "review": {}}
    html = REVIEW_HTML.replace(json.dumps(PRODUCT_JSONLD), json.dumps(watch))
    product = parse_review_page(html, "https://x/watch-review.1385834.0.html", "smartwatch")
    assert product["category"] == "smartwatch"
    assert product["rating"] is None
    assert "Notebookcheck Rating" not in product["specs"]


def test_device_class_label_decides_the_category():
    # a tablet that the "Audio" tag listed is still a tablet, because the page says so
    # real layout: <div><span style="...">Tablet</span> - Weighted Average</div>
    html = REVIEW_HTML + '<div><span style="font-weight:bold;">Tablet</span> - Weighted Average</div>'
    product = parse_review_page(html, "https://x/tab-review.1402404.0.html", "audio")
    assert product["category"] == "tablet"
    assert product["specs"]["Device Class"] == "Tablet"

    html = REVIEW_HTML + "<div><span>Gaming</span> - Weighted Average</div>"
    assert parse_review_page(html, "https://x/a.1.0.html", "mini_pc")["category"] == "laptop"
