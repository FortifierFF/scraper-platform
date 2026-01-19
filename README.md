# Scraper Platform

A production-ready scraping platform monorepo built with NestJS, Python Scrapy, Postgres, and Redis. Supports multi-tenancy, config-driven scraping, and job orchestration.

## Architecture

- **NestJS API**: RESTful API with Kysely (SQL builder) for database access
- **Python Worker**: Scrapy-based worker that polls the database for jobs
- **Postgres**: Stores datasets, jobs, items, and tenants
- **Redis + BullMQ**: Job queue (API enqueues, worker polls DB for MVP)
- **Docker Compose**: Local development environment

## Tech Stack

- Node.js 20+, TypeScript
- NestJS (API framework)
- Kysely (TypeScript SQL builder, no ORM)
- dbmate (database migrations)
- BullMQ + Redis (job queue)
- Python 3.11+ (worker)
- Scrapy + BeautifulSoup4
- Docker + Docker Compose

## Project Structure

```
scraper-platform/
  apps/
    api/                      # NestJS API
  services/
    worker/                   # Python Scrapy worker
  db/
    migrations/               # SQL migrations (dbmate)
    schema.ts                 # Kysely Database types
    seed.ts                   # Seed script
  docker/
    api.Dockerfile
    worker.Dockerfile
  docker-compose.yml
  .env.example
  README.md
```

## Setup

### Prerequisites

- Docker and Docker Compose
- pnpm (>=8.0.0)
- Node.js 20+
- Python 3.11+ (if running worker locally)

### 1. Clone and Install

```bash
# Install pnpm if not already installed
npm install -g pnpm

# Install dependencies
pnpm install
```

### 2. Environment Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Database Configuration
# Use your actual database credentials
DATABASE_URL=postgresql://${POSTGRES_USER:-scraper}:${POSTGRES_PASSWORD:-scraper123}@localhost:5433/${POSTGRES_DB:-scraper_db}
POSTGRES_USER=scraper
POSTGRES_PASSWORD=scraper123
POSTGRES_DB=scraper_db

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# API Configuration
API_PORT=3000

# Worker Configuration
WORKER_POLL_INTERVAL=5
```

**Note**: The database uses port `5433` (not 5432) to avoid conflicts.

### 3. Start Services

```bash
# Start all services (Postgres, Redis, API, Worker)
docker compose up --build
```

This will:
- Start Postgres on port 5433
- Start Redis on port 6379
- Start the NestJS API on port 3000
- Start the Python worker

### 4. Run Migrations

In a new terminal, run migrations:

```bash
# DATABASE_URL is loaded from .env file
# Run migrations
dbmate up
```

Or run migrations inside the API container:

```bash
# DATABASE_URL is already set in docker-compose.yml from .env
docker compose exec api dbmate up
```

### 5. Seed Database

```bash
# Run seed script
pnpm seed
```

Or inside the API container:

```bash
docker compose exec api pnpm seed
```

This creates:
- A dev tenant with API key: `dev-key`
- An example shared dataset: "Example News"

## API Usage

All API requests require the `X-API-Key` header with a valid tenant API key.

### Base URL

```
http://localhost:3000
```

### Authentication

Include the API key in every request:

```bash
curl -H "X-API-Key: dev-key" http://localhost:3000/v1/datasets
```

## API Endpoints

### 1. List Datasets

Get all datasets accessible to the tenant (shared + owned).

```bash
curl -H "X-API-Key: dev-key" \
  "http://localhost:3000/v1/datasets"
