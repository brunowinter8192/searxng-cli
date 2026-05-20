# Explore Pipeline

URL discovery and traversal testing for Crawl4AI's BFS deep crawl strategy.

## 01_discovery.py

**Purpose:** Crawls a website using BFS strategy with domain filtering. Reports URL discovery metrics: total fetched, unique URLs, duplicates removed, content presence, character counts.
**Output:** `01_reports/<label>_<timestamp>.json`

`--all` crawls all domains from `domains.txt` in parallel (asyncio.gather, no semaphore — each domain gets its own browser context with independent BFS state).

```bash
python dev/explore_pipeline/01_discovery.py https://docs.searxng.org --depth 2 --max-pages 50
python dev/explore_pipeline/01_discovery.py --all
```

## domains.txt

Seed URLs for batch crawling. Format: `label|url|depth|max_pages`

Each domain represents a different HTML generator and content type for broad test coverage.

## 02_url_filters.py

**Purpose:** Compares crawl results with and without URL filters. Runs baseline crawl (no filters) and filtered crawl (with --exclude-patterns), then reports which URLs were removed by the filter.
**Output:** `02_reports/<label>_<timestamp>.md`

```bash
python dev/explore_pipeline/02_url_filters.py https://docs.searxng.org --exclude-patterns "/genindex*,/py-modindex*,/search*"
```

ContentTypeFilter (text/html) is always active in both runs. The report shows baseline count, filtered count, removed URLs, and marks removed URLs in the full baseline list.

## 03_strategies.py

**Purpose:** Benchmarks explore_site crawl strategies. Compares baseline (domcontentloaded + DefaultMarkdownGenerator), prefetch + domcontentloaded, and prefetch without wait_until. Measures time per strategy, pages discovered, per-page latency, and speedup vs baseline.
**Output:** `03_reports/explore_strategies_<domain>_<timestamp>.md`

```bash
python dev/explore_pipeline/03_strategies.py https://docs.crawl4ai.com --max-pages 50
python dev/explore_pipeline/03_strategies.py --depth 3
```

Default test URL: docs.crawl4ai.com. Report includes results table, speedup calculation, and depth distribution per strategy.

## Report Formats

**01_reports:** JSON with summary (total fetched, unique URLs, duplicates, content/empty counts, total chars) and URL list with per-URL content status and character counts. Reports are consumed by `dev/scrape_pipeline/filter_eval/06_content_source.py`.

**02_reports:** Markdown with summary table, removed URLs list, and full baseline URL list with [REMOVED] markers.

**03_reports:** Markdown with strategy comparison table (pages, time, per-page ms, duplicates), speedup vs baseline, and depth distribution per strategy.
