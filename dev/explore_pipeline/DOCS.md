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

## 05_playwright_bfs.py (328 LOC)

**Purpose:** Manual Playwright-per-page BFS: renders each page via `AsyncWebCrawler.arun()` (real browser, post-JS DOM), extracts `result.links.internal`, follows matching `--include-pattern` URLs. Measures recall vs goldstandard. Contrasts with `04_render_recall.py` (HTTP BFS).
**Output:** `05_reports/docs_github_rest_<YYYYMMDD>.md`

```bash
./venv/bin/python dev/explore_pipeline/05_playwright_bfs.py
./venv/bin/python dev/explore_pipeline/05_playwright_bfs.py --max-pages 400 --concurrency 1
./venv/bin/python dev/explore_pipeline/05_playwright_bfs.py --stealth
```

CLI flags: `--gold PATH`, `--seed URL`, `--include-pattern STR`, `--max-pages INT`, `--max-depth INT`, `--delay N.N`, `--page-timeout INT`, `--concurrency {1,2,3}`, `--stealth`

Key finding (2026-05-29): Playwright BFS from `docs.github.com/de/rest` reaches 248/305 = 81.3%. Ceiling is structural — GHEC/deprecated pages are not linked from any FPT sidebar page.

## 06_nextdata_probe.py (339 LOC)

**Purpose:** Agentic discovery via `__NEXT_DATA__` nav-tree extraction. Fetches seed HTML via plain HTTP (no browser), parses `sidebarTree` from the Next.js SSR blob, detects all versions via `allVersions`, fetches each version's REST root page, unions all sidebar trees normalized to canonical `/de/rest/…` form. Scores recall vs goldstandard.
**Output:** `06_reports/gh_live_discovery_<date>_<time>.md` · discovered URL set → `06_discovered_urls.txt`

```bash
./venv/bin/python dev/explore_pipeline/06_nextdata_probe.py
./venv/bin/python dev/explore_pipeline/06_nextdata_probe.py --no-ghes
./venv/bin/python dev/explore_pipeline/06_nextdata_probe.py --gold dev/explore_pipeline/goldstandard/docs_github_rest.txt
```

CLI flags: `--gold PATH`, `--no-ghec`, `--no-ghes`

Key finding (2026-05-31): 305/305 = 100% recall in 1.6s. FPT sidebar (256) + GHEC normalized (36 net new) + GHES all-versions normalized (24 net new, incl. deprecated `projects-classic` in GHES 3.16). Generic to any Next.js SSR doc site. Method narrative: `decisions/OldThemes/agentic_discovery/01_gh_live_experiment.md`.

## Report Formats

**01_reports:** JSON with summary (total fetched, unique URLs, duplicates, content/empty counts, total chars) and URL list with per-URL content status and character counts. Reports are consumed by `dev/scrape_pipeline/filter_eval/06_content_source.py`.

**02_reports:** Markdown with summary table, removed URLs list, and full baseline URL list with [REMOVED] markers.

**03_reports:** Markdown with strategy comparison table (pages, time, per-page ms, duplicates), speedup vs baseline, and depth distribution per strategy.

**05_reports:** Markdown with recall table (found/matched/missing/noise/latency), baseline comparison, and sample missing URLs.

**06_reports:** Markdown with recall table (found per version/net additions/matched/noise), baseline comparison, per-step discovery log. Discovered URL set saved separately as `06_discovered_urls.txt`.
