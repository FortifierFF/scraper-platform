"""
Main worker process that polls the database for QUEUED jobs
and executes Scrapy spiders to scrape data.
"""
import os
import time
import sys
import json
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Add the worker directory to Python path so Scrapy can find the project
worker_dir = os.path.dirname(os.path.abspath(__file__))
if worker_dir not in sys.path:
    sys.path.insert(0, worker_dir)

# Import our spider
from scraper_platform.spiders.example_news_spider import ExampleNewsSpider

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError('DATABASE_URL environment variable is required')

# Polling interval in seconds
POLL_INTERVAL = int(os.getenv('WORKER_POLL_INTERVAL', '5'))


def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL)


def claim_job(conn, job_id):
    """
    Atomically claim a job by updating its status to RUNNING.
    Returns True if successfully claimed, False otherwise.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'RUNNING', started_at = now()
            WHERE id = %s AND status = 'QUEUED'
            RETURNING id
            """,
            (job_id,)
        )
        conn.commit()
        return cur.rowcount == 1


def update_job_progress(conn, job_id, progress, stats=None):
    """Update job progress and stats."""
    with conn.cursor() as cur:
        if stats:
            cur.execute(
                """
                UPDATE jobs
                SET progress = %s, stats = %s
                WHERE id = %s
                """,
                (progress, psycopg2.extras.Json(stats or {}), job_id)
            )
        else:
            cur.execute(
                """
                UPDATE jobs
                SET progress = %s
                WHERE id = %s
                """,
                (progress, job_id)
            )
        conn.commit()


def mark_job_succeeded(conn, job_id, stats=None):
    """Mark job as succeeded and handle auto-trigger for full scrape."""
    with conn.cursor() as cur:
        # Get current stats to preserve mode
        cur.execute("SELECT stats FROM jobs WHERE id = %s", (job_id,))
        result = cur.fetchone()
        current_stats = result[0] if result else {}
        
        # Merge stats (preserve mode and other existing fields)
        if stats:
            merged_stats = {**current_stats, **stats}
        else:
            merged_stats = current_stats
        
        # Update job with merged stats
        cur.execute(
            """
            UPDATE jobs
            SET status = 'SUCCEEDED', finished_at = now(), progress = 100, stats = %s
            WHERE id = %s
            """,
            (psycopg2.extras.Json(merged_stats), job_id)
        )
        conn.commit()
        
        # If quick_check found new articles, trigger full scrape
        if merged_stats.get('mode') == 'quick_check' and merged_stats.get('new_articles_found'):
            try:
                # Get dataset_id and tenant_id
                cur.execute("SELECT dataset_id, tenant_id FROM jobs WHERE id = %s", (job_id,))
                result = cur.fetchone()
                if result:
                    dataset_id, tenant_id = result
                    # Create full scrape job
                    cur.execute("""
                        INSERT INTO jobs (dataset_id, tenant_id, status, progress, stats)
                        VALUES (%s, %s, 'QUEUED', 0, '{"mode": "full"}'::jsonb)
                        RETURNING id
                    """, (dataset_id, tenant_id))
                    full_job_id = cur.fetchone()[0]
                    conn.commit()
                    print(f'Quick check found new articles, created full scrape job: {full_job_id}')
            except Exception as e:
                conn.rollback()
                print(f'Error creating full scrape job: {e}')


def mark_job_failed(conn, job_id, error_message):
    """Mark job as failed."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'FAILED', finished_at = now(), error_message = %s
            WHERE id = %s
            """,
            (error_message, job_id)
        )
        conn.commit()


def get_dataset(conn, dataset_id):
    """Get dataset by ID. Must be enabled."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM datasets
            WHERE id = %s AND is_enabled = TRUE
            """,
            (dataset_id,)
        )
        return cur.fetchone()


