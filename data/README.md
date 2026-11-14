# ShopBot product data

This folder holds the **exported product dataset**: a snapshot of the
`products` table in our PostgreSQL (Neon) database, saved as files so every
collaborator can browse the data without database access.

> These files are **generated, so don't edit them by hand**. There is one pair of files per source,
> `products_<source>_<date_time>.csv` and `.jsonl`, e.g. `products_ptc_computer_2026-11-14_115038.csv`.
> Each export creates **new** files; delete the older pair of that source afterwards so only the newest
> stays. To make new ones, run:
>
> ```bash
> python -m product_search_analysis.collect --source <source>   # collect products into the database
> python -m product_search_analysis.export --source <source>    # write a new timestamped export here
> ```

## Files

| File | What's inside | Open with |
|---|---|---|
| `products_<source>_<date_time>.csv` | One row per product, every field except `specs` and `features` | GitHub (renders as a table), Excel, VS Code |
| `products_<source>_<date_time>.jsonl` | One product per line as JSON, with **every** field | Code (`json.loads` per line), pandas (`pd.read_json(path, lines=True)`) |

Without `--source`, the export holds every source and is named `products_<date_time>.*`; with `--category` the categories are added to the name.

### CSV columns

| Column | Example | Meaning |
|---|---|---|
| `product_id` | `amazon:B07C4YHF4L` | Unique id: `<source>:<id at the source>` |
| `category` | `headphones` | `laptop`, `smartphone`, `headphones`, `tv` or `tablet` |
| `brand` | `Sony` | Brand or manufacturer |
| `title` | `Sony WH-1000XM5 Wireless…` | Product name |
| `price` | `399.99` | Price in USD at collection time. Other currencies are converted (INR, riel: see Sources; notebookcheck euros at 1 EUR = 1.1081 USD, ECB rate of 2026-11-12, original in `specs["Price"]`). Empty = no price found |
| `rating` | `4.6` | Average customer rating (1–5). Empty when the source shows no ratings |
| `description` | `CPU: Intel Core i5 | RAM: 16GB …` | Cleaned product description (≥ 20 characters) |
| `image_url` | `https://…/image.jpg` | Main product image |
| `source_url` | `https://www.amazon.com/dp/…` | Product page |
| `source` | `amazon` | Where the product came from (see Sources and licenses) |

### Extra fields in the JSONL files

| Field | Type | Meaning |
|---|---|---|
| `specs` | object | Technical details, e.g. `{"Item Weight": "250 g"}` |
| `features` | list of text | Bullet-point features |

## Sources and licenses

The `source` column says where each product came from:

| `source` | Dataset | License / terms |
|---|---|---|
| `amazon` | **Amazon Reviews 2023** (McAuley Lab, UC San Diego) | Research use only. Cite: *Hou et al., "Bridging Language and Items for Retrieval and Recommendation", 2024.* |
| `kaggle_amazon_in` | **Amazon Sales Dataset** by karkavelrajaj on Kaggle (Amazon India, Jan 2023) | **CC BY-NC-SA 4.0**: non-commercial, credit the author, share derived data under the same license. Prices were converted from INR at 82.8 INR = 1 USD; originals are in `specs["Price (INR)"]`. |
| `amazon_web` | Scraped live from amazon.com search results (`scraping/amazon/amazon_scraping.py`) | Subject to Amazon's Conditions of Use. `price` is USD. Prices Amazon showed in riel were converted at `config.KHR_PER_USD` (4,000 KHR = 1 USD, approximate); other currencies are left empty. Requests ask Amazon for USD prices with its `i18n-prefs=USD` cookie. The shown text is always in `specs["Price (as shown)"]`. |
| `alibaba` | Scraped from alibaba.com search results (`scraping/alibaba/alibaba.py`) | Subject to Alibaba's Terms of Use. `price` is the lowest price of the range shown, in USD; the shown range, minimum order and supplier are in `specs`. `brand` is empty (Alibaba lists suppliers, not brands) and `description` is the text shown on the search card. |
| `ptc_computer` | Scraped from the listing pages of ptc-computer.com.kh, a computer shop in Cambodia (`scraping/ptc_computer/ptc_computer.py`) | The site has no robots.txt; check its terms before sharing. `price` is the shop price in USD (old price, SKU and stock are in `specs`). Category `computer` mixes laptops, desktops and all-in-ones. `rating` is empty: the site shows no ratings. |
| `angkor_meas` | Scraped from angkormeas.com, a phone shop in Cambodia (`scraping/angkor_meas/angkor_meas.py`) | robots.txt allows these pages for general crawlers. `price` is the current shop price in USD (sale price when on sale; the crossed-out price, stock and "Used" condition are in `specs`). The description lists the variants with their prices, what is in the box and colours. `rating` is empty: the shop shows no ratings. |
| `sunsimexco` | Scraped from sunsimexco.com.kh, an electronics shop in Cambodia (`scraping/sunsimexco/sunsimexco.py`) | robots.txt allows everything. Only products with an exact price and a specification are kept ("Call for price" products are skipped). `price` is the current price in USD; old price, discount, SKU and subcategory are in `specs`. Category `tv` comes from the shop's "Televisions & Projector" listing, so it can include projectors. `rating` is empty. |

All the sources above were collected from other sites (Amazon, Alibaba, PTC Computer, Angkor Meas, Sunsimexco), so keep this repository
**private** and don't redistribute the data.
