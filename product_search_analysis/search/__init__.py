"""Search: text cleaning, an inverted index, and a Boolean query engine.

Hand-off functions:
    tokenize(text)          -> list[str]     clean + tokenize text (text.py)
    load_index()            -> Index         load the saved index from disk (index.py)
    search_boolean(query)   -> list[dict]    run a Boolean query (boolean.py)
"""
from product_search_analysis.search.boolean import search_boolean
from product_search_analysis.search.index import Index, build_index, load_index, save_index
from product_search_analysis.search.text import tokenize

__all__ = ["tokenize", "load_index", "search_boolean",
           "Index", "build_index", "save_index"]
