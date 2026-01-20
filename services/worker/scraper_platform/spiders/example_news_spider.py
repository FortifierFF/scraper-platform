"""
Example news spider that reads configuration from dataset.config.
Config-driven spider for scraping news articles.
"""
import scrapy
import os
import psycopg2
from bs4 import BeautifulSoup
from scrapy.utils.project import get_project_settings
from scraper_platform.items import ArticleItem
from urllib.parse import urljoin, urlparse
import hashlib


class ExampleNewsSpider(scrapy.Spider):
    """
    Config-driven news spider.
    Reads configuration from dataset.config:
    - start_urls: List of URLs to start crawling
    - article_link_selector: CSS selector for article links
    - title_selector: CSS selector for article title
    - date_selector: CSS selector for publication date (optional)
    - content_selector: CSS selector for article content container
    """
    name = 'example_news_spider'
    
    def __init__(self, dataset_config=None, dataset_id=None, job_mode='full', *args, **kwargs):
        super(ExampleNewsSpider, self).__init__(*args, **kwargs)
        # Get config from parameter or settings
        if dataset_config:
            self.config = dataset_config
        else:
            settings = get_project_settings()
            self.config = settings.get('DATASET_CONFIG', {})
        
        if dataset_id:
            self.dataset_id = dataset_id
        else:
            settings = get_project_settings()
            self.dataset_id = settings.get('DATASET_ID')
        
        # Get job mode (quick_check or full)
        self.job_mode = job_mode or os.environ.get('JOB_MODE', 'full')
        
        # Get config values
        start_urls_list = self.config.get('start_urls', [])
        # Set start_urls as class attribute (Scrapy requirement)
        self.start_urls = start_urls_list if isinstance(start_urls_list, list) else [start_urls_list] if start_urls_list else []
        self.article_link_selector = self.config.get('article_link_selector', 'a')
        self.title_selector = self.config.get('title_selector', 'h1')
        self.date_selector = self.config.get('date_selector')
        self.content_selector = self.config.get('content_selector', 'p')
        
        # Initialize DB connection for checking existing articles
        self.db_conn = None
        self._init_db_connection()
        
        # Track if we should stop (found existing article)
        self.should_stop = False
        self.new_articles_found = False  # For quick_check mode
        
        self.logger.info(f'Spider initialized with {len(self.start_urls)} start URLs, mode: {self.job_mode}')
    
    def _init_db_connection(self):
        """Initialize database connection for checking existing articles."""
        try:
            database_url = os.environ.get('DATABASE_URL')
            if database_url:
                self.db_conn = psycopg2.connect(database_url)
                self.logger.info('Database connection initialized for article checking')
        except Exception as e:
            self.logger.warning(f'Failed to initialize DB connection: {e}')
    
    def _article_exists(self, article_url):
        """Check if article URL already exists in database."""
        if not self.db_conn:
            return False
        
        try:
            with self.db_conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM items WHERE dataset_id = %s AND url = %s LIMIT 1",
                    (self.dataset_id, article_url)
                )
                return cur.fetchone() is not None
        except Exception as e:
            self.logger.warning(f'Error checking article existence: {e}')
            return False
    
    def closed(self, reason):
        """Called when spider closes. Update job stats with new_articles_found."""
        if self.db_conn:
            self.db_conn.close()
        
        # Update job stats if in quick_check mode
        if self.job_mode == 'quick_check' and self.new_articles_found:
            # This will be picked up by the scheduler to trigger full scrape
            self.logger.info('Quick check found new articles - full scrape should be triggered')
        
        # Don't call super().closed() - it's handled by Scrapy's signal system
    
    def start_requests(self):
        """Generate initial requests from start_urls."""
        if not self.start_urls:
            self.logger.warning('No start URLs configured')
            return
        
        for url in self.start_urls:
            self.logger.info(f'Starting crawl from: {url}')
            yield scrapy.Request(url=url, callback=self.parse)
    
    def parse(self, response):
        """
        Parse listing page and extract article links or items directly.
        Also handles pagination for listing pages.
        Smart scraping: stops when existing article found (for full mode).
        """
        # Check if we should stop (found existing article in previous page)
        if self.should_stop:
            self.logger.info(f'Stopping pagination - existing article found earlier')
            return
        
        # If article_link_selector is provided, follow links
        if self.article_link_selector:
            article_links = response.css(self.article_link_selector)
            self.logger.info(f'Found {len(article_links)} article links on {response.url}')
            
            # Extract unique article URLs (deduplicate)
            seen_urls = set()
            new_articles_on_page = 0
            
            for link in article_links:
                href = link.attrib.get('href')
                if href:
                    # Make absolute URL
                    article_url = urljoin(response.url, href)
                    # Only follow if we haven't seen this URL
                    if article_url not in seen_urls:
                        seen_urls.add(article_url)
                        
                        # Check if article already exists in DB (for smart stopping)
                        if self._article_exists(article_url):
                            self.logger.info(f'Found existing article: {article_url[:80]}, stopping pagination')
                            self.should_stop = True
                            # In quick_check mode, if we find existing articles, we know there are no new ones
                            if self.job_mode == 'quick_check':
                                self.logger.info('Quick check: All articles on page 1 already exist')
                            break
                        else:
                            # New article found
                            new_articles_on_page += 1
                            if self.job_mode == 'quick_check':
                                self.new_articles_found = True
                            yield response.follow(article_url, self.parse_article)
            
            if new_articles_on_page > 0:
                self.logger.info(f'Found {new_articles_on_page} new articles on {response.url}')
            
            # In quick_check mode, only scrape page 1
            if self.job_mode == 'quick_check':
                self.logger.info('Quick check mode: Only scraping page 1, skipping pagination')
                return
            
            # Handle pagination - follow "Next" link (Следваща) to get all pages
            # The site has pagination from page 1 to page 16 (or more), each with 20 articles
            # We'll follow the "Следваща" (Next) link recursively until there are no more pages
            next_link = None
            
            # Method 1: Look for "Следваща" text (Next in Bulgarian)
            next_links = response.xpath('//a[contains(text(), "Следваща")]/@href').getall()
            if next_links:
                next_link = next_links[0]
            else:
                # Method 2: Look for link with "next" class
                next_links = response.css('a.next::attr(href)').getall()
                if next_links:
                    next_link = next_links[0]
                else:
                    # Method 3: Find current page number and follow next one
                    # Extract current page from URL
                    current_page = 1
                    if '?page=' in response.url:
                        try:
                            current_page = int(response.url.split('?page=')[1].split('&')[0])
                        except:
                            pass
                    
                    # Look for link to next page number
                    next_page_num = current_page + 1
                    next_page_link = response.xpath(f'//a[@href and contains(@href, "page={next_page_num}")]/@href').get()
                    if next_page_link:
                        next_link = next_page_link
            
            # Don't follow pagination if we should stop (found existing article in full mode)
            if self.should_stop:
                self.logger.info('Stopping pagination - existing article found, no need to continue')
                return
            
            if next_link:
                next_url = urljoin(response.url, next_link)
                # Check if we've already visited this page (avoid infinite loops)
                if not hasattr(self, '_visited_pages'):
                    self._visited_pages = set()
                
                if next_url not in self._visited_pages and not self.should_stop:
                    self._visited_pages.add(next_url)
                    self.logger.info(f'Following pagination to: {next_url}')
                    yield response.follow(next_url, self.parse, errback=self.handle_pagination_error)
                else:
                    self.logger.info(f'Already visited {next_url}, stopping pagination')
            else:
                self.logger.info(f'No more pages found. Finished pagination at: {response.url}')
    
    def handle_pagination_error(self, failure):
        """Handle errors when following pagination links (e.g., 400, 404)."""
        request = failure.request
        self.logger.warning(f'Failed to follow pagination link {request.url}: {failure.value}')
        # Don't stop pagination on errors - let Scrapy's retry middleware handle it
        # If it's a real 404 after retries, Scrapy will handle it
        pass
    
    def parse_item_from_container(self, container, page_url):
        """Parse a single item from a container element."""
        # Extract title
        title_elem = container.select_one(self.title_selector)
        title = title_elem.get_text(strip=True) if title_elem else None
        
        if not title:
            return
        
        # Extract content
        content_elems = container.select(self.content_selector)
        content_text = ' '.join([elem.get_text(strip=True) for elem in content_elems])
        
        if not content_text:
            return
        
        # Build item (similar to parse_article but for container)
        url_hash = hashlib.sha256(f"{page_url}#{title}".encode()).hexdigest()
        source = urlparse(page_url).netloc
        
        item = ArticleItem()
        item['dataset_id'] = self.dataset_id
        item['entity_type'] = 'article.v1'
        item['tags'] = []
        item['source'] = source
        item['url'] = page_url  # Use page URL since we don't have individual URLs
        item['canonical_url'] = None
        item['hash'] = url_hash
        item['published_at'] = None
        item['title'] = title
        item['contentText'] = content_text
        item['author'] = None
        item['summary'] = content_text[:200] if len(content_text) > 200 else content_text
        item['imageUrl'] = None
        item['publishedAt'] = None
        
        yield item
    
    def parse_article(self, response):
        """
        Parse individual article page and extract structured data.
        """
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title_elem = soup.select_one(self.title_selector)
        title = title_elem.get_text(strip=True) if title_elem else None
        
        if not title:
            self.logger.warning(f'No title found for {response.url}, skipping')
            return
        
        # Extract content
        content_elems = soup.select(self.content_selector)
        content_text = ' '.join([elem.get_text(strip=True) for elem in content_elems])
        
        if not content_text:
            self.logger.warning(f'No content found for {response.url}, skipping')
            return
        
        # Extract publication date (optional)
        published_at = None
        if self.date_selector:
            date_elem = soup.select_one(self.date_selector)
            if date_elem:
                # Try to get datetime attribute or text
                datetime_attr = date_elem.get('datetime')
                if datetime_attr:
                    published_at = datetime_attr
                else:
                    published_at = date_elem.get_text(strip=True)
        
        # Extract author (try common selectors)
        author = None
        author_selectors = ['[rel="author"]', '.author', '.byline', '[itemprop="author"]']
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                author = author_elem.get_text(strip=True)
                break
        
        # Extract summary (try meta description or first paragraph)
        summary = None
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            summary = meta_desc.get('content', '').strip()
        else:
            first_p = soup.select_one('p')
            if first_p:
                summary = first_p.get_text(strip=True)[:200]  # First 200 chars
        
        # Extract image (try og:image or first img)
        image_url = None
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
            image_url = og_image.get('content')
        else:
            first_img = soup.select_one('img')
            if first_img:
                image_url = urljoin(response.url, first_img.get('src', ''))
        
        # Get canonical URL
        canonical_url = None
        canonical_link = soup.find('link', attrs={'rel': 'canonical'})
        if canonical_link:
            canonical_url = canonical_link.get('href')
        
        # Generate hash for deduplication
        url_hash = hashlib.sha256(response.url.encode()).hexdigest()
        
        # Extract source domain
        source = urlparse(response.url).netloc
        
        # Build item
        item = ArticleItem()
        item['dataset_id'] = self.dataset_id
        item['entity_type'] = 'article.v1'
        item['tags'] = []  # Can be enhanced with config
        item['source'] = source
        item['url'] = response.url
        item['canonical_url'] = canonical_url
        item['hash'] = url_hash
        item['published_at'] = published_at
        # Data fields
        item['title'] = title
        item['contentText'] = content_text
        item['author'] = author
        item['summary'] = summary
        item['imageUrl'] = image_url
        item['publishedAt'] = published_at  # Duplicate for data JSON
        
        yield item
