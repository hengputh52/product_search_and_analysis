from product_search_analysis.cleaning import clean_product, is_valid
from product_search_analysis.scraping.ptc_computer.ptc_computer import parse_listing_page, parse_price

# Trimmed copy of a real listing page: two product cards and the pagination.
CARD = """
<div class="col-lg-4 col-md-4 col-6 mb-4">
 <div class="p-3 bg-white rounded shadow-md h-100 product-card d-flex flex-column justify-content-between">
  <div class="aiz-card-box mt-1 mb-2 has-transition bg-white">
   <a href="https://ptc-computer.com.kh/brand/{brand_slug}" target="_blank"><div><img src="logo.png"></div></a>
   <div class="position-relative">
    <div class="product_gallery" id="productGallery">
     <a class="d-block" href="https://ptc-computer.com.kh/product/{slug}">
      <img class="img-fit lazyload" data-src="https://s3.example.com/{number}.png"
           src="https://ptc-computer.com.kh/public/assets/img/placeholder.jpg"></a>
    </div>
    <div class="absolute-top-right aiz-p-hov-icon">
     <a href="javascript:void(0)" onclick="addToCompare({number})"><i class="las la-sync"></i></a>
    </div>
   </div>
   <div class="text-left">
    <span class="fs-12 fw-600" onclick="enableCopy(this, `{sku}`)">{sku}</span>
    <div class="rating rating-sm my-1"><i class="las la-star"></i><i class="las la-star"></i></div>
    <span class="fw-600 fs-12 text-capitalize pl-1">in stock</span>
    <h3 class="fw-500 fs-13"><a class="d-block text-reset" href="https://ptc-computer.com.kh/product/{slug}">{title}</a></h3>
    <h3 class="d-none d-lg-block"><a class="d-block text-reset" href="https://ptc-computer.com.kh/product/{slug}"
        id="product_sort_description"><p>----------------------------<br>
      - CPU: Intel® Core™ Ultra 7 256V<br>
      - OS: <b>Win 11 Home<br></b>
      - <b>Keyboard Backlight + Fingerprint</b><br>
      - RAM: 16GB LPDDR5X on board</p></a></h3>
   </div>
  </div>
  <div><div class="fs-13">{old}<span class="fw-600" style="font-size:18px;">{price}</span></div></div>
 </div>
</div>
"""
PAGE = (
    "<div class='row'>"
    + CARD.format(brand_slug="dell-laptop-desktop-cambodia", slug="dell-16-plus-oqf81", number=3504,
                  sku="LDJ-1835", title="Dell 16 Plus DB16250 Ice Blue - Ultra 7 256V", old="", price="$1,889")
    + CARD.format(brand_slug="asus-laptop-desktop-cambodia", slug="asus-vivobook-go-15-x1", number=4081,
                  sku="LAS-1001", title="ASUS Vivobook Go 15 E1504FA", old="<del>$709</del>", price="$559")
    + "</div>"
    + '<ul class="pagination"><li class="page-item active"><span class="page-link">1</span></li>'
      '<li class="page-item"><a class="page-link" href="https://ptc-computer.com.kh/parent_category/computer?page=2" '
      'rel="next">›</a></li></ul>'
)
URL = "https://ptc-computer.com.kh/parent_category/computer"


def test_parse_price():
    assert parse_price("$1,889") == 1889.0
    assert parse_price("") is None


def test_parse_listing_page():
    products, next_url = parse_listing_page(PAGE, "computer", URL)
    assert next_url == "https://ptc-computer.com.kh/parent_category/computer?page=2"
    assert [p["product_id"] for p in products] == ["ptc_computer:3504", "ptc_computer:4081"]

    dell, asus = products
    assert dell["title"] == "Dell 16 Plus DB16250 Ice Blue - Ultra 7 256V"
    assert dell["brand"] == "Dell"
    assert asus["brand"] == "ASUS"  # spelled as in the title
    assert dell["price"] == 1889.0
    assert asus["price"] == 559.0
    assert asus["specs"]["Old price"] == "$709"
    assert dell["image_url"] == "https://s3.example.com/3504.png"  # not the lazy-load placeholder
    assert dell["source_url"] == "https://ptc-computer.com.kh/product/dell-16-plus-oqf81"
    assert dell["rating"] is None
    assert dell["features"] == [
        "CPU: Intel® Core™ Ultra 7 256V",
        "OS: Win 11 Home",
        "Keyboard Backlight + Fingerprint",
        "RAM: 16GB LPDDR5X on board",
    ]
    assert dell["specs"]["CPU"] == "Intel® Core™ Ultra 7 256V"
    assert dell["specs"]["SKU"] == "LDJ-1835"
    assert dell["specs"]["Stock"] == "in stock"
    assert all(is_valid(clean_product(p)) for p in products)


def test_last_page_has_no_next_link():
    last = PAGE.replace('rel="next"', "")
    assert parse_listing_page(last, "computer", URL)[1] is None
