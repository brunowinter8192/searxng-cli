# dev/news_pipeline/

Per-domain news scraping pipeline for trading-bot data layer. CoinDesk → RAG collection `searxng_crypto`. End-to-end runnable; single-command daily runner.

**Status:** End-to-end complete (discover → dedup → scrape → cleanup → publish). Stays in `dev/`; `src/` promotion deferred.

## Convention

**Browser automation:** `01_coindesk_discover.py` uses pydoll + background Chrome launched via `open -gna` (macOS, no focus steal). `02b_coindesk_scrape_fresh_context.py` uses crawl4ai (Playwright) with `headless=True`; fresh `AsyncWebCrawler` per URL run concurrently (Semaphore(8)) defeats CoinDesk's cookie-metered regwall and achieves ~30s on 32 URLs.

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

**Approach:** `_JS_EXTRACT` (DOM traversal, skipTags/skipCls noise filter) + `_JS_CLICK_BTN` + `_JS_COUNT` poll loop. `lastmod` and `publication_date` derived from URL's `/YYYY/MM/DD/` path → UTC midnight ISO string. Title captured from `<a>` text. `MAX_CLICK_ROUNDS=8` safety cap. **Live-blog URLs filtered post-discovery via `_is_live_blog`: slug (last path segment) starts with `live-` — catches `live-markets-`, `live-updates-`, any future `live-X-` variant.**

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

**Purpose:** Scrape each URL with fresh `AsyncWebCrawler` per URL — new Chromium process + clean cookie jar each fetch. Runs CONCURRENTLY via `asyncio.gather` + prod's deterministic per-domain Scrapy gate (ported from `src/crawler/pipe_scraper.py`: `_ensure_domain_state` + `_gate_domain`, `DOWNLOAD_DELAY=1.0`, `CONCURRENCY_PER_DOMAIN=8`, jitter=uniform(0.5×,1.5×)). `domcontentloaded` + `delay_before_return_html=0.5`, `page_timeout=15000`, no networkidle, no custom UA. Loud regwall guard: per-page WARN + per-run ERROR + exit non-zero if ≥20% regwalled. **Use this for production-quality scrapes.**

Only deviation from `pipe_scraper.py`: fresh crawler per URL (isolation). Pacing is identical.
Validated: 0/32 regwall, 32/32 ok, ~32s on 32 CoinDesk URLs. See `decisions/OldThemes/news_pipeline_layers/12_scrape_prod_rebuild.md` for full investigation trail (real-B1 timezone dead-end, B2 validation, gate restoration).

**Input:** `--input <path>` or auto-picks newest `01_output/discover_*.json`. Pipeline passes the 04_dedup output explicitly via `--input`.

**Output:**
- `02b_output/<sha256[:12]>.md` per article — YAML frontmatter (url, lastmod, publication_date, title, section, scraped_at) + raw markdown body. Regwalled pages NOT written.
- `02b_output/manifest.json` — status values: `ok`, `empty`, `failed`, `regwall`.

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

### prod_scrape_smoke.py ← investigation tool

**Purpose:** Smoke A — empirical regwall baseline. Runs all 32 URLs from a discover-filtered JSON through the PRODUCTION `scrape_urls_workflow` (from `src/crawler/pipe_scraper.py`, shared session). Produces `smoke_output/raw/` + `smoke_output/regwall_review.md` with summary table (slug / bytes / lines / marker_hits / verdict_hint) and 50-line previews. Verdict heuristic: `REGWALL?` if bytes<3000 OR marker_hits≥3. NOT committed: `smoke_output/` is gitignored.

**Result:** 17/32 REGWALL? (9k bytes, 5 marker hits), 15/32 article? (17k-35k bytes). Confirmed shared-session accumulates cookie counter → regwall after quota.

```bash
./venv/bin/python dev/news_pipeline/prod_scrape_smoke.py
```

### scrape_isolation_smoke.py ← investigation tool

**Purpose:** Smoke B — two isolation candidates over same 32 URLs. B1: shared crawler + per-URL `timezone_id` (intended to bust crawl4ai 0.8.6 context cache). B2: fresh `AsyncWebCrawler` per URL, concurrent via `asyncio.gather` + `Semaphore(8)`. Produces `smoke_output/b1_regwall_review.md` + `smoke_output/b2_regwall_review.md` and a comparison table (stdout). NOT committed: `smoke_output/` is gitignored.

