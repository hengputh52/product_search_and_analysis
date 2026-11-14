"""Lexical (word-matching) rankers over the inverted index: TF-IDF + cosine, and BM25.

Both reuse the positional index from index.py: for a term, `index.positions(term)`
gives {product_id: [positions]}, and the number of positions is the term frequency
(tf). So no extra index has to be built.

Every ranker (here, dense.py, hybrid.py, and any you add) follows the `Ranker` interface:
    ranker.search(query, top_k) -> [(product_id, score), ...]   best first
"""
import math
from collections import Counter, defaultdict
from typing import Protocol

from product_search_analysis.config import BM25_B, BM25_K1
from product_search_analysis.search.text import tokenize


class Ranker(Protocol):
    """What retrieve() needs from a ranking method. No base class to inherit:
    any object with this `search` method works (TfidfRanker, DenseRanker, your own...)."""

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """The top_k (product_id, score) pairs for `query`, highest score first."""
        ...


def top_scores(scores: dict, top_k: int) -> list[tuple[str, float]]:
    """Highest scores first; ties broken by product_id so results are always in the same order."""
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:top_k]


def _tf_weight(tf: int) -> float:
    """Log-scaled term frequency: a word 10 times is not 10x as important as once."""
    return 1 + math.log(tf) if tf > 0 else 0.0


class TfidfRanker:
    """Vector space model: product and query become TF-IDF vectors, ranked by cosine similarity.

        weight(term, doc) = (1 + log tf) * idf        idf = log(N / df)
        score(query, doc) = (q . d) / (|q| * |d|)     between 0 and 1
    """

    def __init__(self, index):
        self.index = index
        n_docs = len(index.docs)
        # df = number of products containing the term. A term in every product gets idf 0.
        self.idf = {term: math.log(n_docs / len(posting)) for term, posting in index.postings.items()}

        # |d| for every product, computed once (it doesn't depend on the query)
        squares = defaultdict(float)
        for term, posting in index.postings.items():
            for doc_id, positions in posting.items():
                squares[doc_id] += (_tf_weight(len(positions)) * self.idf[term]) ** 2
        self.norms = {doc_id: math.sqrt(total) for doc_id, total in squares.items()}

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        counts = Counter(t for t in tokenize(query) if t in self.idf)  # unknown words can't match
        query_vector = {t: _tf_weight(c) * self.idf[t] for t, c in counts.items()}
        query_norm = math.sqrt(sum(w * w for w in query_vector.values()))
        if query_norm == 0:
            return []

        # Only products sharing at least one term with the query can score above 0,
        # so walk the postings of the query terms instead of every product.
        dot = defaultdict(float)
        for term, query_weight in query_vector.items():
            for doc_id, positions in self.index.positions(term).items():
                dot[doc_id] += query_weight * _tf_weight(len(positions)) * self.idf[term]

        scores = {doc_id: value / (query_norm * self.norms[doc_id])
                  for doc_id, value in dot.items() if value > 0 and self.norms.get(doc_id)}
        return top_scores(scores, top_k)


class BM25Ranker:
    """Okapi BM25, the standard probabilistic ranking function.

        score(query, doc) = sum over query terms t of
            idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_length / average_length))
        idf(t) = log(1 + (N - df + 0.5) / (df + 0.5))

    Compared with TF-IDF: extra occurrences of a word add less and less (k1), and
    long product texts are penalised (b), so a short, focused title can win.
    """

    def __init__(self, index, k1: float = BM25_K1, b: float = BM25_B):
        self.index = index
        self.k1 = k1
        self.b = b
        n_docs = len(index.docs)

        # Document length = number of tokens = sum of tf over all its terms.
        self.lengths = Counter()
        for posting in index.postings.values():
            for doc_id, positions in posting.items():
                self.lengths[doc_id] += len(positions)
        self.average_length = (sum(self.lengths.values()) / n_docs) if n_docs else 1.0

        self.idf = {term: math.log(1 + (n_docs - len(posting) + 0.5) / (len(posting) + 0.5))
                    for term, posting in index.postings.items()}

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        scores = defaultdict(float)
        for term in set(tokenize(query)):            # each query word counts once
            idf = self.idf.get(term)
            if idf is None:
                continue
            for doc_id, positions in self.index.positions(term).items():
                tf = len(positions)
                length_ratio = self.lengths[doc_id] / self.average_length
                scores[doc_id] += idf * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * length_ratio))
        return top_scores(scores, top_k)
