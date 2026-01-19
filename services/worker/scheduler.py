"""
Scheduler module for automatically creating quick_check jobs.
Runs in a separate thread to periodically check for new articles.
"""
import os
import time
import threading
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
SCHEDULER_ENABLED = os.getenv('SCHEDULER_ENABLED', 'true').lower() == 'true'
QUICK_CHECK_INTERVAL = int(os.getenv('QUICK_CHECK_INTERVAL', '600'))  # Default: 10 minutes (600 seconds)


def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL)


def get_enabled_datasets(conn):
    """Get all enabled datasets that should be checked."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name 
        FROM datasets 
        WHERE is_enabled = TRUE
        ORDER BY created_at
    """)
    datasets = cur.fetchall()
    cur.close()
    return datasets


def create_quick_check_job(conn, dataset_id, tenant_id):
    """Create a quick_check job for a dataset."""
    cur = conn.cursor()
    try:
        # Check if there's already a QUEUED quick_check job for this dataset
        cur.execute("""
            SELECT id FROM jobs 
            WHERE dataset_id = %s 
            AND status = 'QUEUED' 
            AND stats->>'mode' = 'quick_check'
            LIMIT 1
        """, (dataset_id,))
        existing = cur.fetchone()
        
        if existing:
            # Job already queued, skip
            cur.close()
            return None
        
        # Create new quick_check job
        cur.execute("""
            INSERT INTO jobs (dataset_id, tenant_id, status, progress, stats)
            VALUES (%s, %s, 'QUEUED', 0, '{"mode": "quick_check"}'::jsonb)
            RETURNING id
        """, (dataset_id, tenant_id))
        job_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return job_id
    except Exception as e:
        conn.rollback()
        cur.close()
        print(f'Error creating quick_check job: {e}')
        return None


# Note: Quick check result handling is now done in main.py mark_job_succeeded()
# This function is kept for reference but not actively used


def scheduler_loop():
    """Main scheduler loop that runs every QUICK_CHECK_INTERVAL seconds."""
    if not SCHEDULER_ENABLED:
        print('Scheduler is disabled (SCHEDULER_ENABLED=false)')
        return
    
    print(f'Scheduler started: Creating quick_check jobs every {QUICK_CHECK_INTERVAL} seconds')
    
    while True:
        try:
            conn = get_db_connection()
            
            # Get all enabled datasets
            datasets = get_enabled_datasets(conn)
            
            # Get default tenant (for now, use the first tenant)
            # In production, you might want to use a system tenant
            cur = conn.cursor()
            cur.execute("SELECT id FROM tenants WHERE is_enabled = TRUE LIMIT 1")
            tenant_result = cur.fetchone()
            cur.close()
            
            if not tenant_result:
                print('No enabled tenant found, skipping scheduler cycle')
                conn.close()
                time.sleep(QUICK_CHECK_INTERVAL)
                continue
            
            tenant_id = tenant_result[0]
            
            # Create quick_check jobs for each dataset
            for dataset_id, dataset_name in datasets:
                job_id = create_quick_check_job(conn, dataset_id, tenant_id)
                if job_id:
                    print(f'Created quick_check job {job_id} for dataset: {dataset_name}')
            
            conn.close()
            
            # Wait before next cycle
            time.sleep(QUICK_CHECK_INTERVAL)
            
        except Exception as e:
            print(f'Scheduler error: {e}')
            time.sleep(60)  # Wait 1 minute on error before retrying


def start_scheduler():
    """Start scheduler in a background thread."""
    if not SCHEDULER_ENABLED:
        return
    
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    print('Scheduler thread started')
