from product_search_analysis.search.text import tokenize


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Bluetooth SPEAKER!!!") == ["bluetooth", "speaker"]


def test_tokenize_removes_stop_words():
    # "the" and "and" are stop-words and should be dropped
    assert tokenize("the speaker and the bass") == ["speaker", "bass"]


def test_tokenize_stems_plural_to_singular():
    # a search for "speakers" and a product saying "speaker" must share a token
    assert tokenize("speakers") == tokenize("speaker")


def test_tokenize_keeps_digits():
    assert tokenize("20000mAh power bank") == ["20000mah", "power", "bank"]


def test_tokenize_strips_html():
    assert tokenize("<b>Waterproof</b> speaker") == ["waterproof", "speaker"]


def test_tokenize_handles_none_and_empty():
    assert tokenize(None) == []
    assert tokenize("") == []
