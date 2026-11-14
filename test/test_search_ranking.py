"""Tests for TF-IDF, BM25, dense, hybrid (RRF), retrieve() and the benchmark metrics.

Everything runs on a tiny in-memory index; the dense model is replaced by a fake
encoder, so no database, network or sentence-transformers download is needed.
"""
import numpy as np
import pytest

from product_search_analysis.config import CATEGORIES
from product_search_analysis.search.benchmark import (
    is_relevant, load_queries, ndcg_at, precision_at, reciprocal_rank, run_benchmark,
)
from product_search_analysis.search.dense import DenseRanker, product_text
from product_search_analysis.search.hybrid import HybridRanker, reciprocal_rank_fusion
from product_search_analysis.search.index import Index
from product_search_analysis.search.rankers import BM25Ranker, TfidfRanker
from product_search_analysis.search.retrieve import _BUILDERS, Retriever, available_methods, register_method
from product_search_analysis.search.text import tokenize


def make_index() -> Index:
    idx = Index()
    idx.add("p1", "JBL Bluetooth Speaker", "portable waterproof speaker", [], category="speaker")
    idx.add("p2", "Sony Headphones", "wireless bluetooth headphones", [], category="headphones")
    idx.add("p3", "Anker Power Bank", "20000mah portable charger", ["fast charging"], category="powerbank")
    idx.add("p4", "Samsung Galaxy Phone", "android smartphone with a big battery", [], category="smartphone")
    return idx


def ids(hits) -> list[str]:
    return [doc_id for doc_id, _ in hits]


# A fake "model": 2-D vectors by hand. Axis 0 = audio, axis 1 = charging.
FAKE_VECTORS = {"p1": [1.0, 0.0], "p2": [0.8, 0.6], "p3": [0.0, 1.0], "p4": [0.6, 0.8]}


def fake_dense() -> DenseRanker:
    def encode_query(query):
        return np.array([1.0, 0.0]) if "music" in query else np.array([0.0, 1.0])
    doc_ids = sorted(FAKE_VECTORS)
    return DenseRanker(doc_ids, np.array([FAKE_VECTORS[d] for d in doc_ids]), encode_query)


# ---------- TF-IDF ----------

def test_tfidf_finds_matching_product_first():
    assert ids(TfidfRanker(make_index()).search("speaker", 10)) == ["p1"]


def test_tfidf_scores_are_cosine_between_0_and_1():
    for _, score in TfidfRanker(make_index()).search("bluetooth portable", 10):
        assert 0 < score <= 1


def test_tfidf_identical_text_has_cosine_1():
    idx = Index()
    idx.add("a", "bluetooth speaker", "", [])
    idx.add("b", "power bank", "", [])
    [(doc_id, score)] = TfidfRanker(idx).search("bluetooth speaker", 10)
    assert doc_id == "a" and score == pytest.approx(1.0)


def test_tfidf_unknown_or_stop_words_return_nothing():
    ranker = TfidfRanker(make_index())
    assert ranker.search("xyzzy", 10) == []
    assert ranker.search("the and", 10) == []


# ---------- BM25 ----------

def test_bm25_ranks_more_query_terms_higher():
    # p1 has both "bluetooth" and "speaker"; p2 only "bluetooth"
    assert ids(BM25Ranker(make_index()).search("bluetooth speaker", 10)) == ["p1", "p2"]


def test_bm25_prefers_shorter_document_with_same_tf():
    idx = Index()
    idx.add("short", "speaker", "", [])
    idx.add("long", "speaker", "with many other words about colours sizes and boxes", [])
    assert ids(BM25Ranker(idx).search("speaker", 10)) == ["short", "long"]


def test_bm25_rare_term_counts_more_than_common_term():
    # "bluetooth" is in 2 products, "waterproof" only in p1 -> higher idf
    ranker = BM25Ranker(make_index())
    assert ranker.idf["waterproof"] > ranker.idf["bluetooth"]


def test_bm25_respects_top_k():
    assert len(BM25Ranker(make_index()).search("bluetooth portable", 1)) == 1


# ---------- dense ----------

def test_dense_ranks_by_cosine_similarity():
    assert ids(fake_dense().search("music", 2)) == ["p1", "p2"]
    assert ids(fake_dense().search("charge", 2)) == ["p3", "p4"]


def test_product_text_joins_title_description_features():
    assert product_text("Anker", "power bank", ["fast", " "]) == "Anker. power bank. fast"


# ---------- hybrid / RRF ----------

