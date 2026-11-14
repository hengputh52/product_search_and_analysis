from product_search_analysis.cleaning import clean_product, is_valid
from product_search_analysis.scraping.angkor_meas.angkor_meas import (
    add_product_page,
    parse_listing_page,
    parse_price,
)

# Trimmed copy of a real listing page: a normal product, a sale product, a tablet that the
# shop shows on the smartphone listing, and the pagination.
ITEM = """
<li class="product type-product post-{id} status-publish {stock} {cats}">
 <a class="woocommerce-LoopProduct-link woocommerce-loop-product__link" href="https://angkormeas.com/shop/{slug}/">
  <img src="https://angkormeas.com/wp-content/uploads/{slug}-300x300.jpg" alt="{title}">
  <h2 class="woocommerce-loop-product__title">{title}</h2>
  <span class="price">{price}</span>
 </a>
</li>
"""
AMOUNT = ('<span class="woocommerce-Price-amount amount"><bdi>'
          '<span class="woocommerce-Price-currencySymbol">$</span>\xa0{}</bdi></span>')
LISTING = (
    '<ul class="products">'
    + ITEM.format(id=31389, stock="instock", cats="product_cat-smartphone product_cat-honor",
                  slug="honor-x80-pro-max-256g8g", title="Honor X80 Pro Max 256G+8G", price=AMOUNT.format("389"))
    + ITEM.format(id=31300, stock="outofstock", cats="product_cat-smartphone product_cat-huawei",
                  slug="used-huawei-pura-90s-pro", title="Used Huawei Pura 90s Pro (OFF: $50)",
                  price=f'<del aria-hidden="true">{AMOUNT.format("749")}</del> '
                        f'<ins aria-hidden="true">{AMOUNT.format("1,699")}</ins>')
    + ITEM.format(id=31000, stock="instock", cats="product_cat-tablet product_cat-oneplus",
                  slug="used-oneplus-pad3", title="Used OnePlus Pad3 512G (99%)", price=AMOUNT.format("399"))
    + '</ul><nav class="woocommerce-pagination"><ul class="page-numbers">'
      '<li><span class="page-numbers current">1</span></li>'
      '<li><a class="next page-numbers" href="https://angkormeas.com/cate/smartphone/page/2/?">→</a></li></ul></nav>'
)
PRODUCT_PAGE = """
<div class="woocommerce-product-gallery__image">
  <img src="https://angkormeas.com/wp-content/uploads/honor-x80-600x600.jpg"
       data-large_image="https://angkormeas.com/wp-content/uploads/honor-x80.jpg"></div>
<div class="woocommerce-product-details__short-description">
 <ul>
  <li style="list-style-type: none"><ul>
    <li><strong><span>Honor X80 Pro Max (China)</span></strong></li>
    <li><span><strong>256G+8G :$389</strong></span></li>
  </ul></li>
  <li><strong><span>Promotion In Box:</span></strong>
   <ul><li><strong>Free Case</strong></li><li><strong>Adaptor</strong></li></ul></li>
  <li><span>Color: Black,Blue, Silver</span></li>
 </ul>
</div>
<div class="elementor-element elementor-widget elementor-widget-woocommerce-product-content">
 <div class="elementor-widget-container">
  <table><tr><th rowspan="2">Display</th><td class="ttl"><a href="#">Size</a></td><td class="nfo">6.61 inches</td></tr>
   <tr><td class="ttl"><a href="#">Resolution</a></td><td class="nfo">720 x 1604 pixels</td></tr></table>
  <table><tr><th rowspan="2">Body</th><td class="ttl">Weight</td><td class="nfo">207 g</td></tr>
   <tr><td class="ttl"></td><td class="nfo">IP64 dust tight<br>Drop resistant up to 1.8m</td></tr></table>
 </div>
</div>
<div class="elementor-widget-container">Khmer Speaking: 017-802-272 (header block, not the description)</div>
<div class="product_meta">
 <span class="posted_in">Categories <a href="https://angkormeas.com/cate/smartphone/">Smartphone</a></span>
 <span class="posted_in">Brand: <a href="https://angkormeas.com/brand/honor/" rel="tag">Honor</a></span>
</div>
"""
URL = "https://angkormeas.com/cate/smartphone/"


def test_parse_price():
    assert parse_price("$ \xa01,389") == 1389.0
    assert parse_price(None) is None


def test_parse_listing_page():
    products, skipped, next_url = parse_listing_page(LISTING, "smartphone", URL)
    assert skipped == 1  # the tablet
    assert next_url == "https://angkormeas.com/cate/smartphone/page/2/"
    honor, huawei = products
    assert honor["product_id"] == "angkor_meas:31389"
    assert honor["price"] == 389.0
    assert honor["specs"] == {"Price (as shown)": "$ 389", "Stock": "in stock"}
    assert huawei["price"] == 1699.0  # the sale price, not the crossed-out one
    assert huawei["specs"]["Old price"] == "$ 749"
    assert huawei["specs"]["Stock"] == "out of stock"
    assert huawei["specs"]["Condition"] == "Used"


def test_later_pages_keep_the_category_filter():
    page2 = "https://angkormeas.com/cate/smartphone/page/2/?"
    products, skipped, _ = parse_listing_page(LISTING.replace('rel="next"', ""), "smartphone", page2)
    assert (len(products), skipped) == (2, 1)


def test_last_page_has_no_next_link():
    last = LISTING.replace('class="next page-numbers"', 'class="page-numbers"')
    assert parse_listing_page(last, "smartphone", URL)[2] is None


def test_add_product_page():
    honor = parse_listing_page(LISTING, "smartphone", URL)[0][0]
    full = add_product_page(honor, PRODUCT_PAGE)
    assert full["brand"] == "Honor"
    assert full["image_url"] == "https://angkormeas.com/wp-content/uploads/honor-x80.jpg"
    assert full["features"] == [
        "Honor X80 Pro Max (China)", "256G+8G :$389", "Promotion In Box:",
        "Free Case", "Adaptor", "Color: Black,Blue, Silver",
    ]
    assert full["description"].startswith("Honor X80 Pro Max (China) | 256G+8G :$389")
    assert full["description"].endswith("Display - Size: 6.61 inches | Display - Resolution: 720 x 1604 pixels"
                                        " | Body - Weight: 207 g | Body - Other: IP64 dust tight; Drop resistant up to 1.8m")
    assert "Khmer Speaking" not in full["description"]
    assert full["specs"]["Color"] == "Black,Blue, Silver"
    assert full["specs"]["Display - Size"] == "6.61 inches"
    assert full["specs"]["Body - Other"] == "IP64 dust tight; Drop resistant up to 1.8m"
    assert full["specs"]["Price (as shown)"] == "$ 389"  # listing data kept
    assert is_valid(clean_product(full))
