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

## 04_render_recall.py

**Purpose:** Measures URL discovery recall on docs.github.com/de/rest against a 305-URL gold standard. Compares three BFS strategies (prefetch+dCL baseline, prefetch+NI, full-render NI) to isolate the effect of JS rendering on discovered URL count.
**Output:** `04_reports/docs_github_rest_<YYYYMMDD>.md`
**Gold standard:** `goldstandard/docs_github_rest.txt` (305 URLs from github/docs content/rest repo tree)

```bash
# Full run — all 3 strategies + regression (rate-limit warning: A/B prefetch=True blocked by GitHub WAF)
./venv/bin/python dev/explore_pipeline/04_render_recall.py

# Strategy C only (most resilient to rate limiting)
./venv/bin/python dev/explore_pipeline/04_render_recall.py --strategies C_bfs_networkidle --no-regression

# All strategies with delay between to avoid rate limiting
./venv/bin/python dev/explore_pipeline/04_render_recall.py --delay 600

# Custom gold / depth
./venv/bin/python dev/explore_pipeline/04_render_recall.py --gold dev/explore_pipeline/goldstandard/docs_github_rest.txt --max-pages 600 --depth 10
```

CLI flags: `--gold PATH`, `--max-pages INT`, `--depth INT`, `--no-regression`, `--strategies COMMA_LIST`, `--delay INT`

Key finding from Phase A run (2026-05-29): `BFSDeepCrawlStrategy` uses HTTP for link extraction regardless of `wait_until` — changing to `networkidle` has no effect on recall. Strategy C (prefetch=False) found 205/305 = 67.2% recall. See `decisions/OldThemes/crawler_js_render_discovery/A_recall_probe.md`.

## Report Formats

**01_reports:** JSON with summary (total fetched, unique URLs, duplicates, content/empty counts, total chars) and URL list with per-URL content status and character counts. Reports are consumed by `dev/scrape_pipeline/filter_eval/06_content_source.py`.

**02_reports:** Markdown with summary table, removed URLs list, and full baseline URL list with [REMOVED] markers.

**03_reports:** Markdown with strategy comparison table (pages, time, per-page ms, duplicates), speedup vs baseline, and depth distribution per strategy.