def get_queued_jobs(conn, limit=10):
    """Get QUEUED jobs ordered by created_at."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, dataset_id
            FROM jobs
            WHERE status = 'QUEUED'
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (limit,)
        )
        return cur.fetchall()


def get_job_mode(conn, job_id):
    """Get job mode from stats JSONB."""
    cur = conn.cursor()
    cur.execute("SELECT stats->>'mode' as mode FROM jobs WHERE id = %s", (job_id,))
    result = cur.fetchone()
    cur.close()
    return result[0] if result and result[0] else 'full'  # Default to 'full'


def run_spider(dataset, job_id, job_mode='full'):
    """
    Run the appropriate Scrapy spider for the dataset.
    Returns stats dictionary.
    
    Args:
        dataset: Dataset configuration
        job_id: Job ID
        job_mode: 'quick_check' (only page 1) or 'full' (all pages until existing article found)
    """
    # Get spider name from dataset extractor field
    spider_name = dataset['extractor']
    
    # For MVP, we support example_news_spider
    if spider_name == 'example_news_spider':
        spider_class = ExampleNewsSpider
    else:
        raise ValueError(f'Unknown spider: {spider_name}')
    
    # Configure Scrapy settings
    # Set SCRAPY_SETTINGS_MODULE to ensure settings.py is loaded
    os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'scraper_platform.settings')
    # Also set DATABASE_URL in environment so pipeline can access it
    os.environ['DATABASE_URL'] = DATABASE_URL
    os.environ['DATASET_ID'] = dataset['id']
    os.environ['JOB_ID'] = job_id
    os.environ['JOB_MODE'] = job_mode  # Pass mode to spider
    
    settings = get_project_settings()
    settings.set('DATASET_ID', dataset['id'])
    settings.set('JOB_ID', job_id)
    settings.set('JOB_MODE', job_mode)
    settings.set('DATASET_CONFIG', dataset['config'])
    settings.set('DATABASE_URL', DATABASE_URL)
    # Explicitly enable pipeline
    settings.set('ITEM_PIPELINES', {
        'scraper_platform.pipelines.ImageDownloadPipeline': 200,
        'scraper_platform.pipelines.PostgresPipeline': 300,
    })
    
    # Run crawler (blocking)
    process = CrawlerProcess(settings)
    # Pass config and mode to spider via constructor
    process.crawl(spider_class, dataset_config=dataset['config'], dataset_id=dataset['id'], job_mode=job_mode)
    process.start()  # This blocks until crawling is done
    
    # Get crawler stats
    crawler_stats = process.crawler.stats.get_stats()
    
    # Get stats from the crawler
    stats = {
        'items_scraped': crawler_stats.get('item_scraped_count', 0),
        'pages_crawled': crawler_stats.get('response_received_count', 0),
    }
    
    return stats


def process_job(conn, job):
    """Process a single job."""
    job_id = job['id']
    dataset_id = job['dataset_id']
    
    print(f'Processing job {job_id} for dataset {dataset_id}')
    
    try:
        # Try to claim the job
        if not claim_job(conn, job_id):
            print(f'Job {job_id} was already claimed by another worker')
            return
        
        # Get dataset
        dataset = get_dataset(conn, dataset_id)
        if not dataset:
            mark_job_failed(conn, job_id, f'Dataset {dataset_id} not found or disabled')
            return
        
        # Get job mode from stats
        job_mode = get_job_mode(conn, job_id)
        print(f'Job mode: {job_mode}')
        
        # Update progress
        update_job_progress(conn, job_id, 10, {'status': 'starting_spider', 'mode': job_mode})
        
        # Run spider with mode
        stats = run_spider(dataset, job_id, job_mode)
        
        # Check if quick_check found new articles
        # If items were scraped, new articles were found
        if job_mode == 'quick_check':
            if stats.get('items_scraped', 0) > 0:
                stats['new_articles_found'] = True
                print(f'Quick check found {stats["items_scraped"]} new articles')
            else:
                stats['new_articles_found'] = False
                print('Quick check: No new articles found')
        
        # Mark as succeeded (will auto-trigger full scrape if new articles found)
        mark_job_succeeded(conn, job_id, stats)
        print(f'Job {job_id} completed successfully')
        
    except Exception as e:
        error_msg = str(e)
        print(f'Job {job_id} failed: {error_msg}')
        mark_job_failed(conn, job_id, error_msg)


def main():
    """Main worker loop."""
    print('Starting worker...')
    print(f'Polling interval: {POLL_INTERVAL} seconds')
    
    while True:
        try:
            conn = get_db_connection()
            
            # Get queued jobs
            jobs = get_queued_jobs(conn, limit=5)
            
            if jobs:
                print(f'Found {len(jobs)} queued job(s)')
                for job in jobs:
                    process_job(conn, job)
            else:
                print('No queued jobs, waiting...')
            
            conn.close()
            
        except Exception as e:
            print(f'Error in worker loop: {e}')
            import traceback
            traceback.print_exc()
        
        # Wait before next poll
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nWorker stopped by user')
        sys.exit(0)
