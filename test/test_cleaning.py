from product_search_analysis.cleaning import deduplicate, normalize_text, parse_price


def test_normalize_text_removes_html_and_spaces():
    assert normalize_text("<p>Noise&nbsp;Cancelling\n  <b>Headphones</b></p>") == "Noise Cancelling Headphones"


def test_normalize_text_handles_none():
    assert normalize_text(None) == ""


def test_parse_price():
    assert parse_price("$1,299.00") == 1299.0
    assert parse_price("n/a") is None


def test_deduplicate_ignores_case():
    products = [{"title": "Pixel 9"}, {"title": "PIXEL 9"}, {"title": "Galaxy S25"}]
    assert [p["title"] for p in deduplicate(products)] == ["Pixel 9", "Galaxy S25"]