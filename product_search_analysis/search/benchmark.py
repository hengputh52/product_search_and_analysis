"""Benchmark every registered retrieval method on the same queries.

Queries live in benchmark_queries.json (config.BENCHMARK_QUERIES_FILE), one object each:
    {"query": "jbl speaker",                      the search text
     "categories": ["speaker", "audio"],           result categories that count as relevant
     "title_words": ["jbl"],                       optional: words the title must also contain
     "group": "brand",                             optional: averaged separately in the report
     "note": "..."}                                optional: why the judgment looks like this
Add a query by adding an object; no code change needed.

We have no hand-labelled relevance judgments, so relevance is approximated
automatically from the shop's category (+ title words). Categories are noisy and
are NOT part of the indexed text, so the check is fair to every method but only
approximate: compare methods with each other, don't read the numbers as exact quality.

Metrics (k = --top-k, default 10), defined in METRICS below; add one with one line:
    P@5, P@k    share of the top 5 / top k results that are relevant
    MRR         1 / rank of the first relevant result (0 if none), averaged
    nDCG@k      rewards relevant results near the top; 1.0 = perfect order
    ms/query    average search time, after one warm-up query per method

Run (needs the index and the embeddings, see retrieve.py):
    python -m product_search_analysis.search.benchmark                          # every method
    python -m product_search_analysis.search.benchmark --methods tfidf bm25 --top-k 20
    python -m product_search_analysis.search.benchmark --queries my_queries.json
Results are printed and saved to data/benchmark/benchmark_<date_time>.{md,json}.
"""
import argparse
import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path

from product_search_analysis.config import BENCHMARK_DIR, BENCHMARK_QUERIES_FILE, DEFAULT_TOP_K
from product_search_analysis.search.retrieve import available_methods, get_retriever


# ---------- relevance and metrics (pure functions, tested in test/test_search_ranking.py) ----------

def is_relevant(doc: dict, judgment: dict) -> bool:
    """Approximate relevance: expected category, and the required title words if any."""
    if doc.get("category") not in judgment["categories"]:
        return False
    title = (doc.get("title") or "").lower()
    return all(word.lower() in title for word in judgment.get("title_words", []))


def precision_at(relevant: list[bool], k: int) -> float:
    return sum(relevant[:k]) / k


def reciprocal_rank(relevant: list[bool]) -> float:
    for rank, rel in enumerate(relevant, start=1):
        if rel:
            return 1 / rank
    return 0.0


def ndcg_at(relevant: list[bool], k: int, total_relevant: int) -> float:
    """Binary nDCG: DCG of our order / DCG of the best possible order."""
    dcg = sum(1 / math.log2(rank + 1) for rank, rel in enumerate(relevant[:k], start=1) if rel)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, total_relevant) + 1))
    return dcg / ideal if ideal else 0.0


# Metric name (with {k} filled in) -> function(relevant flags, k, number of relevant products).
# Add a metric here and it shows up in every report.
METRICS = {
    "P@5": lambda relevant, k, total: precision_at(relevant, 5),
    "P@{k}": lambda relevant, k, total: precision_at(relevant, k),
    "MRR": lambda relevant, k, total: reciprocal_rank(relevant),
    "nDCG@{k}": lambda relevant, k, total: ndcg_at(relevant, k, total),
}
TIME_METRIC = "ms/query"


# ---------- running ----------

def load_queries(path: Path = BENCHMARK_QUERIES_FILE) -> list[dict]:
    queries = json.loads(Path(path).read_text(encoding="utf-8"))
    for q in queries:
        if not q.get("query") or not q.get("categories"):
            raise ValueError(f"{path}: every query needs 'query' and 'categories': {q}")
    return queries


def _average(rows: list[dict], names: list[str]) -> dict:
    return {name: sum(row[name] for row in rows) / len(rows) for name in names}


