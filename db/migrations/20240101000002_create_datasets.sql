-- migrate:up
-- Create datasets table
CREATE TABLE datasets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_tenant_id UUID NULL REFERENCES tenants(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  sources TEXT[] NOT NULL DEFAULT '{}',
  schedule_cron TEXT NULL,
  extractor TEXT NOT NULL,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for datasets
CREATE INDEX idx_datasets_owner_tenant_id ON datasets(owner_tenant_id) WHERE owner_tenant_id IS NOT NULL;
CREATE INDEX idx_datasets_entity_type ON datasets(entity_type);
CREATE INDEX idx_datasets_extractor ON datasets(extractor);
CREATE INDEX idx_datasets_is_enabled ON datasets(is_enabled);
CREATE INDEX idx_datasets_tags ON datasets USING GIN(tags);

-- migrate:down
DROP TABLE IF EXISTS datasets;