**Result:** Both rows 0/32 regwall, 24s — but B1 row was invalid (script edited while running; B1 actually executed as B2). Real-B1 subsequently failed 25/32 timeout. B2 is the shipped mechanism. See `decisions/OldThemes/news_pipeline_layers/12_scrape_prod_rebuild.md`.

```bash
./venv/bin/python dev/news_pipeline/scrape_isolation_smoke.py
```

## The Block — Discovery Probes (`theblock/`)

Status: discovery 36/64 sub-sitemaps cached (first pipe run). CF-pass rate measured at **0.8%** on live pool (vs old 18.8% discriminator probe). Per-IP budget B: min=4, max=20, mean=9.3 (3 exhausted proxies). See `decisions/OldThemes/news_pipeline_layers/` files 14–21 for full state.

### theblock/probe_discovery.py

**Purpose:** Measure discovery coverage + URL taxonomy. Fetches the 64-sub sitemap union, news sitemap, RSS, and bounded UI crawl; outputs `theblock/discover_coverage_report.md`. Resume-safe: per-sub checkpoint files in `theblock/cache/`.

**CF behaviour:** IP-level 403/429 fires after ~21 sequential sub-sitemap fetches. See `decisions/OldThemes/news_pipeline_layers/15_theblock_cf_block_and_anti_cf_method.md`.

```bash
./venv/bin/python dev/news_pipeline/theblock/probe_discovery.py
```

### theblock/probe_monosans.sh + monosans_cfg_*.toml

**Purpose:** Evidence probe for `monosans/proxy-scraper-checker` proxy pool yield against theblock.co. Two runs: neutral `check_url` (icanhazip) and theblock.co sitemap `check_url`. Wrapper handles Docker invocation (native TUI binary requires TTY; Docker path works headless).

**Results:** `decisions/OldThemes/news_pipeline_layers/16_monosans_pool_evidence.md`. Key finding: neutral pool yields 494/17,202 proxies; theblock check_url yields 0/17,202. Conclusion: use neutral check_url only; theblock.co CF validation is the `curl_cffi impersonate="chrome"` fetch loop's responsibility.

**Configs:**
- `monosans_cfg_neutral.toml` — `check_url = https://ipv4.icanhazip.com`, concurrency 512
- `monosans_cfg_theblock.toml` — `check_url = https://www.theblock.co/sitemap_tbco_news.xml`, concurrency 50

**Ephemeral dirs (gitignored):** `theblock/monosans_bin/`, `theblock/monosans_docker/`, `theblock/monosans_out_neutral/`, `theblock/monosans_out_theblock/`.

```bash
bash dev/news_pipeline/theblock/probe_monosans.sh neutral
bash dev/news_pipeline/theblock/probe_monosans.sh theblock
```

### theblock/probe_curl_cffi_discriminator.py

**Purpose:** Discriminates OldThemes 16's ambiguous 0/17202 monosans result: re-tests the neutral pool with `curl_cffi impersonate=chrome` (correct browser JA3 vs monosans' rustls) against a real `/post/` sub-sitemap (`sitemap_tbco_post_type_post_0.xml`). Identifies which failure mode dominates: CF signature block (a), CF IP-reputation block (b), or stale pool (c).

**Results:** `decisions/OldThemes/news_pipeline_layers/17_curl_cffi_passability_discriminator.md`. Key finding: **80/425 (18.8%) pass** → verdict **(a)**: rustls was the blocker; curl_cffi-chrome passes CF; free proxy loop is viable for the discovery gap. URL correction required mid-run: real sub URL is `sitemap_tbco_post_type_post_N.xml` (not `post_N.xml`).

**Ephemeral output (gitignored):** `theblock/probe_curl_cffi_discriminator_reports/`

```bash
./venv/bin/python dev/news_pipeline/theblock/probe_curl_cffi_discriminator.py
```

### theblock/probe_pool_size.py

**Purpose:** Measure the raw proxy pool size from 68 public source URLs — pure fetch+parse+count, NO liveness checking, NO proxy contacted. Fetches all sources concurrently (`httpx.AsyncClient`, `Semaphore(20)`, 15s timeout), parses `host:port` entries from bare, `proto://`, and `proto://user:pass@` formats, reports per-source counts + per-protocol bucket breakdown + global unique dedup vs baseline.

