"""Try ranked retrieval: edit the settings below, then run this file (VS Code ▶ or `python run_ranking.py`).

Results come best first, with a score. Queries are plain text (no AND/OR/NOT; for those use run_search.py).
METHOD = "tfidf" / "bm25"   ranked by matching words.
METHOD = "dense" / "hybrid" ranked by meaning (sentence embeddings), so natural questions work,
    e.g. "something to listen to music while running". "hybrid" fuses bm25 + dense. One-time setup:
        pip install sentence-transformers
        python -m product_search_analysis.ranking.dense
METHOD = "compare"          runs tfidf and bm25 (+ dense and hybrid if set up) side by side per query.
"""

# ---------- settings ----------
QUERIES = [
    "iphone 17",
    # "wireless earbuds for running",
    # "portable battery to charge my phone when traveling",
]
METHOD = "tfidf"         # "tfidf" | "bm25" | "dense" | "hybrid" | "compare"
MAX_RESULTS = 10        # results shown per query
REBUILD_INDEX = False   # True = rebuild from the database first (do this after scraping new products)
# -------------------------------

from product_search_analysis.config import EMBEDDINGS_FILE
from product_search_analysis.ranking.retrieve import Retriever
from run_search import get_index

METHODS = ["tfidf", "bm25", "dense", "hybrid"]
NEEDS_EMBEDDINGS = {"dense", "hybrid"}
DENSE_SETUP = ("need a one-time setup:\n"
               "    pip install sentence-transformers\n"
               "    python -m product_search_analysis.ranking.dense")


def dense_ready() -> bool:
    """dense/hybrid need the sentence-transformers package and the saved embeddings."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return EMBEDDINGS_FILE.exists()


def show(query, retriever, method):
    print(f"  {method}:")
    for r in retriever.retrieve(query, method, MAX_RESULTS):
        price = f"${r['price']:,.2f}" if r.get("price") is not None else "no price"
        print(f"  {r['rank']:>3}. {r['score']:8.4f}  [{r.get('category')}] {r['title'][:60]}  ({price})")


def main():
    if METHOD not in ["compare", *METHODS]:
        raise SystemExit(f"METHOD must be one of {', '.join(METHODS)}, compare (got {METHOD!r})")
    if METHOD in NEEDS_EMBEDDINGS and not dense_ready():
        raise SystemExit(f"dense and hybrid {DENSE_SETUP}\nOr use METHOD = \"bm25\" meanwhile.")

    retriever = Retriever(get_index(REBUILD_INDEX))
    methods = [METHOD]
    if METHOD == "compare":
        methods = [m for m in METHODS if m not in NEEDS_EMBEDDINGS or dense_ready()]
        if len(methods) < len(METHODS):
            print(f"(dense and hybrid skipped: they {DENSE_SETUP})\n")

    for query in QUERIES:
        print(f"Query: {query}")
        for method in methods:
            show(query, retriever, method)
        print()


if __name__ == "__main__":
    main()
