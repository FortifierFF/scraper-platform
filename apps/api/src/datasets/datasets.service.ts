import { Injectable, NotFoundException, ForbiddenException, Inject } from '@nestjs/common';
import { Kysely } from 'kysely';
import { Database, Dataset, NewDataset, DatasetUpdate } from '../db/schema';
import { DB } from '../db/db.module';
import { CreateDatasetDto } from './dto/create-dataset.dto';
import { UpdateDatasetDto } from './dto/update-dataset.dto';
import { Tenant } from '../db/schema';

@Injectable()
export class DatasetsService {
  constructor(@Inject(DB) private readonly db: Kysely<Database>) {}

  /**
   * List datasets with filters
   * Tenant can see shared datasets (owner_tenant_id IS NULL) and their own datasets
   */
  async findAll(
    tenant: Tenant,
    filters: {
      entityType?: string;
      tag?: string;
      source?: string;
      mine?: boolean;
    },
  ): Promise<Dataset[]> {
    let query = this.db
      .selectFrom('datasets')
      .selectAll()
      .where((eb) =>
        eb.or([
          eb('owner_tenant_id', 'is', null), // Shared datasets
          eb('owner_tenant_id', '=', tenant.id), // Own datasets
        ]),
      );

    // Apply filters
    if (filters.entityType) {
      query = query.where('entity_type', '=', filters.entityType);
    }

    if (filters.tag) {
      query = query.where('tags', '@>', [filters.tag]);
    }

    if (filters.source) {
      query = query.where('sources', '@>', [filters.source]);
    }

    if (filters.mine === true) {
      query = query.where('owner_tenant_id', '=', tenant.id);
    }

    return query.orderBy('created_at', 'desc').execute();
  }

  /**
   * Get dataset by ID
   * Enforces access rules (shared or owned by tenant)
   */
  async findOne(id: string, tenant: Tenant): Promise<Dataset> {
    const dataset = await this.db
      .selectFrom('datasets')
      .selectAll()
      .where('id', '=', id)
      .where((eb) =>
        eb.or([
          eb('owner_tenant_id', 'is', null),
          eb('owner_tenant_id', '=', tenant.id),
        ]),
      )
      .executeTakeFirst();

    if (!dataset) {
      throw new NotFoundException(`Dataset ${id} not found or access denied`);
    }

    return dataset;
  }

  /**
   * Create a new dataset
   * Sets owner_tenant_id to current tenant
   */
  async create(tenant: Tenant, dto: CreateDatasetDto): Promise<Dataset> {
    const newDataset: NewDataset = {
      owner_tenant_id: tenant.id,
      name: dto.name,
      entity_type: dto.entity_type,
      tags: dto.tags || [],
      sources: dto.sources || [],
      schedule_cron: dto.schedule_cron || null,
      extractor: dto.extractor,
      config: dto.config,
      is_enabled: dto.is_enabled ?? true,
    };

    const [dataset] = await this.db
      .insertInto('datasets')
      .values(newDataset)
      .returningAll()
      .execute();

    return dataset;
  }

  /**
   * Update dataset
   * Only owner can update (or shared datasets can be updated by anyone - adjust if needed)
   */
  async update(
    id: string,
    tenant: Tenant,
    dto: UpdateDatasetDto,
  ): Promise<Dataset> {
    // First check access
    const existing = await this.findOne(id, tenant);

    // Only owner can update (shared datasets can be updated by anyone for MVP)
    // For stricter control, uncomment:
    // if (existing.owner_tenant_id && existing.owner_tenant_id !== tenant.id) {
    //   throw new ForbiddenException('Only dataset owner can update');
    // }

    const update: DatasetUpdate = {
      ...dto,
    };

    const [dataset] = await this.db
      .updateTable('datasets')
      .set(update)
      .where('id', '=', id)
      .returningAll()
      .execute();

    return dataset;
  }
}
