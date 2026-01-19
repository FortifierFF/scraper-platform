-- migrate:up
-- Create tenants table
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  api_key TEXT UNIQUE NOT NULL,
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for API key lookups
CREATE INDEX idx_tenants_api_key ON tenants(api_key) WHERE is_enabled = TRUE;

-- migrate:down
DROP TABLE IF EXISTS tenants;
