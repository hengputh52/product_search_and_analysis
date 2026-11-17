"""Try Boolean search: edit the settings below, then run this file (VS Code ▶ or `python run_search.py`).

Exact matching; results come in product-id order (not ranked). Query syntax:
    AND  OR  NOT  "exact phrase"  ( )      e.g.  (speaker OR headphones) AND bluetooth NOT sony
    Words next to each other are ANDed:  bluetooth speaker  ==  bluetooth AND speaker
For ranked results (best first), use run_ranking.py.
"""

# ---------- settings ----------
QUERIES = [
    "bluetooth speaker",
    # '"power bank" NOT case',
    # "(earbuds OR headphones) AND noise",
]
MAX_RESULTS = 10        # results shown per query
REBUILD_INDEX = False   # True = rebuild from the database first (do this after scraping new products)
# -------------------------------

from product_search_analysis import db
from product_search_analysis.config import EMBEDDINGS_FILE, INDEX_FILE
from product_search_analysis.search import index as index_module
from product_search_analysis.search import search_boolean


def get_index(rebuild: bool = False):
    """Load the saved index; build it from the database first if asked or if it doesn't exist."""
    if rebuild or not INDEX_FILE.exists():
        print("Building the index from the database (about 20 seconds)...")
        with db.connect() as conn:
            index = index_module.build_index(conn)
        index_module.save_index(index)
        print(f"Indexed {len(index.docs)} products -> {INDEX_FILE}\n")
        if EMBEDDINGS_FILE.exists():
            print("Note: rebuild the embeddings too, so dense/hybrid ranking see the same products:\n"
                  "  python -m product_search_analysis.ranking.dense\n")
        return index
    return index_module.load_index()


def main():
    index = get_index(REBUILD_INDEX)
    for query in QUERIES:
        print(f"Query: {query}")
        try:
            results = search_boolean(query, index)
        except ValueError as error:
            print(f"  invalid query: {error}\n")
            continue
        print(f"  {len(results)} matches (not ranked)")
        for r in results[:MAX_RESULTS]:
            print(f"  {r['product_id']:<28} [{r.get('category')}] {r['title'][:65]}")
        if len(results) > MAX_RESULTS:
            print(f"  ... and {len(results) - MAX_RESULTS} more")
        print()


if __name__ == "__main__":
    main()
