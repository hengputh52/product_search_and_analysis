"""Boolean query engine over the inverted index.

Supports:  AND  OR  NOT  "exact phrase"  ( grouping )
Precedence (tightest first):  phrase / () , NOT , AND , OR
Adjacent terms are ANDed implicitly, so  `bluetooth speaker`  ==  `bluetooth AND speaker`.
Operators are case-insensitive (AND / and both work).

    from product_search_analysis.search import search_boolean
    search_boolean('(speaker OR headphones) AND bluetooth NOT sony')
"""
import re

from product_search_analysis.search.index import load_index
from product_search_analysis.search.text import tokenize

# A query splits into: a "quoted phrase", a single parenthesis, or a run of other chars.
_LEX_RE = re.compile(r'"[^"]*"|[()]|[^\s()]+')
_OPERATORS = {"AND", "OR", "NOT"}


def _lex(query: str) -> list[str]:
    return _LEX_RE.findall(query or "")


def _atom(token: str):
    """A phrase ("a b") or a word -> an AST leaf. Both go through tokenize()."""
    if token.startswith('"') and token.endswith('"'):
        return ("PHRASE", tokenize(token[1:-1]))
    terms = tokenize(token)                       # a word may clean down to 0, 1 or many
    if len(terms) == 1:
        return ("TERM", terms[0])
    return ("PHRASE", terms)                       # [] matches nothing; >1 behaves as a phrase


class _Parser:
    """Recursive-descent parser. Grammar (loosest to tightest):
        or_expr  := and_expr (OR and_expr)*
        and_expr := not_expr ((AND)? not_expr)*     # AND is optional between atoms
        not_expr := NOT not_expr | atom
        atom     := '(' or_expr ')' | phrase | term
    """

    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        node = self._or()
        if self.pos != len(self.tokens):
            raise ValueError(f"Unexpected token in query: {self._peek()!r}")
        return node

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self):
        token = self._peek()
        self.pos += 1
        return token

    def _is_op(self, name: str) -> bool:
        token = self._peek()
        return (token is not None and token not in ("(", ")")
                and not token.startswith('"') and token.upper() == name)

    def _or(self):
        node = self._and()
        while self._is_op("OR"):
            self._next()
            node = ("OR", node, self._and())
        return node

    def _and(self):
        node = self._not()
        while True:
            token = self._peek()
            if token is None or token == ")" or self._is_op("OR"):
                break
            if self._is_op("AND"):          # explicit AND
                self._next()
            node = ("AND", node, self._not())   # ...or implicit AND between adjacent atoms
        return node

    def _not(self):
        if self._is_op("NOT"):
            self._next()
            return ("NOT", self._not())
        return self._atom()

    def _atom(self):
        token = self._peek()
        if token is None:
            raise ValueError("Unexpected end of query")
        if token == "(":
            self._next()
            node = self._or()
            if self._next() != ")":
                raise ValueError("Missing closing ')'")
            return node
        if token == ")":
            raise ValueError("Unexpected ')'")
        self._next()
        return _atom(token)


def _phrase_docs(index, terms) -> set:
    """Products where `terms` appear as consecutive positions (phrase match)."""
    postings = [index.positions(t) for t in terms]
    if not terms or any(not p for p in postings):
        return set()
    candidates = set(postings[0])
    for p in postings[1:]:
        candidates &= set(p)
    result = set()
    for doc in candidates:
        later = [set(p[doc]) for p in postings[1:]]
        for start in postings[0][doc]:
            if all((start + offset + 1) in later[offset] for offset in range(len(later))):
                result.add(doc)
                break
    return result


def _evaluate(node, index) -> set:
    kind = node[0]
    if kind == "TERM":
        return set(index.positions(node[1]))
    if kind == "PHRASE":
        return _phrase_docs(index, node[1])
    if kind == "AND":
        return _evaluate(node[1], index) & _evaluate(node[2], index)
    if kind == "OR":
        return _evaluate(node[1], index) | _evaluate(node[2], index)
    if kind == "NOT":
        return index.doc_ids - _evaluate(node[1], index)
    raise ValueError(f"Unknown node: {node!r}")


def search_boolean(query: str, index=None) -> list[dict]:
    """Run a Boolean query and return matching products, ordered by product_id.

    Each result is {"product_id": ..., "title": ..., "source_url": ...}.
    `index` defaults to the one saved on disk (load_index); pass one in for tests.
    """
    index = index if index is not None else load_index()
    tokens = _lex(query)
    if not tokens:
        return []
    doc_ids = _evaluate(_Parser(tokens).parse(), index)
    return [{"product_id": doc_id, **index.docs[doc_id]} for doc_id in sorted(doc_ids)]
