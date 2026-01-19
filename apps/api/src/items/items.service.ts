import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { Kysely } from 'kysely';
import { Database, Item } from '../db/schema';
import { DB } from '../db/db.module';
import { Tenant } from '../db/schema';

@Injectable()
export class ItemsService {
  constructor(@Inject(DB) private readonly db: Kysely<Database>) {}

  /**
   * Get item by ID
   * Verifies tenant has access through dataset
   */
  async findOne(id: string, tenant: Tenant): Promise<Item> {
    const item = await this.db
      .selectFrom('items')
      .innerJoin('datasets', 'datasets.id', 'items.dataset_id')
      .selectAll('items')
      .where('items.id', '=', id)
      .where((eb) =>
        eb.or([
          eb('datasets.owner_tenant_id', 'is', null),
          eb('datasets.owner_tenant_id', '=', tenant.id),
        ]),
      )
      .executeTakeFirst();

    if (!item) {
      throw new NotFoundException(`Item ${id} not found or access denied`);
    }

    return item;
  }

  /**
   * Query items with filters and cursor pagination
   * Only shows items from datasets tenant can access
   */
  async findAll(
    tenant: Tenant,
    filters: {
      datasetId?: string;
      entityType?: string;
      tag?: string;
      source?: string;
      since?: string; // ISO timestamp
      until?: string; // ISO timestamp
      limit?: number;
      cursor?: string; // format: "observedAt|id"
    },
  ): Promise<{ items: Item[]; nextCursor?: string }> {
    // Build query with dataset access check
    let query = this.db
      .selectFrom('items')
      .innerJoin('datasets', 'datasets.id', 'items.dataset_id')
      .selectAll('items')
      .where((eb) =>
        eb.or([
          eb('datasets.owner_tenant_id', 'is', null),
          eb('datasets.owner_tenant_id', '=', tenant.id),
        ]),
      );

    // Apply filters
    if (filters.datasetId) {
      query = query.where('items.dataset_id', '=', filters.datasetId);
    }

    if (filters.entityType) {
      query = query.where('items.entity_type', '=', filters.entityType);
    }

    if (filters.tag) {
      query = query.where('items.tags', '@>', [filters.tag]);
    }

    if (filters.source) {
      query = query.where('items.source', '=', filters.source);
    }

    if (filters.since) {
      query = query.where('items.observed_at', '>=', new Date(filters.since));
    }

    if (filters.until) {
      query = query.where('items.observed_at', '<=', new Date(filters.until));
    }

    // Cursor pagination (using observed_at + id for stable ordering)
    if (filters.cursor) {
      const [observedAt, id] = filters.cursor.split('|');
      query = query.where((eb) =>
        eb.or([
          eb('items.observed_at', '<', new Date(observedAt)),
          eb.and([
            eb('items.observed_at', '=', new Date(observedAt)),
            eb('items.id', '<', id),
          ]),
        ]),
      );
    }

    const limit = Math.min(filters.limit || 50, 100);
    query = query
      .orderBy('items.observed_at', 'desc')
      .orderBy('items.id', 'desc')
      .limit(limit + 1);

    const items = await query.execute();

    // Check if there's a next page
    let nextCursor: string | undefined;
    if (items.length > limit) {
      const lastItem = items[limit - 1];
      nextCursor = `${lastItem.observed_at.toISOString()}|${lastItem.id}`;
      items.pop(); // Remove the extra item
    }

    return { items, nextCursor };
  }
}
