import { Injectable, NotFoundException, ForbiddenException, Inject } from '@nestjs/common';
import { Kysely } from 'kysely';
import { Database, Job, NewJob } from '../db/schema';
import { DB } from '../db/db.module';
import { Queue } from 'bullmq';
import { Tenant } from '../db/schema';
import { DatasetsService } from '../datasets/datasets.service';

@Injectable()
export class JobsService {
  private readonly queue: Queue;

  constructor(
    @Inject(DB) private readonly db: Kysely<Database>,
    private readonly datasetsService: DatasetsService,
  ) {
    // Initialize BullMQ queue
    this.queue = new Queue('scrape-jobs', {
      connection: {
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT || '6379', 10),
      },
    });
  }

  /**
   * Create a job and enqueue it to BullMQ
   * Verifies tenant has access to the dataset
   */
  async create(tenant: Tenant, datasetId: string): Promise<Job> {
    // Verify dataset exists and tenant has access
    const dataset = await this.datasetsService.findOne(datasetId, tenant);

    // Create job record
    // Store mode in stats JSONB (mode: 'quick_check' or 'full')
    const mode = (dto as any).mode || 'full'; // Default to full if not specified
    const newJob: NewJob = {
      dataset_id: datasetId,
      tenant_id: tenant.id,
      status: 'QUEUED',
      progress: 0,
      stats: { mode }, // Store mode in stats
    };

    const [job] = await this.db
      .insertInto('jobs')
      .values(newJob)
      .returningAll()
      .execute();

    // Enqueue to BullMQ
    await this.queue.add('scrape', {
      jobId: job.id,
      datasetId: datasetId,
    });

    return job;
  }

  /**
   * Get job by ID
   * Verifies tenant has access (job belongs to tenant or dataset is accessible)
   */
  async findOne(id: string, tenant: Tenant): Promise<Job> {
    const job = await this.db
      .selectFrom('jobs')
      .selectAll()
      .where('id', '=', id)
      .executeTakeFirst();

    if (!job) {
      throw new NotFoundException(`Job ${id} not found`);
    }

    // Verify access through dataset
    try {
      await this.datasetsService.findOne(job.dataset_id, tenant);
    } catch (error) {
      throw new ForbiddenException('Access denied to this job');
    }

    return job;
  }

  /**
   * List jobs with filters
   * Only shows jobs for datasets tenant can access
   */
  async findAll(
    tenant: Tenant,
    filters: {
      datasetId?: string;
      status?: string;
      limit?: number;
      cursor?: string;
    },
  ): Promise<{ jobs: Job[]; nextCursor?: string }> {
    // Build query with dataset access check
    let query = this.db
      .selectFrom('jobs')
      .innerJoin('datasets', 'datasets.id', 'jobs.dataset_id')
      .selectAll('jobs')
      .where((eb) =>
        eb.or([
          eb('datasets.owner_tenant_id', 'is', null),
          eb('datasets.owner_tenant_id', '=', tenant.id),
        ]),
      );

    if (filters.datasetId) {
      query = query.where('jobs.dataset_id', '=', filters.datasetId);
    }

    if (filters.status) {
      query = query.where('jobs.status', '=', filters.status as any);
    }

    // Cursor pagination (using created_at + id)
    if (filters.cursor) {
      const [createdAt, id] = filters.cursor.split('|');
      query = query.where((eb) =>
        eb.or([
          eb('jobs.created_at', '<', new Date(createdAt)),
          eb.and([
            eb('jobs.created_at', '=', new Date(createdAt)),
            eb('jobs.id', '<', id),
          ]),
        ]),
      );
    }

    const limit = Math.min(filters.limit || 50, 100);
    query = query.orderBy('jobs.created_at', 'desc').orderBy('jobs.id', 'desc').limit(limit + 1);

    const jobs = await query.execute();

    // Check if there's a next page
    let nextCursor: string | undefined;
    if (jobs.length > limit) {
      const lastJob = jobs[limit - 1];
      nextCursor = `${lastJob.created_at.toISOString()}|${lastJob.id}`;
      jobs.pop(); // Remove the extra item
    }

    return { jobs, nextCursor };
  }
}