**Results:** `decisions/OldThemes/news_pipeline_layers/19_maxed_source_expansion.md`. Key finding: 68/68 sources OK (1.7s), **428,500 raw** / **118,701 globally unique** host:port entries (24.9× monosans single-source baseline of ~17,202).

**Ephemeral output (gitignored):** `theblock/probe_pool_size_reports/`

```bash
./venv/bin/python dev/news_pipeline/theblock/probe_pool_size.py
```

### theblock/probe_liveness.py (386 LOC)

**Purpose:** Instrumented async liveness checker + concurrency sweep. Stage 1 deliverable. Imports the 68 source URL lists from `probe_pool_size.py` (no re-typing). Modes: `--freeze` (fetch sources → write sorted, deduped `frozen_pool/{http,socks4,socks5}.txt`); `--sample N` / `--full` (check frozen pool via `curl_cffi.AsyncSession`); `--source monosans` (fetch live monosans JSON via `monosans_loader`, apply staleness filter, check without freeze); `--source curated` (fetch monosans+proxifly unified list via `curated_sources`, apply staleness filter, check without freeze). Classifies every dead proxy into a reason bucket, appends structured entry to `sweep_log.md`. After every run (all modes except `--freeze`), folds results into the cumulative `logs/proxy_status_log.json` via `proxy_status_log.record_run()`. socks5 uses `socks5h://` (remote DNS through proxy). Timeout split: elapsed-time primary + libcurl message fallback + unknown on mismatch (version-drift signal).

**Staleness filter (`--source monosans` and `--source curated`):** after loading the live list, calls `proxy_status_log.partition_fresh(entries, window_s)` to split into `(to_check, skipped_fresh)`. Only `to_check` enters `run_checks` and `record_run`; skipped proxies keep their existing `last_seen`. `--recheck-window S` (int, default `3600`) controls the freshness threshold in seconds. Console and `sweep_log.md` report `skipped_fresh=N` when non-zero. Frozen/sample path is unaffected.

**Results:** `decisions/OldThemes/news_pipeline_layers/20_liveness_check_and_concurrency_sweep.md`. Sweep: 20k sample × 4 concurrency levels (512/1000/2000/3000), timeout 5s/5s.

**Persistent output (committed):** `theblock/probe_liveness_logs/sweep_log.md`, `theblock/logs/proxy_status_log.json`
**Ephemeral (gitignored):** `theblock/frozen_pool/`, `theblock/probe_liveness_logs/unknown_errors_*.log`

```bash
# Freeze (once, or to refresh pool):
./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --freeze

# monosans live source (no freeze needed); --recheck-window skips proxies checked < N seconds ago:
./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --source monosans
./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --source monosans --recheck-window 1800

# curated unified source (monosans+proxifly merged+deduped); staleness filter applied:
./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --source curated --concurrency 128

# Sweep run at specific concurrency:
./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --sample 20000 --concurrency 512
./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --sample 20000 --concurrency 1000

# Full pool check (Stage 2):
./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --full --concurrency 1000
```

### theblock/monosans_loader.py (39 LOC)

**Purpose:** Fetch `monosans/proxy-list` live JSON (`proxies.json`) and return `[(protocol, host:port)]` — same tuple shape as `load_frozen_pool()`. Single synchronous `httpx.get`. Handles optional auth fields (currently always null in monosans). Called by `probe_liveness.py` (`--source monosans`) and by `curated_sources.load_curated_proxies()`.

### theblock/curated_sources.py (262 LOC)

**Purpose:** Unified proxy source hub. Two production loaders + 13 standalone eval loaders + shared fetch/dedup helpers.

**Production loaders:**
- `load_curated_proxies()` — monosans + proxifly (~3.5k unique); used by existing sitemap dev-runs.
- `load_backfill_pool()` — all 13 Top-Repo sources merged + deduped → **22,723 unique**; used by `acquire_pipe.py --pool backfill`. proxifly excluded (rank 15, below survey cutoff).

