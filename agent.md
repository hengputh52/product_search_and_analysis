You are helping me build the data collection stage of an Information Retrieval
project called ShopBot — a product chatbot that answers questions about
consumer electronics.

## Goal
Build a reproducible, scalable data collection module that fetches, cleans,
and stores 500–1,000 consumer electronics products. This module will later
sit alongside other modules (indexing, ranking, retrieval, RAG, API).
Design for reuse — later stages must consume this module without duplication.

## Tech Stack
- Language: Node.js (ES modules)
- Database: PostgreSQL (Neon)
- HTTP client: axios
- Package manager: npm
- Env config: dotenv
- Logger: pino (lightweight structured logs)

## Architectural Principles
├── .env.example
├── .gitignore
├── package.json
├── README.md
├── docker-compose.yml # (placeholder for later: Elasticsearch)
├── db/
│ ├── migrations/
│ │ └── 001_create_products.sql
│ └── seed/
│ └── sample.json # 10 hand-crafted products for dev
└── src/
├── config/
│ ├── env.js # loads + validates env vars
│ └── constants.js # category IDs, batch sizes, timeouts
├── utils/
│ ├── logger.js # pino logger (shared everywhere)
│ ├── sleep.js
│ └── retry.js # exponential backoff wrapper
├── db/
│ ├── client.js # pg Pool singleton
│ └── repositories/
│ └── productRepository.js # insert, findById, findAll
├── cleaners/
│ ├── html.js # stripHtml()
│ ├── whitespace.js # normalizeWhitespace()
│ ├── text.js # normalizeText() — composed cleaner
│ └── index.js # barrel export
├── sources/
│ ├── ISource.js # JSDoc interface definition
│ ├── bestbuy/
│ │ ├── client.js # axios instance with auth
│ │ ├── mapper.js # BestBuyRaw → Product
│ │ └── index.js # exposes fetchProducts()
│ └── dummyjson/
│ ├── client.js
│ ├── mapper.js
│ └── index.js
├── pipeline/
│ ├── collect.js # orchestrates fetch → clean → store
│ └── deduplicate.js # pure function: dedupe by title
└── scripts/
└── runCollection.js # CLI entry: npm run collect

1. **Separation of concerns** — each layer has one responsibility:
   - `sources/` → external data providers (one file per source)
   - `pipeline/` → orchestration (fetch → clean → store)
   - `cleaners/` → text normalization utilities (shared with later stages)
   - `repositories/` → database access (shared with later stages)
   - `config/` → env + constants
   - `utils/` → generic helpers (sleep, retry, logger)

2. **Pluggable data sources** — adding a new source (Amazon, Flipkart)
   should require ONE new file in `sources/`, zero changes elsewhere.
   All sources implement the same interface:
     `async fetchProducts(category, limit) → ProductRaw[]`

3. **Reusable utilities** — cleaners, logger, retry helper, and DB client
   must be importable by ANY future module (Stage 2 indexer, Stage 5 chat
   API, etc.) without pulling in collection-specific code.

4. **Config, not hardcoding** — API keys, category IDs, batch sizes, delays
   all live in `.env` or `config/constants.js`. No magic numbers in logic.

5. **Testable** — each cleaner and parser is a pure function, exported
   individually. No side effects inside helpers.

## Required Project Structure

## Module Contracts

### `sources/*/index.js` (every source implements this)
```js
/**
 * @param {string} category   — one of: laptop | smartphone | headphones | tv | tablet
 * @param {number} limit      — max products to fetch
 * @returns {Promise<Product[]>}
 */
export async function fetchProducts(category, limit) { ... }
```

### `Product` shape (domain model, source-agnostic)
```js
{
  productId: string,
  title: string,
  description: string,
  brand: string,
  category: 'laptop' | 'smartphone' | 'headphones' | 'tv' | 'tablet',
  price: number,
  specs: Record<string, string>,
  features: string[],
  imageUrl: string,
  sourceUrl: string,
  rating: number | null,
  source: 'bestbuy' | 'dummyjson',
}
```

### `repositories/productRepository.js`
```js
export async function insertMany(products) { ... }
export async function findById(id) { ... }
export async function count() { ... }
export async function truncate() { ... }
```

### `cleaners/text.js`
```js
export function normalizeText(raw) { ... }   // pure, no I/O
```

### `pipeline/collect.js`
```js
export async function runCollection({ source, categories, perCategory }) { ... }
```

## Database

`db/migrations/001_create_products.sql` creates:

| Column        | Type       | Notes                                |
|---------------|------------|--------------------------------------|
| product_id    | TEXT PK    |                                      |
| title         | TEXT       | NOT NULL                             |
| description   | TEXT       | NOT NULL                             |
| brand         | TEXT       |                                      |
| category      | TEXT       | NOT NULL                             |
| price         | NUMERIC    |                                      |
| specs         | JSONB      | default '{}'                         |
| features      | TEXT[]     | default '{}'                         |
| image_url     | TEXT       |                                      |
| source_url    | TEXT       |                                      |
| rating        | NUMERIC    |                                      |
| source        | TEXT       | NOT NULL                             |
| collected_at  | TIMESTAMP  | default now()                        |

Add indexes on `category` and `brand` for later facet queries.

## Config via `.env`
DATABASE_URL=
BESTBUY_API_KEY=
LOG_LEVEL=info
COLLECTION_SOURCE=bestbuy # or dummyjson
PRODUCTS_PER_CATEGORY=200
REQUEST_DELAY_MS=1000
MAX_RETRIES=3


## Responsible Crawling (in `utils/retry.js` + sources)
- Delay between requests: `REQUEST_DELAY_MS` (default 1000ms)
- Retry 429 / 5xx: exponential backoff (1s, 2s, 4s)
- Max retries: `MAX_RETRIES`
- Every request logged via pino with method, URL, status, duration

## Cleaning Rules (composed in `cleaners/text.js`)
- Strip HTML tags
- Collapse whitespace
- Lowercase category
- Drop products with description < 20 chars
- Dedupe by title (case-insensitive)

## CLI Script
`npm run collect` executes `src/scripts/runCollection.js`, which:
1. Loads env
2. Runs migrations if needed
3. Calls `pipeline.collect.runCollection(...)` with env-driven config
4. Prints summary: `{ fetched, kept, duplicates, invalid, inserted }`

Expose additional scripts in `package.json`:
- `npm run migrate` — runs SQL migrations
- `npm run seed` — loads `db/seed/sample.json` for quick dev
- `npm run collect` — full collection

## README Must Document
- Architecture overview (one diagram or bullet list)
- How each layer can be reused by future stages
- How to add a new source (concrete 4-step guide)
- Env setup, migration, run commands
- Dataset license note

## What To Deliver
- All files in the structure above
- Working `npm run migrate && npm run collect`
- Example JSDoc on every exported function
- One short unit test for `normalizeText()` (using `node:test`)
- README with architecture diagram (ASCII is fine)

## Build Order
1. Scaffold folders + `package.json`
2. `config/`, `utils/`, `db/client.js`
3. Migration SQL
4. `cleaners/` (with the `normalizeText` test)
5. `sources/dummyjson/` (easy, no API key)
6. `sources/bestbuy/`
7. `repositories/productRepository.js`
8. `pipeline/collect.js`
9. `scripts/runCollection.js`
10. README

Ask for the Best Buy API key when you reach step 6. Use DummyJSON for the
first end-to-end dry run.