def test_rrf_rewards_documents_ranked_by_both_lists():
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60)
    assert ids(fused) == ["b", "a", "c"]
    assert dict(fused)["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_hybrid_combines_bm25_and_dense():
    idx = make_index()
    hybrid = HybridRanker([BM25Ranker(idx), fake_dense()], candidates=10)
    # BM25 alone finds only p1 ("music" is in no product text); dense adds every other product
    result = ids(hybrid.search("speaker music", 10))
    assert result[0] == "p1"
    assert set(result) == {"p1", "p2", "p3", "p4"}


def test_rrf_weights_let_one_list_count_more():
    # equal weights: "a" (rank 1 in list 1) ties "c" (rank 1 in list 2) -> id order
    assert ids(reciprocal_rank_fusion([["a"], ["c"]]))[0] == "a"
    # list 2 weighted double -> "c" first
    assert ids(reciprocal_rank_fusion([["a"], ["c"]], weights=[1.0, 2.0]))[0] == "c"


def test_hybrid_can_fuse_any_number_of_rankers():
    idx = make_index()
    hybrid = HybridRanker([TfidfRanker(idx), BM25Ranker(idx), fake_dense()], candidates=10)
    assert ids(hybrid.search("speaker music", 1)) == ["p1"]


def test_weights_must_match_rankers():
    with pytest.raises(ValueError):
        HybridRanker([fake_dense()], weights=[1.0, 2.0])


# ---------- retrieve() ----------

def make_retriever() -> Retriever:
    return Retriever(make_index(), rankers={"dense": fake_dense()})


def test_retrieve_returns_ranked_products_with_metadata():
    retriever = make_retriever()
    for method in ("tfidf", "bm25", "dense", "hybrid"):
        results = retriever.retrieve("bluetooth speaker music", method=method, top_k=2)
        assert [r["rank"] for r in results] == [1, 2]
        assert results[0]["product_id"] == "p1"
        assert results[0]["category"] == "speaker" and results[0]["title"] == "JBL Bluetooth Speaker"
        assert results[0]["score"] >= results[1]["score"]


def test_retrieve_blank_query_returns_nothing():
    assert Retriever(make_index()).retrieve("   ", method="bm25") == []


def test_retrieve_unknown_method_raises():
    with pytest.raises(ValueError):
        Retriever(make_index()).retrieve("speaker", method="pagerank")


class CheapestFirst:
    """An example add-on ranker: products containing the query word, cheapest first."""

    def __init__(self, index):
        self.index = index

    def search(self, query, top_k):
        hits = {d for t in tokenize(query) for d in self.index.positions(t)}
        priced = sorted(hits, key=lambda d: self.index.docs[d].get("price") or 0)
        return [(d, 1.0 / (rank + 1)) for rank, d in enumerate(priced)][:top_k]


def test_register_method_adds_a_new_method_to_retrieve():
    register_method("cheapest", lambda retriever: CheapestFirst(retriever.index))
    try:
        assert "cheapest" in available_methods()
        idx = Index()
        idx.add("a", "speaker big", "", [], price=90.0)
        idx.add("b", "speaker small", "", [], price=20.0)
        assert [r["product_id"] for r in Retriever(idx).retrieve("speaker", "cheapest")] == ["b", "a"]
    finally:
        _BUILDERS.pop("cheapest")          # keep the registry clean for other tests


def test_register_method_refuses_to_overwrite_by_accident():
    with pytest.raises(ValueError):
        register_method("bm25", lambda retriever: None)


# ---------- benchmark metrics ----------

def test_is_relevant_checks_category_and_title_words():
    judgment = {"categories": ["speaker"], "title_words": ["jbl"]}
    assert is_relevant({"category": "speaker", "title": "JBL Flip 6"}, judgment)
    assert not is_relevant({"category": "speaker", "title": "Sony SRS"}, judgment)
    assert not is_relevant({"category": "tv", "title": "JBL soundbar"}, judgment)


def test_precision_and_reciprocal_rank():
    relevant = [False, True, True, False]
    assert precision_at(relevant, 4) == 0.5
    assert precision_at(relevant, 10) == 0.2       # missing results count as not relevant
    assert reciprocal_rank(relevant) == 0.5
    assert reciprocal_rank([False, False]) == 0.0


def test_ndcg_is_1_for_perfect_order_and_lower_otherwise():
    assert ndcg_at([True, True, False], 3, total_relevant=2) == pytest.approx(1.0)
    assert ndcg_at([False, True, True], 3, total_relevant=2) < 1.0
    assert ndcg_at([False, False], 2, total_relevant=0) == 0.0


def test_shipped_benchmark_queries_are_valid():
    queries = load_queries()                       # raises if a query lacks query/categories
    assert len(queries) >= 20
    known = set(CATEGORIES)
    for q in queries:
        assert set(q["categories"]) <= known, q    # a typo in a category would make it never relevant


def test_run_benchmark_reports_every_method_metric_and_group():
    queries = [{"query": "speaker", "categories": ["speaker"], "group": "keyword"},
               {"query": "music", "categories": ["speaker", "headphones"], "group": "natural_language"}]
    result = run_benchmark(make_retriever(), queries, ["bm25", "dense"], k=2)
    assert set(result["summary"]) == {"bm25", "dense"}
    assert set(result["summary"]["bm25"]) == {"P@5", "P@2", "MRR", "nDCG@2", "ms/query"}
    assert set(result["by_group"]) == {"keyword", "natural_language"}
    rr = {(r["method"], r["query"]): r["MRR"] for r in result["per_query"]}
    # bm25 matches the word "speaker" but knows no "music"; the fake dense model is the opposite
    assert rr == {("bm25", "speaker"): 1.0, ("bm25", "music"): 0.0,
                  ("dense", "speaker"): 0.0, ("dense", "music"): 1.0}
    assert result["summary"]["bm25"]["MRR"] == 0.5