```

**Query Parameters:**
- `entityType`: Filter by entity type (e.g., `article.v1`)
- `tag`: Filter by tag
- `source`: Filter by source
- `mine`: `true` to show only owned datasets

**Example Response:**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "owner_tenant_id": null,
    "name": "Example News",
    "entity_type": "article.v1",
    "tags": ["news/world", "en"],
    "sources": ["example.com"],
    "schedule_cron": null,
    "extractor": "example_news_spider",
    "config": {
      "start_urls": ["https://example.com/news"],
      "article_link_selector": "a.article-link",
      "title_selector": "h1.article-title",
      "date_selector": "time.published-date",
      "content_selector": "div.article-content p"
    },
    "is_enabled": true,
    "created_at": "2024-01-01T00:00:00.000Z",
    "updated_at": "2024-01-01T00:00:00.000Z"
  }
]
```

### 2. Create Dataset

Create a new dataset owned by the tenant.

```bash
curl -X POST \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My News Site",
    "entity_type": "article.v1",
    "extractor": "example_news_spider",
    "tags": ["news/tech", "en"],
    "sources": ["example.com"],
    "config": {
      "start_urls": ["https://example.com/articles"],
      "article_link_selector": "a.article",
      "title_selector": "h1",
      "content_selector": "div.content p"
    }
  }' \
  "http://localhost:3000/v1/datasets"
```

**Example Response:**

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "owner_tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My News Site",
  "entity_type": "article.v1",
  "tags": ["news/tech", "en"],
  "sources": ["example.com"],
  "schedule_cron": null,
  "extractor": "example_news_spider",
  "config": {
    "start_urls": ["https://example.com/articles"],
    "article_link_selector": "a.article",
    "title_selector": "h1",
    "content_selector": "div.content p"
  },
  "is_enabled": true,
  "created_at": "2024-01-01T00:00:00.000Z",
  "updated_at": "2024-01-01T00:00:00.000Z"
}
```

### 3. Get Dataset

Get a specific dataset by ID.

```bash
curl -H "X-API-Key: dev-key" \
  "http://localhost:3000/v1/datasets/550e8400-e29b-41d4-a716-446655440000"
```

### 4. Update Dataset

Update a dataset (only owner can update).

```bash
curl -X PATCH \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "is_enabled": false
  }' \
  "http://localhost:3000/v1/datasets/550e8400-e29b-41d4-a716-446655440000"
```

### 5. Create Job

Trigger a scraping job for a dataset.

```bash
curl -X POST \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "datasetId": "550e8400-e29b-41d4-a716-446655440000"
  }' \
  "http://localhost:3000/v1/jobs"
```

**Example Response:**

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "QUEUED",
  "created_at": "2024-01-01T00:00:00.000Z",
  "started_at": null,
  "finished_at": null,
  "progress": 0,
  "stats": {},
  "error_message": null
}
```

### 6. Get Job Status

Check the status of a job.

```bash
curl -H "X-API-Key: dev-key" \
  "http://localhost:3000/v1/jobs/770e8400-e29b-41d4-a716-446655440002"
```

**Example Response (Running):**

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "created_at": "2024-01-01T00:00:00.000Z",
  "started_at": "2024-01-01T00:00:05.000Z",
  "finished_at": null,
  "progress": 50,
  "stats": {
    "items_scraped": 10,
    "pages_crawled": 5
  },
  "error_message": null
}
```

### 7. List Jobs

List jobs with filters and pagination.

```bash
curl -H "X-API-Key: dev-key" \
  "http://localhost:3000/v1/jobs?datasetId=550e8400-e29b-41d4-a716-446655440000&status=SUCCEEDED&limit=20"
```

**Query Parameters:**
- `datasetId`: Filter by dataset ID
- `status`: Filter by status (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELED`)
- `limit`: Number of results (max 100, default 50)
- `cursor`: Pagination cursor (format: `createdAt|id`)

**Example Response:**

```json
{
  "jobs": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "SUCCEEDED",
      "progress": 100,
      "stats": {
        "items_scraped": 25
      },
      "finished_at": "2024-01-01T00:01:00.000Z"
    }
  ],
  "nextCursor": "2024-01-01T00:00:00.000Z|770e8400-e29b-41d4-a716-446655440002"
}
```

