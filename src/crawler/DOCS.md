# Crawler Module

Full-site crawl pipeline. Used by the capture-and-index workflow for offline documentation indexing.

## crawl_site.py (325 LOC)

**Purpose:** Discovery engine + content crawl. Provides `discover_urls_playwright()` (Playwright-per-page BFS, single discovery method) and `crawl_urls()` (parallel content crawl via `arun_many()`). Saves pages as markdown files with `<!-- source: URL -->` header.
**Called by:** `crawl_site_workflow` (standalone CLI entry point); `discover_urls_playwright` called internally by `crawl_site_workflow` only.
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, UndetectedAdapter, AsyncPlaywrightCrawlerStrategy, DefaultMarkdownGenerator, SemaphoreDispatcher), `src.scraper.scrape_url.is_garbage_content`

### Key functions

- `discover_urls_playwright(seed, include_patterns, exclude_patterns, max_pages, max_depth, delay_s, page_timeout_ms, concurrency, stealth)` → `(list[str], dict)` — manual BFS: `crawler.arun()` per URL, links from `result.links.internal` (post-JS DOM). 429 back-off-once-then-stop. Returns stop_reason: `"frontier_exhausted"` | `"max_pages_reached"` | `"429_persistent"`.
- `crawl_urls(urls)` — parallel content crawl, `SemaphoreDispatcher(max_session_permit=10)`, `wait_until="networkidle"`.
- `normalize_url(url)` — strips query/fragment/@version/trailing slash; used by BFS visited-set dedup.

### CLI

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | required | Seed URL to crawl |
| `--output-dir` | required | Directory to save markdown files |
| `--depth` | 3 | Max BFS depth |
| `--max-pages` | 100 | Max discovery pages |
| `--include-patterns` | None | Comma-separated URL substrings to include |
| `--exclude-patterns` | None | Comma-separated URL substrings to exclude |
| `--url-file` | None | Pre-built URL list — skips discovery entirely |
| `--delay` | 3.0 | `delay_before_return_html` in seconds |
| `--page-timeout` | 15000 | Page load timeout in ms |
| `--concurrency` | 1 | Discovery concurrency (>1 risks WAF 429, max recommended: 10) |
| `--stealth` | false | `enable_stealth` + `UndetectedAdapter` to reduce 429s |

```bash
./venv/bin/python -m src.crawler.crawl_site --url "https://docs.example.com" --output-dir "./output"
./venv/bin/python -m src.crawler.crawl_site --url "https://docs.example.com" --url-file urls_filtered.txt --output-dir "./output"
```

