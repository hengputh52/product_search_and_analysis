"""Turn product or query text into search tokens.

tokenize() is the one entry point used by BOTH the index builder and the query
parser, so documents and searches are processed exactly the same way (a search
for "Speakers" finds a product whose text says "speaker").

Steps: strip HTML + collapse spaces (reuse cleaning.normalize_text) -> lowercase
       -> split into words -> drop stop-words -> stem to a common root.
"""
import re

import snowballstemmer

from product_search_analysis.cleaning import normalize_text

# Keep letters and digits together so model numbers survive: "20000mah", "bt5".
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Words too common to help a search. Small on purpose - product text is short.
STOP_WORDS = frozenset("""
a an and are as at be but by for from has have in into is it its of on or
that the their then there these this to was were will with you your
""".split())

_stemmer = snowballstemmer.stemmer("english")


def tokenize(text) -> list[str]:
    """'<b>The SPEAKERS are charging!</b>' -> ['speaker', 'charg']. None/'' -> []."""
    cleaned = normalize_text(text).lower()        # strip HTML, collapse spaces, lowercase
    words = _TOKEN_RE.findall(cleaned)            # split into alphanumeric words
    kept = [w for w in words if w not in STOP_WORDS]
    return _stemmer.stemWords(kept)               # reduce each word to its root
