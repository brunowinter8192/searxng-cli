# Crawler Module

Full-site crawl and URL discovery CLI tools. Used by the `/crawl-site` command pipeline for offline documentation indexing.

## crawl_site.py (325 LOC)

**Purpose:** Discovery engine + content crawl. Provides `discover_urls_playwright()` (Playwright-per-page BFS, single discovery method) and `crawl_urls()` (parallel content crawl via `arun_many()`). Saves pages as markdown files with `<!-- source: URL -->` header.
**Called by:** `explore_site.py` (imports `discover_urls_playwright` + constants); `crawl_site_workflow` is the standalone CLI entry point.
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

## explore_site.py (152 LOC)

**Purpose:** URL discovery workflow — backend for `searxng-cli explore_site` and the `/crawl-site` pipeline. Wraps `discover_urls_playwright()` with redirect detection, file I/O, append dedup, and saturation logging. Returns `(urls, stop_reason, output_path)`.
**Called by:** `cli.py` (`explore_site_workflow`); standalone `__main__`.
**Calls out:** `src.crawler.crawl_site` (discover_urls_playwright, defaults), `src.crawler.filter_urls` (match_any), `requests` (redirect resolution)

### CLI

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | required | Seed URL to explore |
| `--max-pages` | 200 | Max pages to discover |
| `--depth` | 10 | Max BFS depth |
| `--output` | `/tmp/explore_<domain>_urls.txt` | Output file path |
| `--append` | false | Append to output file instead of overwrite |
| `--include-patterns` | None | Comma-separated URL substrings to include |
| `--exclude-patterns` | None | Comma-separated URL substrings to exclude |
| `--delay` | 3.0 | `delay_before_return_html` in seconds |
| `--page-timeout` | 15000 | Page load timeout in ms |
| `--concurrency` | 1 | Discovery concurrency (>1 risks WAF 429, max recommended: 10) |
| `--stealth` | false | `enable_stealth` + `UndetectedAdapter` to reduce 429s |

```bash
./venv/bin/python -m src.crawler.explore_site --url "https://docs.example.com"
./venv/bin/python -m src.crawler.explore_site --url "https://docs.example.com" --max-pages 400 --append
./venv/bin/python -m src.crawler.explore_site --url "https://docs.github.com/de/rest" --include-patterns "/de/rest/"
```

## filter_urls.py (62 LOC)

**Purpose:** In-place URL list filter. Reads a URL-per-line file, drops lines matching any fnmatch glob pattern in `--exclude-patterns`, atomically rewrites the file. `--dry-run` previews without touching the file. Provides `match_any(url, patterns_str) -> bool` — fnmatch-based glob-match helper (imported by `explore_site.py`).
**Called by:** `cli.py` (`filter_urls_workflow`); `explore_site.py` imports `match_any`.
**Calls out:** stdlib only (`fnmatch`, `tempfile`, `os`)

### CLI

| Flag | Default | Description |
|------|---------|-------------|
| `file` | required | Path to URL list file (one URL per line) |
| `--exclude-patterns` | required | Comma-separated fnmatch glob patterns to drop |
| `--dry-run` | false | Preview mode — print dropped URLs, do not modify file |

```bash
searxng-cli filter_urls /tmp/example_urls.txt --exclude-patterns "*/genindex.html,*/_modules/*" --dry-run
searxng-cli filter_urls /tmp/example_urls.txt --exclude-patterns "*/genindex.html,*/_modules/*"
```
