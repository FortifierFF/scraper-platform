"""
Scrapy pipelines for processing items.
"""
import hashlib
import json
import os
import psycopg2
from psycopg2.extras import Json
from urllib.parse import urlparse, urljoin
from scrapy.utils.project import get_project_settings
import requests
from pathlib import Path
from scraper_platform.storage import get_image_storage


class PostgresPipeline:
    """
    Pipeline that upserts items into Postgres.
    Uses INSERT ... ON CONFLICT (dataset_id, url) DO UPDATE.
    """
    
    def __init__(self, crawler=None):
        self.crawler = crawler
        self.settings = None
        self.dataset_id = None
        self.database_url = None
        self.conn = None
        self.items_count = 0
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler (Scrapy's standard way)."""
        print('PostgresPipeline: from_crawler called')
        instance = cls(crawler)
        print(f'PostgresPipeline: Instance created, crawler={crawler is not None}')
        return instance
    
    def _get_settings(self):
        """Lazy load settings when needed."""
        if self.settings is None:
            if self.crawler:
                self.settings = self.crawler.settings
            else:
                self.settings = get_project_settings()
            self.dataset_id = self.settings.get('DATASET_ID') or os.environ.get('DATASET_ID')
            self.database_url = self.settings.get('DATABASE_URL') or os.environ.get('DATABASE_URL')
    
    def open_spider(self, spider=None):
        """Open database connection when spider starts."""
        print('PostgresPipeline: open_spider called')
        self._get_settings()
        try:
            if not self.database_url:
                raise ValueError('DATABASE_URL not set in settings')
            print(f'PostgresPipeline: Connecting to database... (dataset: {self.dataset_id})')
            self.conn = psycopg2.connect(self.database_url)
            print(f'PostgresPipeline: Connected to database for dataset {self.dataset_id}')
        except Exception as e:
            print(f'PostgresPipeline: Failed to connect to database: {e}')
            import traceback
            traceback.print_exc()
            raise
    
    def close_spider(self, spider=None):
        """Close database connection when spider finishes."""
        if self.conn:
            self.conn.close()
        print(f'PostgresPipeline: Processed {self.items_count} items')
    
    def process_item(self, item, spider=None):
        """Process and upsert item into database."""
        # Ensure connection is open
        if not self.conn:
            self._get_settings()
            if not self.conn:
                # Try to connect if not already connected
                self.open_spider(spider)
        
        # Double-check connection
        if not self.conn:
            error_msg = 'Database connection not available'
            if spider:
                spider.logger.error(error_msg)
            else:
                print(error_msg)
            raise Exception(error_msg)
        
        # Extract fields
        url = item.get('url')
        if not url:
            if spider:
                spider.logger.warning('Item missing URL, skipping')
            else:
                print('Item missing URL, skipping')
            return item
        
        # Generate hash for deduplication (using URL)
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        # Extract source from URL
        source = item.get('source') or urlparse(url).netloc
        
        # Build data JSONB object (all fields except metadata)
        data = {}
        for key, value in item.items():
            # Skip metadata fields that go into separate columns
            if key not in [
                'dataset_id', 'entity_type', 'tags', 'source', 'url',
                'canonical_url', 'hash', 'published_at'
            ]:
                data[key] = value
        
        # Get entity type
        entity_type = item.get('entity_type', 'article.v1')
        
        # Get tags (ensure it's a list)
        tags = item.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
        
        # Get published_at (can be None or a time string like "00:01")
        # If it's just a time, we'll store it as None (full date needed for TIMESTAMPTZ)
        published_at = item.get('published_at')
        if published_at and len(str(published_at)) < 10:  # Just time, not full date
            published_at = None
        
        # Upsert into database with proper error handling
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO items (
                        dataset_id, entity_type, tags, source, url,
                        canonical_url, hash, published_at, data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (dataset_id, url)
                    DO UPDATE SET
                        observed_at = now(),
                        data = EXCLUDED.data,
                        hash = EXCLUDED.hash,
                        canonical_url = EXCLUDED.canonical_url,
                        published_at = EXCLUDED.published_at,
                        tags = EXCLUDED.tags
                    """,
                    (
                        self.dataset_id,
                        entity_type,
                        tags,
                        source,
                        url,
                        item.get('canonical_url'),
                        url_hash,
                        published_at,
                        Json(data),
                    )
                )
                # Check if this was a new insert (not an update)
                # ON CONFLICT means it was an update, so we check if row was actually inserted
                # For simplicity, we'll track in spider if new articles are found
                self.conn.commit()
                if spider:
                    spider.logger.debug(f'Successfully saved item: {url[:80]}')
                    # Mark that we found a new article (for quick_check mode)
                    if hasattr(spider, 'new_articles_found'):
                        spider.new_articles_found = True
        except Exception as e:
            # Rollback on error to allow future transactions
            self.conn.rollback()
            error_msg = f'Error inserting item {url}: {e}'
            if spider:
                spider.logger.error(error_msg)
                import traceback
                spider.logger.error(traceback.format_exc())
            else:
                print(error_msg)
                import traceback
                traceback.print_exc()
            # Re-raise to let Scrapy handle it
            raise
        
        self.items_count += 1
        if self.items_count % 10 == 0:
            msg = f'PostgresPipeline: Processed {self.items_count} items so far'
            if spider:
                spider.logger.info(msg)
            else:
                print(msg)
        return item


class ImageDownloadPipeline:
    """
    Pipeline that downloads images from article imageUrl and saves them.
    Supports local filesystem and S3-compatible cloud storage.
    """
    
    def __init__(self, crawler=None):
        self.crawler = crawler
        self.settings = None
        self.storage = None
        self.dataset_id = None
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler."""
        return cls(crawler)
    
    def _get_settings(self):
        """Lazy load settings when needed."""
        if self.settings is None:
            if self.crawler:
                self.settings = self.crawler.settings
            else:
                self.settings = get_project_settings()
            self.dataset_id = self.settings.get('DATASET_ID') or os.environ.get('DATASET_ID')
            # Initialize storage backend (spider might be None during init)
            try:
                self.storage = get_image_storage()
                storage_type = os.environ.get('IMAGE_STORAGE_TYPE', 'local')
                print(f'ImageDownloadPipeline: Using {storage_type} storage')
            except Exception as e:
                error_msg = f'Failed to initialize image storage: {e}'
                print(error_msg)
                raise
    
    def open_spider(self, spider=None):
        """Initialize storage when spider starts."""
        self._get_settings()
        storage_type = os.environ.get('IMAGE_STORAGE_TYPE', 'local')
        if spider:
            spider.logger.info(f'ImageDownloadPipeline: Initialized {storage_type} storage backend')
        else:
            print(f'ImageDownloadPipeline: Initialized {storage_type} storage backend')
    
    def process_item(self, item, spider=None):
        """Download image if imageUrl is present."""
        image_url = item.get('imageUrl')
        if not image_url:
            # No image to download
            return item
        
        self._get_settings()
        
        if not self.storage:
            if spider:
                spider.logger.warning('Image storage not initialized, skipping image download')
            return item
        
        try:
            parsed_url = urlparse(image_url)
            # Get file extension from URL
            ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                ext = '.jpg'  # Default to jpg if unknown
            
            # Check if image already exists
            if self.storage.image_exists(image_url, self.dataset_id, ext):
                if spider:
                    spider.logger.debug(f'Image already exists in storage: {image_url[:80]}')
                # Get the storage path (storage backend will return it)
                # For now, we'll still download to get the path, but storage will skip
                pass
            
            # Download image
            if spider:
                spider.logger.info(f'Downloading image: {image_url[:80]}')
            
            response = requests.get(image_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            # Save using storage backend
            storage_path = self.storage.save_image(
                image_url, 
                self.dataset_id, 
                response.content, 
                ext
            )
            
            if storage_path:
                # Update item with storage path
                item['imageLocalPath'] = storage_path
                if spider:
                    spider.logger.info(f'Saved image to storage: {storage_path} ({len(response.content)} bytes)')
            else:
                if spider:
                    spider.logger.warning(f'Failed to save image to storage: {image_url[:80]}')
            
        except Exception as e:
            # Don't fail the item if image download fails
            error_msg = f'Failed to download/save image {image_url}: {e}'
            if spider:
                spider.logger.warning(error_msg)
            else:
                print(error_msg)
            # Keep original imageUrl in case download failed
            # item['imageUrl'] remains unchanged
        
        return item
