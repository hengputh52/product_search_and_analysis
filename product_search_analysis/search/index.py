"""Inverted index over product title + description + features.

Documents come from the PostgreSQL database (same source as export.py); each
product is one document keyed by its product_id. The index stores, for every
term, which products contain it and at which positions - the positions are what
make phrase queries ("bluetooth speaker") possible.

Build it and save it to disk:
    python -m product_search_analysis.search.index
Then query it from code:
    from product_search_analysis.search import search_boolean
"""
import pickle
from decimal import Decimal

from product_search_analysis import db
from product_search_analysis.config import INDEX_FILE, SEARCH_RESULT_FIELDS
from product_search_analysis.search.text import tokenize

# The text that is searched. Dense retrieval embeds the same fields (dense.product_text).
SEARCHED_FIELDS = ["title", "description", "features"]


def _document_tokens(title, description, features) -> list[str]:
    """One token stream per product: title, then description, then each feature."""
    tokens = tokenize(title) + tokenize(description)
    for feature in features or []:
        tokens += tokenize(feature)
    return tokens


class Index:
    """An inverted index you can query.

    postings: term -> {product_id: [position, ...]}   (positions enable phrase search;
              the number of positions is also the term frequency used by TF-IDF and BM25)
    docs:     product_id -> {"title", "source_url", ...config.SEARCH_RESULT_FIELDS}
              (only to show results; this text is not searched)
    """

    def __init__(self):
        self.postings: dict[str, dict[str, list[int]]] = {}
        self.docs: dict[str, dict] = {}

    def add(self, product_id, title, description, features, source_url=None, **info) -> None:
        """Index one product. `info` = extra fields to show with results (brand, category, ...)."""
        self.docs[product_id] = {"title": title, "source_url": source_url, **info}
        for position, term in enumerate(_document_tokens(title, description, features)):
            self.postings.setdefault(term, {}).setdefault(product_id, []).append(position)

    @property
    def doc_ids(self) -> set:
        """Every product_id in the index (needed to evaluate NOT)."""
        return set(self.docs)

    def positions(self, term) -> dict:
        """product_id -> [positions] for one already-stemmed term ({} if absent)."""
        return self.postings.get(term, {})


def _plain(value):
    """PostgreSQL NUMERIC comes back as Decimal; plain floats are easier to use and print."""
    return float(value) if isinstance(value, Decimal) else value


def fields_sql() -> str:
    """SELECT the searched fields + the result fields (each column once)."""
    columns = dict.fromkeys(["product_id", *SEARCHED_FIELDS, *SEARCH_RESULT_FIELDS])
    return f"SELECT {', '.join(columns)} FROM products"


def build_index(conn) -> Index:
    """Read every product from the database and build the inverted index."""
    index = Index()
    cursor = conn.execute(fields_sql())
    names = [column.name for column in cursor.description]
    for values in cursor:
        row = dict(zip(names, values))
        info = {field: _plain(row[field]) for field in SEARCH_RESULT_FIELDS if field != "title"}
        index.add(row["product_id"], row["title"], row["description"], row["features"], **info)
    return index


def save_index(index: Index, path=INDEX_FILE) -> None:
    """Write the index to disk (pickle: fast to reload, keeps sets/dicts as-is)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(index, f)


_cached: Index | None = None


def load_index(path=INDEX_FILE) -> Index:
    """Load the index from disk once and reuse it on later calls."""
    global _cached
    if _cached is None:
        if not path.exists():
            raise FileNotFoundError(
                f"No index at {path}. Build it first: "
                "python -m product_search_analysis.search.index"
            )
        with open(path, "rb") as f:
            _cached = pickle.load(f)
    return _cached


def main() -> None:
    # Import the module under its real name and build through it, so the pickled
    # Index class is 'product_search_analysis.search.index.Index' and not '__main__.Index'
    # (python -m runs this file as __main__, a second copy of this module).
    from product_search_analysis.search import index as index_module

    with db.connect() as conn:
        index = index_module.build_index(conn)
    index_module.save_index(index)
    print(f"Indexed {len(index.docs)} products, {len(index.postings)} unique terms "
          f"-> {INDEX_FILE}")


if __name__ == "__main__":
    main()
