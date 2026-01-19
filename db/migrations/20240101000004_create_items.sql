-- migrate:up
-- Create items table
CREATE TABLE items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  tenant_id UUID NULL REFERENCES tenants(id) ON DELETE SET NULL,
  entity_type TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  canonical_url TEXT NULL,
  hash TEXT NOT NULL,
  published_at TIMESTAMPTZ NULL,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  data JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique constraint: one item per dataset+url
CREATE UNIQUE INDEX idx_items_dataset_url_unique ON items(dataset_id, url);

-- Index for deduplication by hash
CREATE INDEX idx_items_dataset_hash ON items(dataset_id, hash);

-- Indexes for querying
CREATE INDEX idx_items_dataset_id ON items(dataset_id);
CREATE INDEX idx_items_entity_type ON items(entity_type);
CREATE INDEX idx_items_source ON items(source);
CREATE INDEX idx_items_published_at ON items(published_at DESC);
CREATE INDEX idx_items_observed_at ON items(observed_at DESC);
CREATE INDEX idx_items_tags ON items USING GIN(tags);
-- Optional GIN index on data for JSON queries
CREATE INDEX idx_items_data ON items USING GIN(data);

-- migrate:down
DROP TABLE IF EXISTS items;
