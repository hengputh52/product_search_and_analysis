# ShopBot product data

This folder holds the **exported product dataset**: a snapshot of the
`products` table in our PostgreSQL (Neon) database, saved as files so every
collaborator can browse the data without database access.

> These files are **generated, so don't edit them by hand**. To refresh them, run:
>
> ```bash
> python -m product_search_analysis.collect   # collect products into the database
> python -m product_search_analysis.export    # rewrite the files in this folder
> ```

## Files

| File | What's inside | Open with |
|---|---|---|
| `products.csv` | One row per product, main columns only | GitHub (renders as a table), Excel, VS Code |
| `products.jsonl` | One product per line as JSON, with **every** field | Code (`json.loads` per line), pandas (`pd.read_json(path, lines=True)`) |

### `products.csv` columns

| Column | Example | Meaning |
|---|---|---|
| `product_id` | `amazon:B07C4YHF4L` | Unique id: `<source>:<id at the source>` |
| `category` | `headphones` | `laptop`, `smartphone`, `headphones`, `tv` or `tablet` |
| `brand` | `Sony` | Brand or manufacturer |
| `title` | `Sony WH-1000XM5 Wireless…` | Product name |
| `price` | `399.99` | Price in USD at collection time |
| `rating` | `4.6` | Average customer rating (1–5) |
| `source_url` | `https://www.amazon.com/dp/…` | Product page |

### Extra fields in `products.jsonl`

| Field | Type | Meaning |
|---|---|---|
| `description` | text | Cleaned product description (≥ 20 characters) |
| `specs` | object | Technical details, e.g. `{"Item Weight": "250 g"}` |
| `features` | list of text | Bullet-point features |
| `image_url` | text | Main product image |
| `source` | text | Where the product came from, e.g. `amazon` |

## Source and license

Products come from **Amazon Reviews 2023** (McAuley Lab, UC San Diego), which
is released for **research use only**. Keep this repository **private**, and
don't redistribute the data. Cite: *Hou et al., "Bridging Language and Items for
Retrieval and Recommendation", 2024.*
