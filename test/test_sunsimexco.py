import html
import json

from product_search_analysis.cleaning import clean_product, is_valid
from product_search_analysis.scraping.sunsimexco.sunsimexco import (
    parse_brand,
    parse_listing_page,
    parse_prices,
    spec_lines,
    to_product,
)

SPEC = ("<h3><strong>Specification:</strong></h3><ul><li>32inch, Full HD</li><li>Bluetooth</li>"
        "<li>Stereo Speaker: 10Wx2</li><li>Power Consumption:&nbsp;55w</li></ul>")
SALE = "<span style='text-decoration: line-through; opacity: 0.5;'>$139.00</span> $119.00"


def item(**changes):
    """One product as it appears in the listing page's JSON (trimmed)."""
    base = {
        "id": 2605, "name": "AKIRA TV-FLAT FULL-HD SMART 32INCHES - 32LEDW2T2", "sku": "32LEDW2T2",
        "slug": "akira-tv-flat-smart-32inches-32ledw2t2",
        "image_url": "https://sunsimexco.com.kh/storage/media/32LEDW2T2-1.jpg",
        "html_price": SALE, "excerpt": SPEC, "description": SPEC,
        "subcategory_name": "All TVs", "discounted_percentage": 14.39,
    }
    return {**base, **changes}


def inertia_page(props: dict) -> str:
    """HTML the way the site sends it: page JSON inside the data-page attribute."""
    return f'<div id="app" data-page="{html.escape(json.dumps({"props": props}))}"></div>'


def test_parse_prices():
    assert parse_prices(SALE) == (119.0, 139.0)
    assert parse_prices("$1,649.00") == (1649.0, None)
    assert parse_prices("Call for price") == (None, None)


def test_spec_lines():
    assert spec_lines(SPEC) == ["32inch, Full HD", "Bluetooth", "Stereo Speaker: 10Wx2", "Power Consumption: 55w"]
    assert spec_lines("<h3>Specification:</h3>") == []
    assert spec_lines(None) == []


def test_to_product():
    product, reason = to_product(item(), "tv")
    assert reason is None
    assert product["product_id"] == "sunsimexco:2605"
    assert product["price"] == 119.0
    assert product["source_url"] == "https://sunsimexco.com.kh/products/akira-tv-flat-smart-32inches-32ledw2t2"
    assert product["description"] == "32inch, Full HD | Bluetooth | Stereo Speaker: 10Wx2 | Power Consumption: 55w"
    assert product["specs"]["Power Consumption"] == "55w"
    assert product["specs"]["Old price"] == "$139.00"
    assert product["specs"]["SKU"] == "32LEDW2T2"
    assert is_valid(clean_product(product))


def test_skipped_products():
    assert to_product(item(html_price="Call for price"), "tv") == (None, "call for price")
    assert to_product(item(description="", excerpt=""), "tv") == (None, "no specification")
    assert to_product(item(description="<h3>Specification:</h3>", excerpt=None), "tv") == (None, "no specification")


def test_parse_listing_page_and_brand():
    listing = inertia_page({"products": {
        "data": [item()],
        "links": {"next": "https://sunsimexco.com.kh/products?category=tv-projector&page=2"},
    }})
    items, next_url = parse_listing_page(listing)
    assert [i["id"] for i in items] == [2605]
    assert next_url == "https://sunsimexco.com.kh/products?category=tv-projector&page=2"

    last = inertia_page({"products": {"data": [item()], "links": {"next": None}}})
    assert parse_listing_page(last)[1] is None

    detail = inertia_page({"product": {"data": {**item(), "brand": {"slug": "akira", "name": "AKIRA"}}}})
    assert parse_brand(detail) == "AKIRA"
    assert parse_brand(inertia_page({"product": {"data": item()}})) is None