def run_benchmark(retriever, queries: list[dict], methods: list[str], k: int) -> dict:
    """Run every query with every method.
    Returns {"summary": {method: metrics}, "by_group": {group: {method: metrics}}, "per_query": [...]}."""
    metric_names = [name.format(k=k) for name in METRICS] + [TIME_METRIC]
    # how many relevant products exist for each query (for nDCG); same for every method
    totals = [sum(is_relevant(doc, q) for doc in retriever.index.docs.values()) for q in queries]

    per_query = []
    for method in methods:
        retriever.retrieve(queries[0]["query"], method, k)     # warm-up: build ranker / load model
        for judgment, total_relevant in zip(queries, totals):
            start = time.perf_counter()
            results = retriever.retrieve(judgment["query"], method, k)
            elapsed_ms = (time.perf_counter() - start) * 1000

            relevant = [is_relevant(r, judgment) for r in results]
            scores = {name.format(k=k): metric(relevant, k, total_relevant) for name, metric in METRICS.items()}
            per_query.append({"method": method, "query": judgment["query"],
                              "group": judgment.get("group", "all"), **scores, TIME_METRIC: elapsed_ms,
                              "top_3": [r.get("title") for r in results[:3]]})

    summary = {m: _average([r for r in per_query if r["method"] == m], metric_names) for m in methods}
    groups = list(dict.fromkeys(r["group"] for r in per_query))
    by_group = {g: {m: _average([r for r in per_query if r["method"] == m and r["group"] == g], metric_names)
                    for m in methods} for g in groups}
    return {"summary": summary, "by_group": by_group, "per_query": per_query}


def _table(rows: dict[str, dict], first_column: str) -> list[str]:
    names = list(next(iter(rows.values())))
    lines = [f"| {first_column} | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for label, scores in rows.items():
        lines.append(f"| {label} | " + " | ".join(
            f"{scores[n]:.1f}" if n == TIME_METRIC else f"{scores[n]:.3f}" for n in names) + " |")
    return lines


def markdown_report(result: dict, k: int, n_queries: int, n_docs: int) -> str:
    summary = result["summary"]
    ndcg = f"nDCG@{k}"
    lines = [f"# Retrieval benchmark ({datetime.now():%Y-%m-%d %H:%M})", "",
             f"{n_queries} queries, {n_docs} products, top {k}. "
             "Relevance = expected category (+ title words); approximate, see benchmark.py.", "",
             *_table(summary, "method")]

    if len(result["by_group"]) > 1:
        lines += ["", f"## {ndcg} by query group", "",
                  *_table({g: {m: s[ndcg] for m, s in methods.items()}
                           for g, methods in result["by_group"].items()}, "group")]

    lines += ["", f"## {ndcg} per query", "",
              "| query | " + " | ".join(summary) + " |", "|---|" + "---|" * len(summary)]
    by_query = {}
    for row in result["per_query"]:
        by_query.setdefault(row["query"], {})[row["method"]] = row[ndcg]
    for query, scores in by_query.items():
        lines.append(f"| {query} | " + " | ".join(f"{scores[m]:.2f}" for m in summary) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    methods = available_methods()
    parser = argparse.ArgumentParser(description="Benchmark the retrieval methods on the same queries.")
    parser.add_argument("--methods", nargs="+", choices=methods, default=methods)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--queries", type=Path, default=BENCHMARK_QUERIES_FILE, help="JSON file of queries")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    queries = load_queries(args.queries)
    retriever = get_retriever()
    result = run_benchmark(retriever, queries, args.methods, args.top_k)
    report = markdown_report(result, args.top_k, len(queries), len(retriever.index.docs))
    print(report)

    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    with open(BENCHMARK_DIR / f"benchmark_{stamp}.md", "x", encoding="utf-8") as f:
        f.write(report)
    with open(BENCHMARK_DIR / f"benchmark_{stamp}.json", "x", encoding="utf-8") as f:
        json.dump({"top_k": args.top_k, "queries": queries, **result}, f, indent=2, ensure_ascii=False)
    print(f"Saved data/benchmark/benchmark_{stamp}.md and .json")


if __name__ == "__main__":
    main()
