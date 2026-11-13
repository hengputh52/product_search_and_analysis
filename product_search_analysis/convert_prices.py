"""Recalculate the USD `price` of products already in the database from their original price text.

Use it after changing an exchange rate in config.py (USD_PER_EUR, KHR_PER_USD), or for rows
saved before a currency was converted. No web requests: it only reads the price text that
was saved with each product.

    python -m product_search_analysis.convert_prices --dry-run   # show what would change
    python -m product_search_analysis.convert_prices             # update the database
    python -m product_search_analysis.export                     # then write a new export
"""
import argparse

from product_search_analysis import db
from product_search_analysis.scraping.amazon.amazon_scraping import parse_price_usd
from product_search_analysis.scraping.notebookcheck.parser import price_usd as notebookcheck_price_usd

# source -> (specs key holding the price as shown on the website, function: text -> USD or None)
# amazon and kaggle_amazon_in are not listed: they are already saved in USD.
PRICE_TEXT = {
    "notebookcheck": ("Price", notebookcheck_price_usd),
    "amazon_web": ("Price (as shown)", parse_price_usd),
}


def changes(conn) -> list[tuple[str, str, float | None, float | None]]:
    """(product_id, price text, old price, new price) for every row whose USD price would change."""
    found = []
    for source, (key, to_usd) in PRICE_TEXT.items():
        rows = conn.execute(
            "SELECT product_id, specs->>%s, price FROM products WHERE source = %s AND specs ? %s",
            (key, source, key),
        )
        for product_id, text, old in rows.fetchall():
            new = to_usd(text)
            old = float(old) if old is not None else None
            if new is not None and new != old:  # never erase a price we can't recalculate
                found.append((product_id, text, old, new))
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="Recalculate USD prices from the saved price text.")
    parser.add_argument("--dry-run", action="store_true", help="only show what would change")
    args = parser.parse_args()

    with db.connect() as conn:
        found = changes(conn)
        for product_id, text, old, new in found:
            print(f"{product_id:28} {text!r:24} {old} -> {new}")
        if not args.dry_run:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE products SET price = %s WHERE product_id = %s",
                    [(new, product_id) for product_id, _, _, new in found],
                )
    action = "would update" if args.dry_run else "updated"
    print(f"{action} {len(found)} prices")


if __name__ == "__main__":
    main()
