"""Search: text cleaning, an inverted index, Boolean queries and ranked retrieval.

Hand-off functions:
    tokenize(text)                       -> list[str]     clean + tokenize text (text.py)
    load_index()                         -> Index         load the saved index from disk (index.py)
    search_boolean(query)                -> list[dict]    run a Boolean query (boolean.py)
    retrieve(query, method, top_k)       -> list[dict]    ranked products, best first (retrieve.py)
        method: one of available_methods(): "tfidf" | "bm25" | "dense" | "hybrid" (default) | yours

Extension points:
    register_method(name, builder)       add a ranking method (retrieve.py)
    Ranker                               the interface a ranking method implements (rankers.py)
"""
from product_search_analysis.search.boolean import search_boolean
from product_search_analysis.search.index import Index, build_index, load_index, save_index
from product_search_analysis.search.rankers import Ranker
from product_search_analysis.search.retrieve import Retriever, available_methods, register_method, retrieve
from product_search_analysis.search.text import tokenize

__all__ = ["tokenize", "load_index", "search_boolean", "retrieve", "Retriever",
           "available_methods", "register_method", "Ranker",
           "Index", "build_index", "save_index"]
