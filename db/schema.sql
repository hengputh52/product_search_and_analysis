CREATE TABLE IF NOT EXISTS products (
  product_id    TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  description   TEXT NOT NULL,
  brand         TEXT,
  category      TEXT NOT NULL,
  price         NUMERIC,
  specs         JSONB  DEFAULT '{}',
  features      TEXT[] DEFAULT '{}',
  image_url     TEXT,
  source_url    TEXT,
  rating        NUMERIC,
  source        TEXT NOT NULL,
  collected_at  TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
CREATE INDEX IF NOT EXISTS idx_products_brand    ON products (brand);