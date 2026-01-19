# Quick Setup Guide

## 1. Create .env File

Create a `.env` file in the root directory with the following content:

```env
# Database Configuration
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

## 2. Install dbmate (for migrations)

### macOS
```bash
brew install dbmate
```

### Linux
```bash
curl -fsSL https://github.com/amacneil/dbmate/releases/latest/download/dbmate-linux-amd64 -o /usr/local/bin/dbmate
chmod +x /usr/local/bin/dbmate
```

### Windows
Download from: https://github.com/amacneil/dbmate/releases

## 3. Start Services

```bash
# Install dependencies
pnpm install

# Start Docker services
docker compose up --build -d

# Wait for services to be healthy, then run migrations
# DATABASE_URL is loaded from .env file
dbmate up

# Seed database
pnpm seed
```

## 4. Verify Setup

```bash
# Test API
curl -H "X-API-Key: dev-key" http://localhost:3000/v1/datasets
```

You should see the "Example News" dataset in the response.
