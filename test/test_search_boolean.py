from product_search_analysis.search import search_boolean
from product_search_analysis.search.index import Index


def make_index() -> Index:
    """A tiny in-memory index (no database) so the parser tests run fast and offline."""
    idx = Index()
    idx.add("p1", "JBL Bluetooth Speaker", "portable waterproof speaker", [])
    idx.add("p2", "Sony Headphones", "wireless bluetooth headphones", [])
    idx.add("p3", "Anker Power Bank", "20000mah portable charger", ["fast charging"])
    return idx


def ids(results) -> list[str]:
    return sorted(r["product_id"] for r in results)


def test_single_term():
    assert ids(search_boolean("speaker", make_index())) == ["p1"]


def test_stemmed_query_matches_document():
    # "speakers" stems to "speaker" and still finds p1
    assert ids(search_boolean("speakers", make_index())) == ["p1"]


def test_and():
    assert ids(search_boolean("bluetooth AND speaker", make_index())) == ["p1"]


def test_implicit_and():
    # adjacent terms are ANDed, so this equals "bluetooth AND speaker"
    assert ids(search_boolean("bluetooth speaker", make_index())) == ["p1"]


def test_or():
    assert ids(search_boolean("speaker OR headphones", make_index())) == ["p1", "p2"]


def test_not():
    # bluetooth (p1, p2) AND NOT speaker (p1) -> p2
    assert ids(search_boolean("bluetooth NOT speaker", make_index())) == ["p2"]


def test_or_binds_looser_than_and():
    # speaker OR (bluetooth AND headphones) -> p1, p2
    assert ids(search_boolean("speaker OR bluetooth AND headphones", make_index())) == ["p1", "p2"]


def test_parentheses_override_precedence():
    # (speaker OR headphones) AND bluetooth -> p1, p2
    assert ids(search_boolean("(speaker OR headphones) AND bluetooth", make_index())) == ["p1", "p2"]


def test_phrase_matches_adjacent_words():
    assert ids(search_boolean('"portable waterproof"', make_index())) == ["p1"]


def test_phrase_requires_adjacency():
    # p1 has "portable ... speaker" but not "portable speaker" adjacent
    assert ids(search_boolean('"portable speaker"', make_index())) == []


def test_empty_query_returns_nothing():
    assert search_boolean("", make_index()) == []