**Standalone eval loaders (13 repos):**
monosans (via `monosans_loader`), roosterkid, databay-labs, TheSpeedX (existing),
themiralay, r00tee, iplocate, sunny9577, ALIILAPRO, dpangestuw, Zaeem20, zloi-user,
hookzof (new — added for backfill pool).

**Universal fetch helper:** `_fetch_roosterkid(proto, url)` applies `_IP_PORT_RE`
(`\d{1,3}(?:\.\d{1,3}){3}:\d+`) to every line — handles bare, scheme-prefixed
(`http://host:port`), and decorated (`host:port:Country`) formats.
`_fetch_bare_txt` retained for existing callers; `_fetch_roosterkid` is the robust
universal extractor used by all 9 new loaders.

### theblock/proxy_status_log.py (102 LOC)

**Purpose:** Cumulative proxy-status log — keyed by `"protocol://host:port"`, bounded by unique proxy count (not run count). `record_run(results, source_label)` loads `logs/proxy_status_log.json`, upserts every result (alive + dead), writes back. Per-entry schema: `{protocol, host, port, checks, alive, dead, last_status, first_seen, last_seen}`. Explicit `protocol`/`host`/`port` fields enable subnet/ASN/port grouping without re-parsing the key. `proxy_key(proto, host_port)` — **public** canonical key builder (auth-stripped `proto://host:port`); shared by `record_run`, `partition_fresh`, and `curated_sources._merge_dedup` — single source of truth for the entire keyspace. `partition_fresh(entries, window_s)` — called by `probe_liveness.py` on the monosans and curated paths — partitions `[(proto, host_port)]` into `(to_check, skipped_fresh)` using the log's `last_seen` field; age comparison is timezone-aware (`last_seen` parsed as UTC via `.replace(tzinfo=timezone.utc)`).

### theblock/logs/proxy_status_log.json

**Purpose:** Cumulative proxy identity + alive/dead history across all `probe_liveness.py` runs. Keyed by `"protocol://host:port"`. **Tracked in git** — institutional data (analogous to `source_scoreboard.json`). Size bounded by unique proxy count, not run count.

### theblock/source_tracker.py (283 LOC)

**Purpose:** Per-source attribution, cumulative scoreboard, and freshness tracking. Called once per pipe run via `update_and_flush()`. Reads `source_results` + `hp_to_sources` from `pipe_theblock.fetch_fresh_pool()` and computes per-source `checked`/`alive`/`cf_checked`/`cf_passed`/`unique_latest` counters. Merges run stats into `source_scoreboard.json`, re-renders `source_scoreboard.md`, diffs against `source_snapshots/` for freshness, appends to `freshness_log.md`.

**Not run standalone** — called by `pipe_theblock.py`.

### theblock/pipe_theblock.py (339 LOC)

**Purpose:** Full proxy pipeline — Stage 1 (neutral liveness, 5k sample @ conc 128) → Stage 2 (CF-pass check via curl_cffi chrome impersonation) → Stage 3 (sitemap sub-URL discovery with sequential-exhaustion B-capture). Appends one funnel entry to `pipe_log.md` per run. Resume-safe: per-sub checkpoint JSONs in `theblock/cache/`.

**Stage design:**
- Stage 1: Fetch fresh 68-source pool, random 5k sample, neutral liveness @ conc=128 (5s/5s timeouts).
- Stage 2: CF-pass check on neutral-alive proxies using `curl_cffi.requests.Session(impersonate="chrome")` vs `sitemap_tbco_post_type_post_0.xml`. Returns 200+valid-XML = pass.
- Stage 3: Sequential exhaustion — drain ONE proxy until it 403/429s (records B), then rotate. Guarantees real B observations per proxy (vs round-robin which never exhausts).

**Output:** `theblock/pipe_log.md` (appended), `theblock/cache/sub_*.json` (per-sub checkpoint).

```bash
./venv/bin/python dev/news_pipeline/theblock/pipe_theblock.py
```

### theblock/pipe_log.md

**Purpose:** Funnel log — one structured entry per pipe run. Tracks Stage 1 neutral-alive %, Stage 2 CF-pass rate, Stage 3 subs fetched + cache progress, per-IP budget B distribution, and wall-clock per stage. Appended (never overwritten); comparable across runs like `sweep_log.md`. **Tracked in git** (run history is institutional knowledge for cycle-economics decisions).