### 8. List Items

Query scraped items with filters and cursor pagination.

```bash
curl -H "X-API-Key: dev-key" \
  "http://localhost:3000/v1/items?entityType=article.v1&tag=news/world&limit=20"
```

**Query Parameters:**
- `datasetId`: Filter by dataset ID
- `entityType`: Filter by entity type
- `tag`: Filter by tag
- `source`: Filter by source domain
- `since`: ISO timestamp (filter items observed after)
- `until`: ISO timestamp (filter items observed before)
- `limit`: Number of results (max 100, default 50)
- `cursor`: Pagination cursor (format: `observedAt|id`)

**Example Response:**

```json
{
  "items": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "entity_type": "article.v1",
      "tags": ["news/world", "en"],
      "source": "example.com",
      "url": "https://example.com/article/123",
      "canonical_url": "https://example.com/article/123",
      "hash": "abc123...",
      "published_at": "2024-01-01T00:00:00.000Z",
      "observed_at": "2024-01-01T00:01:00.000Z",
      "data": {
        "title": "Example Article",
        "contentText": "Article content here...",
        "author": "John Doe",
        "summary": "Article summary",
        "imageUrl": "https://example.com/image.jpg"
      },
      "created_at": "2024-01-01T00:01:00.000Z"
    }
  ],
  "nextCursor": "2024-01-01T00:01:00.000Z|880e8400-e29b-41d4-a716-446655440003"
}
```

### 9. Get Item

Get a specific item by ID.

```bash
curl -H "X-API-Key: dev-key" \
  "http://localhost:3000/v1/items/880e8400-e29b-41d4-a716-446655440003"
```

## Worker

The Python worker polls the database every 5 seconds (configurable via `WORKER_POLL_INTERVAL`) for `QUEUED` jobs. When a job is found:

1. Atomically claims the job (updates status to `RUNNING`)
2. Loads the dataset configuration
3. Runs the appropriate Scrapy spider
4. Upserts scraped items into Postgres
5. Updates job progress and stats
6. Marks job as `SUCCEEDED` or `FAILED`

### Supported Spiders

- **example_news_spider**: Config-driven news article scraper
  - Reads `start_urls`, `article_link_selector`, `title_selector`, `content_selector` from dataset config
  - Outputs normalized `article.v1` items

### Adding New Spiders

1. Create a new spider in `services/worker/scraper_platform/spiders/`
2. Register it in `services/worker/main.py` in the `run_spider` function
3. Update dataset `extractor` field to match spider name

## Database Schema

### Tables

- **tenants**: API key authentication
- **datasets**: Scraping configurations
- **jobs**: Job execution records
- **items**: Scraped data (normalized)

See `db/schema.ts` for TypeScript types and `db/migrations/` for SQL schema.

## Development

### Running Locally (without Docker)

```bash
# Start Postgres and Redis via Docker
docker compose up postgres redis -d

# Run API
cd apps/api
pnpm dev

# Run Worker (in another terminal)
cd services/worker
pip install -r requirements.txt
python main.py
```

### Running Migrations

```bash
# DATABASE_URL is loaded from .env file
# Run migrations
dbmate up

# Rollback last migration
dbmate rollback

# Check migration status
dbmate status
```

### Testing

```bash
# Test API endpoints
curl -H "X-API-Key: dev-key" http://localhost:3000/v1/datasets
```

## Notes

- **Port 5433**: Postgres runs on port 5433 to avoid conflicts with existing Postgres instances
- **DB Polling**: The worker uses DB polling for MVP. BullMQ is set up for future direct consumption
- **Placeholder URLs**: Example dataset uses placeholder URLs. Replace with real URLs for actual scraping
- **Multi-tenancy**: Datasets can be shared (`owner_tenant_id = NULL`) or private (owned by tenant)
- **Access Control**: Tenants can only access shared datasets and their own datasets

## License

MIT
