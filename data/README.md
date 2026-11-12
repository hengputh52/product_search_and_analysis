# ShopBot product data

This folder holds the **exported product dataset**: a snapshot of the
`products` table in our PostgreSQL (Neon) database, saved as files so every
collaborator can browse the data without database access.

> These files are **generated, so don't edit them by hand**. Every export creates a **new** pair of
> files named with the date and time (e.g. `products_2026-11-12_143005.csv`). Old exports are never
> overwritten. **The newest export is the last file when sorted by name.** To make a new one, run:
>
> ```bash
> python -m product_search_analysis.collect   # collect products into the database
> python -m product_search_analysis.export    # write a new timestamped export here
> ```

## Files

| File | What's inside | Open with |
|---|---|---|
| `products_<date_time>.csv` | One row per product, main columns only | GitHub (renders as a table), Excel, VS Code |
| `products_<date_time>.jsonl` | One product per line as JSON, with **every** field | Code (`json.loads` per line), pandas (`pd.read_json(path, lines=True)`) |

### CSV columns

| Column | Example | Meaning |
|---|---|---|
| `product_id` | `amazon:B07C4YHF4L` | Unique id: `<source>:<id at the source>` |
| `category` | `headphones` | `laptop`, `smartphone`, `headphones`, `tv` or `tablet` |
| `brand` | `Sony` | Brand or manufacturer |
| `title` | `Sony WH-1000XM5 Wireless…` | Product name |
| `price` | `399.99` | Price in USD at collection time |
| `rating` | `4.6` | Average customer rating (1–5) |
| `source_url` | `https://www.amazon.com/dp/…` | Product page |

### Extra fields in the JSONL file

| Field | Type | Meaning |
|---|---|---|
| `description` | text | Cleaned product description (≥ 20 characters) |
| `specs` | object | Technical details, e.g. `{"Item Weight": "250 g"}` |
| `features` | list of text | Bullet-point features |
| `image_url` | text | Main product image |
| `source` | text | Where the product came from, e.g. `amazon` |

## Sources and licenses

The `source` column says where each product came from:

| `source` | Dataset | License / terms |
|---|---|---|
| `amazon` | **Amazon Reviews 2023** (McAuley Lab, UC San Diego) | Research use only. Cite: *Hou et al., "Bridging Language and Items for Retrieval and Recommendation", 2024.* |
| `kaggle_amazon_in` | **Amazon Sales Dataset** by karkavelrajaj on Kaggle (Amazon India, Jan 2023) | **CC BY-NC-SA 4.0**: non-commercial, credit the author, share derived data under the same license. Prices were converted from INR at 82.8 INR = 1 USD; originals are in `specs["Price (INR)"]`. |

Both datasets were originally collected from Amazon, so keep this repository
**private** and don't redistribute the data.
