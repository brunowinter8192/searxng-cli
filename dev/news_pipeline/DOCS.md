# dev/news_pipeline/

Per-domain news scraping probe for trading-bot data layer. CoinDesk first; raw-output stage before site-specific filter design. No `src/` integration yet.

**Status:** Probe stage — raw output for filter-design inspection. No src/ integration yet.

## Convention

**Probes laufen headed (headless=False)** für visuelle Mit-Inspektion durch den User. Gilt für alle `dev/news_pipeline/`-Probes mit Browser-Automation. `--headless` flag als explizites Opt-out vorhanden.

## Documentation Tree

- [exploration/DOCS.md](exploration/DOCS.md) — Manual UI exploration probes (pydoll browser, headed)

## Scripts

### 01_coindesk_discover.py

**Purpose:** Discover CoinDesk articles via UI pagination on `/latest-crypto-news`. pydoll headed browser navigates the page, extracts feed-scoped article links via JS, clicks "More stories" until ≥3 pre-today articles are collected (24h coverage heuristic). Replaces sitemap-based approach (iter 4, 2026-05-27): removes 25-URL cap, picks up yesterday's articles that sitemap missed.

**Approach:** `_JS_EXTRACT` (DOM traversal, skipTags/skipCls noise filter) + `_JS_CLICK_BTN` + `_JS_COUNT` poll loop. `lastmod` and `publication_date` derived from URL's `/YYYY/MM/DD/` path → UTC midnight ISO string. Title captured from `<a>` text. Terminates on `PRE_TODAY_THRESHOLD=3` or `MAX_CLICK_ROUNDS=8` safety cap (warns to stderr if cap fires).

**Output:** `01_output/discover_<UTC-timestamp>.json` — list of `{url, lastmod, publication_date, title, section}` sorted by lastmod desc. Schema identical to sitemap-based predecessor — Stage 2 requires zero changes.

**CLI:** `--headless` opt-in for cron; default headed for visual inspection.

```bash
./venv/bin/python dev/news_pipeline/01_coindesk_discover.py
./venv/bin/python dev/news_pipeline/01_coindesk_discover.py --headless
```

### 02_coindesk_scrape.py

**Purpose:** Scrape each URL from a discover JSON via crawl4ai raw markdown (no PruningContentFilter). Shared `AsyncWebCrawler` session — **hits CoinDesk regwall after ~3 URLs** (iter 1 baseline, 21/25 regwall'd). Kept as reference for shared-session behaviour.

**Input:** `--input <path>` or auto-picks newest `01_output/discover_*.json`.

**Output:**
- `02_output/<sha256[:12]>.md` per article — YAML frontmatter + raw markdown body
- `02_output/manifest.json` — `[{url, hash, file, char_count, status, error?}, ...]`

```bash
./venv/bin/python dev/news_pipeline/02_coindesk_scrape.py
./venv/bin/python dev/news_pipeline/02_coindesk_scrape.py --input dev/news_pipeline/01_output/discover_<ts>.json
```

### 02b_coindesk_scrape_fresh_context.py

**Purpose:** Same as `02_coindesk_scrape.py` but with fresh `AsyncWebCrawler` per URL — new Chrome process + clean cookie jar each fetch. Resolves CoinDesk regwall (iter 2: 23/25 real bodies, 0 regwall hits). **Use this for production-quality scrapes.**

**Input:** `--input <path>` or auto-picks newest `01_output/discover_*.json`.

**Output:**
- `02b_output/<sha256[:12]>.md` per article — YAML frontmatter + raw markdown body
- `02b_output/manifest.json`

```bash
./venv/bin/python dev/news_pipeline/02b_coindesk_scrape_fresh_context.py
./venv/bin/python dev/news_pipeline/02b_coindesk_scrape_fresh_context.py --input dev/news_pipeline/01_output/discover_<ts>.json
```

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `discover_<ts>.json` files (sitemap snapshots) | ✅ yes |
| `01_reports/` | Per-run summary reports (institutional knowledge) | ❌ no |
| `02_output/` | Iter 1 shared-session outputs + `manifest.json` | ✅ yes |
| `02b_output/` | Iter 2 fresh-context outputs + `manifest.json` | ✅ yes |
