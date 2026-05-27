# dev/news_pipeline/

Per-domain news scraping probe for trading-bot data layer. CoinDesk first; raw-output stage before site-specific filter design. No `src/` integration yet.

**Status:** Probe stage — raw output for filter-design inspection. No src/ integration yet.

## Scripts

### 01_coindesk_discover.py

**Purpose:** Fetch CoinDesk Google News Sitemap, filter to last 24h, write structured JSON for scrape input.

**Input:** `https://www.coindesk.com/arc/outboundfeeds/news-sitemap-index` (live HTTP, Mozilla UA, stdlib urllib)

**Output:** `01_output/discover_<UTC-timestamp>.json` — list of `{url, lastmod, publication_date, title, section}` sorted by lastmod desc.

**Stdout:** total sitemap URLs, kept count, section distribution.

```bash
./venv/bin/python dev/news_pipeline/01_coindesk_discover.py
```

### 02_coindesk_scrape.py

**Purpose:** Scrape each URL from a discover JSON via crawl4ai raw markdown (no PruningContentFilter). Writes per-article `.md` with YAML frontmatter + manifest JSON.

**Input:** `--input <path>` or auto-picks newest `01_output/discover_*.json`.

**Output:**
- `02_output/<sha256[:12]>.md` per article — YAML frontmatter (`url`, `lastmod`, `publication_date`, `title`, `section`, `scraped_at`) + raw markdown body
- `02_output/manifest.json` — `[{url, hash, file, char_count, status, error?}, ...]`

**Rate limit:** `asyncio.sleep(1.0)` between URLs. Per-URL errors → `status="failed"` in manifest, batch continues.

**Stdout:** success/empty/fail counts, total chars, slowest URL.

```bash
./venv/bin/python dev/news_pipeline/02_coindesk_scrape.py
./venv/bin/python dev/news_pipeline/02_coindesk_scrape.py --input dev/news_pipeline/01_output/discover_<ts>.json
```

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `discover_<ts>.json` files (sitemap snapshots) | ✅ yes |
| `02_output/` | `<hash>.md` article files + `manifest.json` | ✅ yes |
