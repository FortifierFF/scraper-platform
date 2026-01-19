import { ColumnType, Generated, Insertable, Selectable, Updateable } from 'kysely';
export interface TenantsTable {
    id: Generated<string>;
    name: string;
    api_key: string;
    is_enabled: boolean;
    created_at: ColumnType<Date, never, never>;
    updated_at: ColumnType<Date, never, never>;
}
export interface DatasetsTable {
    id: Generated<string>;
    owner_tenant_id: string | null;
    name: string;
    entity_type: string;
    tags: string[];
    sources: string[];
    schedule_cron: string | null;
    extractor: string;
    config: Record<string, any>;
    is_enabled: boolean;
    created_at: ColumnType<Date, never, never>;
    updated_at: ColumnType<Date, never, never>;
}
export interface JobsTable {
    id: Generated<string>;
    dataset_id: string;
    tenant_id: string;
    status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELED';
    created_at: ColumnType<Date, never, never>;
    started_at: Date | null;
    finished_at: Date | null;
    progress: number;
    stats: Record<string, any>;
    error_message: string | null;
}
export interface ItemsTable {
    id: Generated<string>;
    dataset_id: string;
    tenant_id: string | null;
    entity_type: string;
    tags: string[];
    source: string;
    url: string;
    canonical_url: string | null;
    hash: string;
    published_at: Date | null;
    observed_at: ColumnType<Date, never, never>;
    data: Record<string, any>;
    created_at: ColumnType<Date, never, never>;
}
export interface Database {
    tenants: TenantsTable;
    datasets: DatasetsTable;
    jobs: JobsTable;
    items: ItemsTable;
}
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
