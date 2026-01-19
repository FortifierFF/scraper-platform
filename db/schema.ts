import { ColumnType, Generated, Insertable, Selectable, Updateable } from 'kysely';

// Tenant table schema
export interface TenantsTable {
  id: Generated<string>; // UUID
  name: string;
  api_key: string;
  is_enabled: boolean;
  created_at: ColumnType<Date, never, never>;
  updated_at: ColumnType<Date, never, never>;
}

// Dataset table schema
export interface DatasetsTable {
  id: Generated<string>; // UUID
  owner_tenant_id: string | null; // NULL = shared/public
  name: string;
  entity_type: string; // e.g. "article.v1", "product.v1"
  tags: string[]; // TEXT[]
  sources: string[]; // TEXT[]
  schedule_cron: string | null;
  extractor: string; // spider name
  config: Record<string, any>; // JSONB
  is_enabled: boolean;
  created_at: ColumnType<Date, never, never>;
  updated_at: ColumnType<Date, never, never>;
}

// Job table schema
export interface JobsTable {
  id: Generated<string>; // UUID
  dataset_id: string; // FK to datasets
  tenant_id: string; // FK to tenants (caller who triggered)
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELED';
  created_at: ColumnType<Date, never, never>;
  started_at: Date | null;
  finished_at: Date | null;
  progress: number; // INT, default 0
  stats: Record<string, any>; // JSONB
  error_message: string | null;
}

// Item table schema
export interface ItemsTable {
  id: Generated<string>; // UUID
  dataset_id: string; // FK to datasets
  tenant_id: string | null; // nullable for future use
  entity_type: string;
  tags: string[]; // TEXT[]
  source: string;
  url: string;
  canonical_url: string | null;
  hash: string; // for deduplication
  published_at: Date | null;
  observed_at: ColumnType<Date, never, never>;
  data: Record<string, any>; // JSONB
  created_at: ColumnType<Date, never, never>;
}

// Database interface for Kysely
export interface Database {
  tenants: TenantsTable;
  datasets: DatasetsTable;
  jobs: JobsTable;
  items: ItemsTable;
}

// Type helpers for inserts/updates/selects
export type Tenant = Selectable<TenantsTable>;
export type NewTenant = Insertable<TenantsTable>;
export type TenantUpdate = Updateable<TenantsTable>;

export type Dataset = Selectable<DatasetsTable>;
export type NewDataset = Insertable<DatasetsTable>;
export type DatasetUpdate = Updateable<DatasetsTable>;

export type Job = Selectable<JobsTable>;
export type NewJob = Insertable<JobsTable>;
export type JobUpdate = Updateable<JobsTable>;

export type Item = Selectable<ItemsTable>;
export type NewItem = Insertable<ItemsTable>;
export type ItemUpdate = Updateable<ItemsTable>;
