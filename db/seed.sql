-- Seed script: Create dev tenant and example dataset
INSERT INTO tenants (name, api_key, is_enabled)
VALUES ('dev', 'dev-key', TRUE)
ON CONFLICT (api_key) DO NOTHING;

INSERT INTO datasets (owner_tenant_id, name, entity_type, extractor, tags, sources, config, is_enabled)
VALUES (
  NULL,
  'Example News',
  'article.v1',
  'example_news_spider',
  ARRAY['news/world', 'en'],
  ARRAY['example.com'],
  '{"start_urls": ["https://example.com/news"], "article_link_selector": "a.article-link", "title_selector": "h1.article-title", "date_selector": "time.published-date", "content_selector": "div.article-content p"}'::jsonb,
  TRUE
)
ON CONFLICT DO NOTHING;
