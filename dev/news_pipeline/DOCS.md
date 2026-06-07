# dev/news_pipeline/

Per-domain news scraping pipeline for trading-bot data layer. CoinDesk → RAG collection `searxng_crypto`. End-to-end runnable; single-command daily runner.

**Status:** End-to-end complete (discover → dedup → scrape → cleanup → publish). Stays in `dev/`; `src/` promotion deferred.

## Convention

**Browser automation:** `01_coindesk_discover.py` uses pydoll + background Chrome launched via `open -gna` (macOS, no focus steal). `02b_coindesk_scrape_fresh_context.py` uses crawl4ai (Playwright) with `headless=True`; fresh `AsyncWebCrawler` per URL defeats CoinDesk regwall.

## Documentation Tree

- [exploration/DOCS.md](exploration/DOCS.md) — Manual UI exploration probes (pydoll browser, headed)

## Scripts

### run_pipeline.py ← entry point

**Purpose:** Single-command orchestrator. Chains precondition checks → discover (48h) → dedup → scrape → cleanup → publish. Logs per-stage counts and failure modes to `src/logs/coindesk_pipeline_YYYYMMDD.log`. Writes `src/logs/coindesk_pipeline_last_run.txt` on successful completion. Clears `02b_output/` and `03_output/` at start so publish only indexes current-run articles.

**Preconditions:** (a) internet reachable (HTTP to coindesk.com), (b) `rag-cli list_collections` exits 0.

```bash
./venv/bin/python dev/news_pipeline/run_pipeline.py
```

### 01_coindesk_discover.py

**Purpose:** Discover CoinDesk articles via UI pagination on `/latest-crypto-news`. Background Chrome launched via `open -gna "Google Chrome" --args --remote-debugging-port=<PORT> ...` (no focus steal); pydoll connects via `Chrome().connect(ws_url)`. Clicks "More stories" until ≥3 articles older than 48h are found (`PRE_48H_THRESHOLD=3`, `CUTOFF_DAYS=2`). Chrome killed via `pkill -f remote-debugging-port=<PORT>` on cleanup.

**Approach:** `_JS_EXTRACT` (DOM traversal, skipTags/skipCls noise filter) + `_JS_CLICK_BTN` + `_JS_COUNT` poll loop. `lastmod` and `publication_date` derived from URL's `/YYYY/MM/DD/` path → UTC midnight ISO string. Title captured from `<a>` text. `MAX_CLICK_ROUNDS=8` safety cap. **Live-blog URLs (`/live-markets-*`) filtered post-discovery.**

**Output:** `01_output/discover_<UTC-timestamp>.json` — list of `{url, lastmod, publication_date, title, section}` sorted by lastmod desc.

```bash
./venv/bin/python dev/news_pipeline/01_coindesk_discover.py
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

**Purpose:** Scrape each URL with fresh `AsyncWebCrawler` per URL — new Chrome process + clean cookie jar each fetch (crawl4ai/Playwright, `headless=True`). Resolves CoinDesk regwall (iter 2: 23/25 real bodies, 0 regwall hits). **Use this for production-quality scrapes.** No browser changes needed: headless Playwright has no focus-stealing issue.

**Input:** `--input <path>` or auto-picks newest `01_output/discover_*.json`. Pipeline passes the 04_dedup output explicitly via `--input`.

**Output:**
- `02b_output/<sha256[:12]>.md` per article — YAML frontmatter + raw markdown body
- `02b_output/manifest.json`

```bash
./venv/bin/python dev/news_pipeline/02b_coindesk_scrape_fresh_context.py
./venv/bin/python dev/news_pipeline/02b_coindesk_scrape_fresh_context.py --input dev/news_pipeline/04_output/discover_filtered_<ts>.json
```

### 03_coindesk_cleanup.py

**Purpose:** Extract clean article body from `02b_output/*.md`, strip nav/footer noise, normalize structure for RAG ingestion. Reads YAML frontmatter into manifest (metadata index), outputs pure-content `.md` starting with H1.

**Anchors:** H1 start-anchor + earliest-occurrence end-anchor (plain `More For You` / `## More For You` / `## We Care About Your Privacy` / tag-footer `{2,}` pattern). TAG_FOOTER requires ≥2 concatenated `[text](url)` to avoid single-link false-fires.

**Strip rules:** Google News badge, date/read-time byline (bare + Updated/Published prefix), author byline (`By [...](...)`), standalone image lines, inline links (`[text](url)` → `text`), empty links, trailing whitespace.

**Normalization:** blank line inserted between consecutive body paragraphs (non-header, non-bullet); blank-run collapse-to-1. Stdout reports trailing-ws strip count + para blank insert count.

**Output:** `03_output/<hash>.md` — pure content (no frontmatter). `03_output/manifest.json` — `[{hash, url, lastmod, publication_date, title, section, scraped_at, original_chars, cleaned_chars, reduction_pct, end_anchor_used}]`.

```bash
./venv/bin/python dev/news_pipeline/03_coindesk_cleanup.py
./venv/bin/python dev/news_pipeline/03_coindesk_cleanup.py --input dev/news_pipeline/02b_output/ --output /tmp/clean/
```

### 04_dedup.py

**Purpose:** Dedup gate — drops URLs whose `coindesk__<YYYY-MM-DD>__<hash>.md` already exists in the `searxng_crypto` RAG collection dir. Pure Python, no browser, no network. Filesystem presence of the target filename IS the seen-state; no separate state file.

**Input:** `--input <path>` or auto-picks newest `01_output/discover_*.json`. **Collection dir:** `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/searxng_crypto/`.

**Output:** `04_output/discover_filtered_<UTC-timestamp>.json` — same schema as discover, subset of entries.

```bash
./venv/bin/python dev/news_pipeline/04_dedup.py
./venv/bin/python dev/news_pipeline/04_dedup.py --input dev/news_pipeline/01_output/discover_<ts>.json
```

### 05_publish.py

**Purpose:** Copy cleaned MDs from `03_output/` to the `searxng_crypto` RAG collection dir as `coindesk__<YYYY-MM-DD>__<hash>.md`, then run `rag-cli index --collection searxng_crypto`. Idempotent (safe to re-run; rag-cli hash-skip handles re-index of already-indexed files).

**Input:** `03_output/manifest.json` + `03_output/*.md`. **Collection dir:** same as 04.

**Output:** files copied to `/Users/.../rag-cli/data/documents/searxng_crypto/coindesk__<date>__<hash>.md`. Triggers rag-cli indexing.

```bash
./venv/bin/python dev/news_pipeline/05_publish.py
./venv/bin/python dev/news_pipeline/05_publish.py --skip-index
```

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `discover_<ts>.json` files | ✅ yes |
| `01_reports/` | Per-run summary reports (institutional knowledge) | ❌ no |
| `02_output/` | Iter 1 shared-session outputs + `manifest.json` | ✅ yes |
| `02b_output/` | Iter 2+ fresh-context outputs + `manifest.json` | ✅ yes |
| `03_output/` | Cleaned article bodies + `manifest.json` | ✅ yes |
| `04_output/` | `discover_filtered_<ts>.json` files | ✅ yes |
