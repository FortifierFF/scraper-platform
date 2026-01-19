"""
Scrapy settings for scraper_platform project.
"""
BOT_NAME = 'scraper_platform'

SPIDER_MODULES = ['scraper_platform.spiders']
NEWSPIDER_MODULE = 'scraper_platform.spiders'

# Obey robots.txt (set to False for testing, but be respectful)
# Note: Some sites block via robots.txt, but we respect rate limits
ROBOTSTXT_OBEY = False

# Configure pipelines
# Order matters: ImageDownloadPipeline runs first (lower number = earlier)
ITEM_PIPELINES = {
    'scraper_platform.pipelines.ImageDownloadPipeline': 200,  # Download images first
    'scraper_platform.pipelines.PostgresPipeline': 300,  # Then save to DB
}

# Image storage settings
IMAGES_STORE = '/app/data/images'  # Base directory for images

# Configure delays for requests - be very respectful and conservative
# Target: ~5-10 requests/minute (0.08-0.17 requests/second) to avoid rate limiting
DOWNLOAD_DELAY = 6.0  # Minimum 6 seconds between requests (very conservative)
RANDOMIZE_DOWNLOAD_DELAY = 0.5  # More randomization to avoid patterns (0.5 = ±50% = 3-9 sec range)

# Auto-throttle - conservative settings to avoid getting blocked
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0  # Start with 2 second delay
AUTOTHROTTLE_MAX_DELAY = 5.0  # Max 5 seconds delay if server is slow or returning errors
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0  # Only 1 concurrent request at a time

# Retry settings for temporary errors (400, 404, 500, etc.)
RETRY_ENABLED = True
RETRY_TIMES = 3  # Retry up to 3 times
RETRY_HTTP_CODES = [400, 403, 404, 408, 429, 500, 502, 503, 504]  # Retry on these codes
RETRY_PRIORITY_ADJUST = -1

# Logging
LOG_LEVEL = 'INFO'
