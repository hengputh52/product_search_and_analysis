"""Dense (semantic) retrieval with sentence-transformers.

Every product's text is turned into one vector (an "embedding") by a pretrained
model; a query is turned into a vector the same way, and products are ranked by
cosine similarity. Unlike TF-IDF/BM25 this can match meaning without shared words:
"something to listen to music while running" can find "wireless sport earbuds".

Build the embeddings from the database and save them to disk (takes a few minutes on CPU,
downloads the model on the first run):
    python -m product_search_analysis.search.dense
"""
import logging

import numpy as np

from product_search_analysis import db
from product_search_analysis.config import (
    DENSE_BATCH_SIZE,
    DENSE_DOCUMENT_PREFIX,
    DENSE_MODEL_NAME,
    DENSE_QUERY_PREFIX,
    EMBEDDINGS_FILE,
)

log = logging.getLogger(__name__)

TEXT_SQL = "SELECT product_id, title, description, features FROM products ORDER BY product_id"


def product_text(title, description, features) -> str:
    """The text a product is embedded from: the same fields the inverted index uses.
    The title comes first because the model only reads the first ~256 tokens."""
    parts = [title or "", description or "", *(features or [])]
    return ". ".join(p.strip() for p in parts if p and p.strip())


def load_model():
    """Load the sentence-transformers model (imported here: torch is slow to import)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(DENSE_MODEL_NAME)


def encode(model, texts: list[str], show_progress: bool = False) -> np.ndarray:
    """Texts -> unit-length float32 vectors, so cosine similarity is a plain dot product."""
    vectors = model.encode(texts, batch_size=DENSE_BATCH_SIZE, show_progress_bar=show_progress,
                           normalize_embeddings=True, convert_to_numpy=True)
    return vectors.astype(np.float32)


class DenseRanker:
    """Ranks products by cosine similarity between their embedding and the query's.

    ids:          product_ids, one per row of `vectors`
    vectors:      (n_products, dim) array of unit-length embeddings
    encode_query: function text -> unit-length vector (the model; a fake one in tests)
    """

    def __init__(self, ids: list[str], vectors: np.ndarray, encode_query):
        self.ids = list(ids)
        self.vectors = vectors
        self.encode_query = encode_query

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        if not self.ids:
            return []
        scores = self.vectors @ self.encode_query(query)   # cosine similarity with every product
        # stable sort on -score: equal scores keep product_id order (ids are saved sorted)
        best = np.argsort(-scores, kind="stable")[:top_k]
        return [(self.ids[i], float(scores[i])) for i in best]


def build_embeddings(conn, model) -> tuple[list[str], np.ndarray]:
    """Read every product from the database and embed it."""
    rows = conn.execute(TEXT_SQL).fetchall()
    ids = [row[0] for row in rows]
    texts = [DENSE_DOCUMENT_PREFIX + product_text(title, description, features)
             for _, title, description, features in rows]
    return ids, encode(model, texts, show_progress=True)


def save_embeddings(ids: list[str], vectors: np.ndarray, path=EMBEDDINGS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # the model name is saved too: vectors from different models can't be compared
    np.savez(path, ids=np.array(ids), vectors=vectors, model=np.array(DENSE_MODEL_NAME))


def load_dense_ranker(path=EMBEDDINGS_FILE, model=None) -> DenseRanker:
    """Load saved embeddings + the model that encodes queries."""
    if not path.exists():
        raise FileNotFoundError(
            f"No embeddings at {path}. Build them first: "
            "python -m product_search_analysis.search.dense"
        )
    data = np.load(path)                    # only plain arrays inside, no pickle needed
    saved_model = str(data["model"])
    if saved_model != DENSE_MODEL_NAME:
        raise ValueError(f"{path} was built with {saved_model}, but config.DENSE_MODEL_NAME is "
                         f"{DENSE_MODEL_NAME}. Rebuild: python -m product_search_analysis.search.dense")
    model = model or load_model()
    return DenseRanker([str(i) for i in data["ids"]], data["vectors"],
                       lambda query: encode(model, [DENSE_QUERY_PREFIX + query])[0])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # hide one log line per model-file request
    model = load_model()
    with db.connect() as conn:
        ids, vectors = build_embeddings(conn, model)
    save_embeddings(ids, vectors)
    print(f"Embedded {len(ids)} products with {DENSE_MODEL_NAME} "
          f"({vectors.shape[1]} dimensions) -> {EMBEDDINGS_FILE}")


if __name__ == "__main__":
    main()
