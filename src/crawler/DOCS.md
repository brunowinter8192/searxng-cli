# Crawler Module

Full-site crawl and URL discovery CLI tools. Used by the `/crawl-site` command pipeline for offline documentation indexing.

## crawl_site.py

**Purpose:** Full website crawl with markdown export. Supports auto-detection cascade (sitemap → prefetch → BFS with SPA auto-detection), direct URL file input, and parallel crawl via `arun_many()` with `SemaphoreDispatcher(concurrency=10)`. Saves pages as markdown files with `<!-- source: URL -->` header.
**Input:** URL, output directory, depth, max_pages, optional include/exclude URL patterns, optional strategy flag, optional url-file for pre-filtered URL lists.
**Output:** Markdown files in output directory (one per page), with domain-prefixed filenames.

### CLI

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | required | Seed URL to crawl |
| `--output-dir` | required | Directory to save markdown files |
| `--depth` | 3 | Max crawl depth |
| `--max-pages` | 100 | Max pages to crawl |
| `--strategy` | auto | `auto` (sitemap→prefetch→bfs), `sitemap`, `prefetch`, `bfs` |
| `--exclude-patterns` | None | Comma-separated URL patterns to exclude |
| `--include-patterns` | None | Comma-separated URL patterns to include |
| `--url-file` | None | Path to text file with URLs (one per line) — skips discovery |
| `--no-prefetch` | false | Use serial BFS with full rendering |

```bash
# Auto-detection cascade
python -m src.crawler.crawl_site --url "https://docs.example.com" --output-dir "./output"

# Force strategy
python -m src.crawler.crawl_site --url "https://docs.example.com" --output-dir "./output" --strategy sitemap

# Pre-filtered URL file
python -m src.crawler.crawl_site --url "https://playwright.dev" --url-file urls_filtered.txt --output-dir "./output"
```

## explore_site.py

**Purpose:** URL discovery — backend for both `searxng-cli explore_site` and the `/crawl-site` pipeline. Discovers all URLs of a website and saves to a text file. Wraps `crawl_site.discover_urls()` and `crawl_site.discover_urls_sitemap()` with auto-strategy cascade, redirect detection, and shallow sitemap fallback. Returns `(urls, strategy_used, output_path)` tuple so CLI callers can build their own summary output.
**Input:** URL, strategy (auto/sitemap/prefetch), optional max-pages/depth/include-patterns/exclude-patterns/output/append.
**Output:** Text file with one URL per line; returns `(list[str], str, str)` — discovered URLs, strategy used, resolved output path.

### CLI

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | required | Seed URL to explore |
| `--strategy` | auto | `auto` (sitemap→prefetch), `sitemap`, `prefetch` |
| `--max-pages` | 200 | Max pages to discover |
| `--depth` | 10 | Max crawl depth for prefetch BFS |
| `--output` | `/tmp/explore_<domain>_urls.txt` | Output file path |
| `--append` | false | Append to output file instead of overwrite |
| `--include-patterns` | None | Comma-separated URL patterns to include |
| `--exclude-patterns` | None | Comma-separated URL patterns to exclude |

```bash
# Auto-detection cascade
python -m src.crawler.explore_site --url "https://docs.example.com"

# Continue discovery run
python -m src.crawler.explore_site --url "https://docs.example.com" --max-pages 400 --append

# Force prefetch with depth limit
python -m src.crawler.explore_site --url "https://docs.example.com" --strategy prefetch --depth 5
```

## filter_urls.py

**Purpose:** In-place URL list filter. Reads a URL-per-line file, drops lines matching any fnmatch glob pattern in `--exclude-patterns`, atomically rewrites the file. `--dry-run` prints dropped URLs + kept count to stderr without touching the file. Provides `match_any(url, patterns_str) -> bool` — the shared glob-match helper used by both this module and `explore_site.py` (sitemap-path post-filter).
**Input:** URL list file path, comma-separated exclude-patterns string, optional dry-run flag.
**Output:** Rewrites file in-place (atomic via tmpfile + os.replace); summary to stderr.

### CLI

| Flag | Default | Description |
|------|---------|-------------|
| `file` | required | Path to URL list file (one URL per line) |
| `--exclude-patterns` | required | Comma-separated glob patterns to drop |
| `--dry-run` | false | Preview mode — print dropped URLs, do not modify file |

```bash
# Preview: see what would be dropped
searxng-cli filter_urls /tmp/example_urls.txt --exclude-patterns "*/genindex.html,*/_modules/*" --dry-run

# Apply in-place
searxng-cli filter_urls /tmp/example_urls.txt --exclude-patterns "*/genindex.html,*/_modules/*"

# Exact URL (zero-wildcard) works as literal match
searxng-cli filter_urls /tmp/example_urls.txt --exclude-patterns "https://docs.example.com/en/old/index.html"
```
