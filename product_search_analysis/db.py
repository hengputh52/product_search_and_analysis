import psycopg
from psycopg.types.json import Jsonb

from product_search_analysis.config import DATABASE_URL, SCHEMA_FILE

INSERT_SQL = """
INSERT INTO products (product_id, title, description, brand, category, price,
                      specs, features, image_url, source_url, rating, source)
VALUES (%(product_id)s, %(title)s, %(description)s, %(brand)s, %(category)s, %(price)s,
        %(specs)s, %(features)s, %(image_url)s, %(source_url)s, %(rating)s, %(source)s)
ON CONFLICT (product_id) DO UPDATE SET
  title = EXCLUDED.title, description = EXCLUDED.description, brand = EXCLUDED.brand,
  category = EXCLUDED.category, price = EXCLUDED.price, specs = EXCLUDED.specs,
  features = EXCLUDED.features, image_url = EXCLUDED.image_url,
  source_url = EXCLUDED.source_url, rating = EXCLUDED.rating, collected_at = now()
"""


def connect():
    """Open a connection. Use it with `with connect() as conn:` (auto commit + close)."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing in .env")
    return psycopg.connect(DATABASE_URL)


def create_tables(conn) -> None:
    """Run db/schema.sql (safe to run many times)."""
    conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


def save_products(conn, products: list[dict]) -> int:
    """Insert products; existing product_ids are updated instead of duplicated."""
    rows = [{**p, "specs": Jsonb(p["specs"])} for p in products]
    with conn.cursor() as cur:
        cur.executemany(INSERT_SQL, rows)
    return len(rows)


def count_products(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]