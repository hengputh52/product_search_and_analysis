"""Hybrid retrieval: fuse several rankers (by default BM25 + dense) with Reciprocal Rank Fusion.

BM25 scores (0..~30) and cosine similarities (-1..1) are on different scales, so
they can't simply be added. RRF ignores the scores and uses only each product's
*rank* in each list:

    rrf_score(product) = sum over lists of  weight / (k + rank in that list)

A product ranked high by several lists wins; one found by only one list still counts.
(Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion outperforms Condorcet and
individual Rank Learning Methods", SIGIR 2009.)

Which methods are fused, and their weights, is set in config (HYBRID_METHODS, HYBRID_WEIGHTS).
"""
from collections import defaultdict

from product_search_analysis.config import HYBRID_CANDIDATES, RRF_K
from product_search_analysis.search.rankers import top_scores


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K,
                           weights: list[float] | None = None) -> list[tuple[str, float]]:
    """Fuse several ranked lists of product_ids into one list of (product_id, rrf_score)."""
    weights = weights or [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError(f"{len(rankings)} rankings but {len(weights)} weights")
    scores = defaultdict(float)
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += weight / (k + rank)
    return top_scores(scores, len(scores))


class HybridRanker:
    """Fuses any number of rankers with RRF. Takes the top `candidates` of each before fusing."""

    def __init__(self, rankers: list, candidates: int = HYBRID_CANDIDATES, k: int = RRF_K,
                 weights: list[float] | None = None):
        if weights is not None and len(weights) != len(rankers):
            raise ValueError(f"{len(rankers)} rankers but {len(weights)} weights")
        self.rankers = list(rankers)
        self.candidates = candidates
        self.k = k
        self.weights = weights

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        # at least top_k candidates, or asking for more results than candidates would cut them off
        n = max(self.candidates, top_k)
        rankings = [[doc_id for doc_id, _ in ranker.search(query, n)] for ranker in self.rankers]
        return reciprocal_rank_fusion(rankings, self.k, self.weights)[:top_k]
