import { Kysely, PostgresDialect } from 'kysely';
import { Pool } from 'pg';
import { Database, NewTenant, NewDataset } from './schema';
import * as dotenv from 'dotenv';
import * as path from 'path';
import * as fs from 'fs';

// Load environment variables
// Try multiple paths for .env file
const envPaths = [
  path.join(__dirname, '../.env'),
  path.join(__dirname, '../../.env'),
  '.env',
];
for (const envPath of envPaths) {
  if (fs.existsSync(envPath)) {
    dotenv.config({ path: envPath });
    break;
  }
}

async function seed() {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    throw new Error('DATABASE_URL is required');
  }

  // Create Kysely instance
  const pool = new Pool({
    connectionString: databaseUrl,
  });

  const db = new Kysely<Database>({
    dialect: new PostgresDialect({
      pool,
    }),
  });

  try {
    console.log('Starting seed...');

    // Check if dev tenant already exists
    const existingTenant = await db
      .selectFrom('tenants')
      .selectAll()
      .where('api_key', '=', 'dev-key')
      .executeTakeFirst();

    let tenantId: string;

    if (existingTenant) {
      console.log('Dev tenant already exists, using existing tenant');
      tenantId = existingTenant.id;
    } else {
      // Create dev tenant
      const newTenant: NewTenant = {
        name: 'dev',
        api_key: 'dev-key',
        is_enabled: true,
      };

      const [tenant] = await db
        .insertInto('tenants')
        .values(newTenant)
        .returningAll()
        .execute();

      console.log(`Created tenant: ${tenant.name} (${tenant.id})`);
      tenantId = tenant.id;
    }

    // Check if example dataset already exists
    const existingDataset = await db
      .selectFrom('datasets')
      .selectAll()
      .where('name', '=', 'Example News')
      .where('extractor', '=', 'example_news_spider')
      .executeTakeFirst();

    if (existingDataset) {
      console.log('Example dataset already exists');
    } else {
      // Create shared example dataset
      const newDataset: NewDataset = {
        owner_tenant_id: null, // Shared/public dataset
        name: 'Example News',
        entity_type: 'article.v1',
        extractor: 'example_news_spider',
        tags: ['news/world', 'en'],
        sources: ['example.com'],
        schedule_cron: null,
        config: {
          start_urls: [
            'https://example.com/news',
            // NOTE: These are placeholder URLs. Replace with real URLs for actual scraping.
          ],
          article_link_selector: 'a.article-link',
          title_selector: 'h1.article-title',
          date_selector: 'time.published-date',
          content_selector: 'div.article-content p',
        },
        is_enabled: true,
      };

      const [dataset] = await db
        .insertInto('datasets')
        .values(newDataset)
        .returningAll()
        .execute();

      console.log(`Created dataset: ${dataset.name} (${dataset.id})`);
    }

    console.log('Seed completed successfully!');
  } catch (error) {
    console.error('Seed failed:', error);
    throw error;
  } finally {
    await db.destroy();
  }
}

// Run seed if called directly
if (require.main === module) {
  seed()
    .then(() => {
      console.log('Done');
      process.exit(0);
    })
    .catch((error) => {
      console.error('Error:', error);
      process.exit(1);
    });
}

export { seed };
