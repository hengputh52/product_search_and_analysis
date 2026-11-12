from product_search_analysis.scraping.kaggle_amazon_in.mapper import (
    map_row,
    match_category,
    parse_inr,
    parse_rating,
    split_title,
)

ROW = {
    "product_id": "B0BBN4DZBD",
    "product_name": "Redmi A1 (Light Blue, 2GB RAM, 32GB Storage) | Segment Best AI Dual Cam | 5000mAh Battery",
    "category": "Electronics|Mobiles&Accessories|Smartphones&BasicMobiles|Smartphones",
    "discounted_price": "₹6,499",
    "actual_price": "₹8,999",
    "discount_percentage": "28%",
    "rating": "4.0",
    "rating_count": "7,807",
    "about_product": "Display: 16.56cm HD+ Scratch resistant display|Processor: MediaTek Helio A22 processor|Great value phone",
    "review_title": "Budget friendly phone.,Good for",
    "review_content": "Battery backup and screen quality are good.",
    "img_link": "https://m.media-amazon.com/images/I/41Wd9J6nfpL.jpg",
    "product_link": "https://www.amazon.in/Redmi/dp/B0BBN4DZBD/ref=sr_1_7?qid=1",
}


def test_match_category():
    assert match_category(ROW["category"]) == "smartphone"
    assert match_category("Electronics|WearableTechnology|SmartWatches") == "smartwatch"
    assert match_category("Computers&Accessories|Accessories&Peripherals|Cables&Accessories|Cables|USBCables") is None


def test_parse_values():
    assert parse_inr("₹1,099") == 1099.0
    assert parse_inr("") is None
    assert parse_rating("4.2") == 4.2
    assert parse_rating("|") is None  # the one broken rating in the dataset


def test_split_title():
    assert split_title("Redmi A1 (2GB RAM) | 5000mAh Battery | Android 12") == (
        "Redmi A1 (2GB RAM)", ["5000mAh Battery", "Android 12"]
    )


def test_map_row():
    p = map_row(ROW, "smartphone")
    assert p["product_id"] == "amazon_in:B0BBN4DZBD"
    assert p["title"] == "Redmi A1 (Light Blue, 2GB RAM, 32GB Storage)"
    assert p["brand"] == "Redmi"
    assert p["price"] == round(6499 / 82.8, 2)  # converted to USD
    assert p["specs"]["Price (INR)"] == "₹6,499"
    assert p["specs"]["Processor"] == "MediaTek Helio A22 processor"  # "Key: value" bullet -> spec
    assert p["rating"] == 4.0
    assert p["source_url"] == "https://www.amazon.in/dp/B0BBN4DZBD"
    assert "5000mAh Battery" in p["features"]