### theblock/source_scoreboard.json + source_scoreboard.md

**Purpose:** Cumulative per-source proxy quality tracking across runs. JSON is the canonical state (loaded + merged each run); MD is the rendered ranking table (re-generated each run, tracked). Columns: raw/run, alive%, CF-hits (absolute count — early CF signal), CF% (n), unique%/run, rank score, runs. **Rank score:** `cf_rate` if `cf_checked ≥ 30`, else `alive_rate × exclusivity`. **Tracked in git** — cumulative state across worktrees/merges.

### theblock/freshness_log.md

**Purpose:** Per-run new/dropped proxy diff per source. Appended each run. First run sets baseline snapshot (no diff). Second+ run shows which sources inject fresh proxies (high new%) vs stale sources. **Tracked in git.**

### theblock/jhao104/

jhao104/proxy_pool probe (self-maintaining pool: scrape → Redis → validate/evict → Flask API). Stage 2: sole validator is `theblockValidator` (curl_cffi chrome impersonation vs sitemap_tbco_index.xml); measured CF-pass rate **~0.085%** (1/1177 across 2 cycles). Setup, dep-compat fixes, env-proxy findings, Stage 1 + 2 baselines: [theblock/jhao104/NOTES.md](theblock/jhao104/NOTES.md).

### theblock/probe_curated_theblock_cf.py

Standalone direct CF-pass probe on the monosans+proxifly curated list (no alive pre-filter; curl_cffi chrome impersonation; same gate as jhao104 Stage 2). Key finding: **52/3477 = 1.496% overall** (http: 0.944%, socks4: **3.567%**, socks5: 0.698%); socks4 leads 3.8×; curated list 17.6× better than jhao104 scraped sources. Home-IP direct check: CF-reputation-clear (200 + XML). Reports to gitignored `probe_curated_theblock_cf_reports/`.

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `discover_<ts>.json` files | ✅ yes |
| `01_reports/` | Per-run summary reports (institutional knowledge) | ❌ no |
| `02_output/` | Iter 1 shared-session outputs + `manifest.json` | ✅ yes |
| `02b_output/` | Iter 2+ fresh-context outputs + `manifest.json` | ✅ yes |
| `03_output/` | Cleaned article bodies + `manifest.json` | ✅ yes |
| `04_output/` | `discover_filtered_<ts>.json` files | ✅ yes |
| `smoke_output/` | Smoke A/B raw scrapes + review MDs (investigation only) | ✅ yes |
| `theblock/pipe_log.md` | Funnel log per pipe run (tracked — run history, like sweep_log.md) | ❌ no |
| `theblock/source_scoreboard.json` | Cumulative per-source proxy quality state (tracked) | ❌ no |
| `theblock/source_scoreboard.md` | Rendered source ranking table (tracked, re-generated each run) | ❌ no |
| `theblock/freshness_log.md` | Per-run new/dropped proxy diffs per source (tracked, appended) | ❌ no |
| `theblock/source_snapshots/` | Per-source proxy sets for freshness diffing (gitignored) | ✅ yes |
| `theblock/cache/` | Per-sub sitemap checkpoint JSONs + news_sitemap.json + bulk run data | ✅ yes |
| `theblock/monosans_bin/` | monosans native binary (ephemeral) | ✅ yes |
| `theblock/monosans_docker/` | monosans Docker build context (ephemeral) | ✅ yes |
| `theblock/monosans_out_neutral/` | Neutral pool run output (ephemeral) | ✅ yes |
| `theblock/monosans_out_theblock/` | TheBlock pool run output (ephemeral) | ✅ yes |
| `theblock/probe_curl_cffi_discriminator_reports/` | Per-run discriminator reports (ephemeral) | ✅ yes |
| `theblock/probe_pool_size_reports/` | Per-run pool-size reports (ephemeral) | ✅ yes |
| `theblock/frozen_pool/` | Frozen deduped pool per bucket (ephemeral, regenerated with --freeze) | ✅ yes |
| `theblock/probe_liveness_logs/` | sweep_log.md (committed) + unknown_errors_*.log (gitignored) | partial |
| `theblock/logs/` | proxy_status_log.json (cumulative keyed proxy history — committed) | ❌ no |
