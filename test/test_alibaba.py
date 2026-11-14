from product_search_analysis.cleaning import clean_product, is_valid
from product_search_analysis.scraping.alibaba import alibaba
from product_search_analysis.scraping.alibaba.alibaba import (
    is_blocked,
    parse_price,
    parse_search_html,
    product_id_of,
)

# Two cards side by side, roughly like a rendered search page. The scraper doesn't rely on
# class names: it groups everything around each /product-detail/ link.
SEARCH_HTML = """
<div class="grid">
  <div class="card">
    <label>Select</label><span>certified</span>
    <a href="//www.alibaba.com/product-detail/Wireless-Mechanical-Keyboard-RGB_1600123456789.html?spm=x">
      <img src="//s.alicdn.com/kb1.jpg" alt="Wireless Mechanical Keyboard">
    </a>
    <h2><a href="//www.alibaba.com/product-detail/Wireless-Mechanical-Keyboard-RGB_1600123456789.html?spm=x">
      Wireless Mechanical Keyboard RGB Backlit 87 Keys</a></h2>
    <div>US$12.50-15.80</div>
    <div>Min. order: 10 pieces</div>
    <div>4.8/5.0 (32)</div>
    <a href="https://shenzhen-kb.en.alibaba.com/">Shenzhen KB Technology Co., Ltd.</a>
  </div>
  <div class="card">
    <a href="//www.alibaba.com/product-detail/Office-Keyboard_1600999999999.html"><img data-src="//s.alicdn.com/kb2.jpg" alt="Office Keyboard"></a>
    <h2><a href="//www.alibaba.com/product-detail/Office-Keyboard_1600999999999.html">Office USB Wired Keyboard Slim Silent</a></h2>
    <div>$3.20</div>
    <div>Min. order: 500 pieces</div>
  </div>
</div>
"""


def test_product_id_of():
    assert product_id_of("//www.alibaba.com/product-detail/Wireless-Keyboard_1600123456789.html?x=1") == "1600123456789"
    assert product_id_of("https://www.alibaba.com/showroom/keyboard.html") is None


def test_parse_price():
    assert parse_price("US$12.50-15.80") == (12.5, "US$12.50-15.80")
    assert parse_price("Price $3.20 / piece") == (3.2, "$3.20")
    assert parse_price("KHR 40,000") == (round(40000 / alibaba.KHR_PER_USD, 2), "KHR 40,000")
    assert parse_price("no price") == (None, None)


def test_parse_search_html():
    products = parse_search_html(SEARCH_HTML, "keyboard")
    assert [p["product_id"] for p in products] == ["alibaba:1600123456789", "alibaba:1600999999999"]

    first, second = products
    assert first["title"] == "Wireless Mechanical Keyboard RGB Backlit 87 Keys"
    assert first["price"] == 12.5
    assert first["rating"] == 4.8
    assert first["image_url"] == "https://s.alicdn.com/kb1.jpg"
    assert first["source_url"] == "https://www.alibaba.com/product-detail/Wireless-Mechanical-Keyboard-RGB_1600123456789.html"
    assert first["specs"] == {
        "Price (as shown)": "US$12.50-15.80",
        "Min. order": "10 pieces",
        "Supplier": "Shenzhen KB Technology Co., Ltd.",
    }
    # the second card's data must not leak into the first, and the other way round
    assert "Office" not in first["description"]
    assert first["description"].startswith("Wireless Mechanical Keyboard")  # "Select certified" removed
    assert second["price"] == 3.2
    assert second["rating"] is None
    assert second["image_url"] == "https://s.alicdn.com/kb2.jpg"
    assert second["specs"]["Min. order"] == "500 pieces"

    assert all(is_valid(clean_product(p)) for p in products)  # ready for the database


def test_blocked_page():
    assert is_blocked('<div id="nocaptcha">Please slide to verify</div>')
    assert parse_search_html("<html><body>Please slide to verify</body></html>", "keyboard") == []
