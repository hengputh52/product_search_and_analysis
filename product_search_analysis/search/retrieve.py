"""One entry point for ranked retrieval: retrieve(query, method, top_k).

    from product_search_analysis.search import retrieve
    retrieve("wireless earbuds for running", method="hybrid", top_k=5)
    -> [{"rank": 1, "score": 0.0325, "product_id": "angkor_meas:...", "title": ...,
         "brand": ..., "category": ..., "price": ..., ...config.SEARCH_RESULT_FIELDS}, ...]

Built-in methods:
    "tfidf"   TF-IDF vectors + cosine similarity          (rankers.py)
    "bm25"    Okapi BM25                                   (rankers.py)
    "dense"   sentence-transformers embeddings             (dense.py)
    "hybrid"  config.HYBRID_METHODS fused with RRF         (hybrid.py)   <- default

Adding a method: write a class with `search(query, top_k) -> [(product_id, score)]`
(see rankers.Ranker) and register a builder for it; nothing else needs changing:

    register_method("title_bm25", lambda retriever: MyRanker(retriever.index))

retrieve(), the command line below and the benchmark then all accept "title_bm25".
A builder gets the Retriever, so it can reuse other methods: retriever.ranker("bm25").

Needs the saved index (python -m product_search_analysis.search.index) and, for
"dense"/"hybrid", the saved embeddings (python -m product_search_analysis.search.dense).

Try it from the command line:
    python -m product_search_analysis.search.retrieve "bluetooth speaker" --method bm25 --top-k 5
"""
import argparse
import logging
from typing import Callable

from product_search_analysis.config import DEFAULT_TOP_K, HYBRID_METHODS, HYBRID_WEIGHTS
from product_search_analysis.search.dense import load_dense_ranker
from product_search_analysis.search.hybrid import HybridRanker
from product_search_analysis.search.index import load_index
from product_search_analysis.search.rankers import BM25Ranker, Ranker, TfidfRanker

log = logging.getLogger(__name__)

DEFAULT_METHOD = "hybrid"

# method name -> builder(retriever) -> Ranker. Builders run once, on first use of the method.
_BUILDERS: dict[str, Callable[["Retriever"], Ranker]] = {}


def register_method(name: str, builder: Callable[["Retriever"], Ranker], replace: bool = False) -> None:
    """Make a new ranking method available to retrieve(). `replace=True` to override one."""
    if name in _BUILDERS and not replace:
        raise ValueError(f"Method {name!r} already exists; pass replace=True to override it")
    _BUILDERS[name] = builder


def available_methods() -> list[str]:
    """Names of every registered method, built-in ones first."""
    return list(_BUILDERS)


class Retriever:
    """Holds the index and builds each ranker the first time it is used.

    The dense model is only loaded when a method that needs it is asked for, so
    TF-IDF / BM25 work without sentence-transformers. `rankers` pre-fills rankers
    by method name, e.g. Retriever(index, rankers={"dense": fake}) in tests.
    """

    def __init__(self, index, rankers: dict[str, Ranker] | None = None):
        self.index = index
        self._rankers: dict[str, Ranker] = dict(rankers or {})

    def ranker(self, method: str) -> Ranker:
        if method not in self._rankers:
            if method not in _BUILDERS:
                raise ValueError(f"Unknown method {method!r}; choose one of {', '.join(available_methods())}")
            self._rankers[method] = _BUILDERS[method](self)
        return self._rankers[method]

    def load_dense(self) -> Ranker:
        dense = load_dense_ranker()
        differ = len(set(self.index.docs) ^ set(dense.ids))
        if differ:
            log.warning("Index and embeddings differ by %d products; rebuild both "
                        "(search.index and search.dense) after collecting new data.", differ)
        return dense

    def retrieve(self, query: str, method: str = DEFAULT_METHOD, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        """Ranked products for `query`, best first. Blank query -> []."""
        ranker = self.ranker(method)          # check the method name even for a blank query
        if not (query or "").strip() or top_k <= 0:
            return []
        return [
            {"rank": rank, "score": score, "product_id": doc_id, **self.index.docs.get(doc_id, {})}
            for rank, (doc_id, score) in enumerate(ranker.search(query, top_k), start=1)
        ]


# ---------- built-in methods ----------

register_method("tfidf", lambda retriever: TfidfRanker(retriever.index))
register_method("bm25", lambda retriever: BM25Ranker(retriever.index))
register_method("dense", lambda retriever: retriever.load_dense())
register_method("hybrid", lambda retriever: HybridRanker(
    [retriever.ranker(method) for method in HYBRID_METHODS], weights=HYBRID_WEIGHTS))


# ---------- shared default retriever ----------

_default: Retriever | None = None


def get_retriever() -> Retriever:
    """The shared Retriever over the saved index, created on first use."""
    global _default
    if _default is None:
        _default = Retriever(load_index())
    return _default


def retrieve(query: str, method: str = DEFAULT_METHOD, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Hand-off function: return the top_k products for `query`, ranked by `method`."""
    return get_retriever().retrieve(query, method, top_k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search products with a ranked retrieval method.")
    parser.add_argument("query")
    parser.add_argument("--method", choices=available_methods(), default=DEFAULT_METHOD)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    for r in retrieve(args.query, args.method, args.top_k):
        price = f"${r['price']:,.2f}" if r.get("price") is not None else "no price"
        print(f"{r['rank']:>3}. {r['score']:.4f}  [{r.get('category')}] {r.get('title')}  ({price}, {r['product_id']})")


if __name__ == "__main__":
    main()
