"""
Scrapy items for normalized data structures.
"""
import scrapy


class ArticleItem(scrapy.Item):
    """Normalized article item (entity_type: article.v1)."""
    dataset_id = scrapy.Field()
    entity_type = scrapy.Field()  # "article.v1"
    tags = scrapy.Field()  # List of strings
    source = scrapy.Field()  # Domain name
    url = scrapy.Field()
    canonical_url = scrapy.Field()  # Optional
    hash = scrapy.Field()  # For deduplication
    published_at = scrapy.Field()  # Optional ISO timestamp
    # Data fields (stored in JSONB)
    title = scrapy.Field()  # Required
    contentText = scrapy.Field()  # Required
    author = scrapy.Field()  # Optional
    summary = scrapy.Field()  # Optional
    imageUrl = scrapy.Field()  # Optional
    publishedAt = scrapy.Field()  # Optional (duplicate of published_at for data JSON)


class ProductItem(scrapy.Item):
    """Normalized product item (entity_type: product.v1)."""
    dataset_id = scrapy.Field()
    entity_type = scrapy.Field()  # "product.v1"
    tags = scrapy.Field()
    source = scrapy.Field()
    url = scrapy.Field()
    canonical_url = scrapy.Field()
    hash = scrapy.Field()
    published_at = scrapy.Field()
    # Data fields (stored in JSONB)
    name = scrapy.Field()  # Required
    price = scrapy.Field()  # Optional
    currency = scrapy.Field()  # Optional
    sku = scrapy.Field()  # Optional
    availability = scrapy.Field()  # Optional
    imageUrl = scrapy.Field()  # Optional
