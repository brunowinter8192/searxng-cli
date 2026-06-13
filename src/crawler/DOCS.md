# Crawler Module

Full-site BFS discovery + capture-pipeline scrape step. Used by the capture-and-index workflow for offline documentation indexing.

## pipe_scraper.py (183 LOC)

**Purpose:** Validated capture-pipeline scrape step. Crawls a URL list to raw markdown files with Scrapy-style per-domain pacing (delay-gate + jitter + concurrency cap). Standalone module — NOT a CLI subcommand of `cli.py`.
**Reads:** URL list (from `--url-file` flag or caller-supplied list).
**Writes:** Per-URL `.md` files to `--output-dir` (each with `<!-- source: URL -->` header); `/tmp/<domain>_scrape_report.md` (per-URL outcome table); short summary line to stdout.
**Called by:** capture-and-index skill Phase 2 (`python -m src.crawler.pipe_scraper --url-file <list> --output-dir <dir>`); importable as `scrape_urls_workflow()` for direct programmatic use.
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, DefaultMarkdownGenerator)

Pacing: Scrapy per-domain gate — `lastseen` dict + `asyncio.Lock` (serializes starts) + `asyncio.Semaphore(8)` cap (per domain). `DOWNLOAD_DELAY=1.0s`, jitter=`uniform(0.5×,1.5×)` → ~1 req/s start rate per domain. No batch loop, no inter-batch sleep, no retry/backoff. Validated: 316/316 ok, 0×429, 319s.

### CLI

| Flag | Default | Description |
|---|---|---|
| `--url-file` | required | Text file with URLs (one per line) |
| `--output-dir` | required | Directory to write per-URL markdown files |
| `--download-delay` | 1.0 | Scrapy per-domain base delay in seconds; jitter = uniform(0.5×, 1.5×) |
| `--concurrency-per-domain` | 8 | Per-domain in-flight request cap |

```bash
./venv/bin/python -m src.crawler.pipe_scraper --url-file urls.txt --output-dir ./output
./venv/bin/python -m src.crawler.pipe_scraper --url-file urls.txt --output-dir ./output --download-delay 1.5 --concurrency-per-domain 4
```

---

## crawl_site.py (353 LOC)

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

