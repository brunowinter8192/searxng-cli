# src/news/engine/

## Role

Generic, platform-agnostic pipeline engine modules. Called by `pipeline.py`; no platform-specific
logic lives here. All modules accept platform parameters explicitly (no hardcoded source names).

`pipeline.py` dispatches Stage 3 on `platform.scrape_engine`: `"browser"` → `scrape.py`;
`"proxy_pool"` → `proxy_pool/scrape.py`. A third engine, `"proxy_riding"` → `proxy_riding/scrape.py`,
is ported and package-complete but NOT yet wired in `pipeline.py` — Stage 2 pending.

`publish.py` is kept on disk but is NOT called by any pipe path — cleanup+publish are decoupled
to a future ad-hoc skill.

## Modules

### scrape.py (197 LOC)

**Purpose:** Browser-engine scraper — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing, regwall guard. Active when `platform.scrape_engine == "browser"`.
**Reads:** entries list (in-memory), ScrapeConfig, regwall_signals list.
**Writes:** `{hash}.md` (BODY ONLY, no frontmatter) to output_dir (raw_dir in all call paths).
**Called by:** `pipeline.py:run_pipeline` (browser dispatch arm), `scrape_job.py:scrape_chunks_raw`.
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig).

`RegwallGuardError` is raised (not sys.exit) when regwall fraction ≥ `REGWALL_FAIL_THRESHOLD` (0.20).
`.manifest` attribute on the exception carries the full per-entry manifest (including ok entries
written before abort) so callers can persist raw data from aborted runs.

### dedup.py (61 LOC)

**Purpose:** Filter discover entries to those not yet in the raw corpus by checking file existence; optionally exclude known-failure URLs permanently.
**Reads:** entries list (in-memory), dir (filesystem), source name, mode, optional exclusion set.
**Writes:** nothing (pure filter).
**Called by:** `pipeline.py:run_pipeline` (mode=`"raw"`), `pipeline.py:run_scrape_only` (mode=`"raw"`).
**Calls out:** stdlib only.

`filter_new_entries(entries, collection_dir, source, mode="pubdate", exclude_urls=None) → (new_entries, n_skip_raw, n_excluded)`:
- `exclude_urls: set[str] | None` — when provided, URLs in the set are permanently excluded (counted as `n_excluded`) before the raw-file existence check. Default `None` = no exclusions (unchanged behaviour for browser path + `run_scrape_only`). Only the proxy_pool branch of `run_pipeline` passes this param (loaded from `dead_urls.txt` + `failed_urls.txt`).

Three modes via `mode` param:
- `"raw"` (all pipe paths): exact match `{hash}.md` in raw_dir — dedup on raw corpus.
- `"pubdate"`: exact match `{source}__{pubdate}__{hash}.md` — legacy, collection-based.
- `"hash_only"`: glob `{source}__*__{hash}.md` — legacy, collection-based, no pubdate.

### publish.py (134 LOC)

**Purpose:** Copy cleaned MDs to RAG collection dir; write/merge URL manifest; optionally run `rag-cli index`.
**Reads:** clean_manifest (in-memory), clean_dir (filesystem), existing `{collection}__index.jsonl` if present.
**Writes:** `{source}__{pubdate}__{hash}.md` to collection_dir; `{collection_name}__index.jsonl` in collection_dir.
**Called by:** NOT called by any active pipeline path. Kept on disk for future cleanup+publish skill.
**Calls out:** `rag-cli` (subprocess).

### scrape_job.py (97 LOC)

**Purpose:** Raw-only chunked scrape orchestration for `run_scrape_only()` and shared raw-persist helpers.
**Reads:** chunks (list of entry lists), platform config.
**Writes:** `{hash}.md` into raw_dir per ok entry; appends to `raw/manifest.jsonl`; updates `regwall_urls.txt` / `empty_urls.txt`.
**Called by:** `pipeline.py:run_scrape_only` (`scrape_chunks_raw`); `pipeline.py:run_pipeline` (`_append_to_raw_manifest`, `_update_blocked_urls`).
**Calls out:** `scrape.py:scrape_entries`.

`scrape_chunks_raw(chunks, raw_dir, platform, log)` — raw-only chunk loop. Per chunk: `scrape_entries()` → `_append_to_raw_manifest()` → `_update_blocked_urls({"regwall":…,"empty":…})`. `RegwallGuardError`: `exc.manifest` recovered, ok files preserved, loop stops. Returns `(totals, job_records, regwall_abort)`.

`_append_to_raw_manifest(raw_dir, ok_entries)` — append `{hash,url,publication_date}` lines to `raw/manifest.jsonl`. Append-only; no dedup (dedup happens upstream via `filter_new_entries(mode="raw")`).

`_update_blocked_urls(raw_dir, manifest, status_filenames)` — read existing blocked-URL file, union with new URLs from manifest by status, write back sorted. `status_filenames` keys: `"regwall"/"empty"` (browser), `"dead"/"failed"` (proxy_pool).

`job_records`: `[{t_chunk_start: datetime, url, hash, file, char_count, status, error, wait_strategy, elapsed_s}]` — consumed by `browser_reporter.py`.
`regwall_abort`: True when `RegwallGuardError` terminates the chunk loop early.

### browser_reporter.py (197 LOC)

**Purpose:** Per-job report writer for browser-engine scrape jobs. Produces `job.md` + `cumulative.png` from `job_records`.
**Reads:** `job_records` (in-memory list from `scrape_chunks_raw`), `t_job_start`.
**Writes:** `{job_dir}/job.md` (counts, regwall rate, throughput, backfill projection, char-count percentiles p10–p95, failure table); `{job_dir}/cumulative.png` (step-plot of cumulative ok count vs elapsed seconds).
**Called by:** `pipeline.py:run_scrape_only`.
**Calls out:** `matplotlib` (lazy import inside `_write_plot`), `statistics` (stdlib).

Key metric: `completion_s ≈ (t_chunk_start − t_job_start).total_seconds() + elapsed_s` per ok record — used as x-axis of the cumulative plot.
Backfill projection extrapolates from URLs/min → hours to scrape `_BACKFILL_TOTAL` (61 k) articles.

### proxy_pool/ (11 modules — see DOCS.md)

Generic proxy-rotation scrape engine. Active when `platform.scrape_engine == "proxy_pool"`.
Entry point: `scrape_entries_proxy()` in `proxy_pool/scrape.py`.

### proxy_riding/ (3 modules — see DOCS.md)

Browser + rotating-proxy engine for CoinDesk backfill. Ported from `dev/news_pipeline/coindesk_proxy_riding/`.
Entry point: `scrape_entries_riding()` in `proxy_riding/scrape.py`.
NOT yet active — `platform.scrape_engine == "proxy_riding"` dispatch arm not yet wired in `pipeline.py`.

## Documentation Tree

- [proxy_pool/DOCS.md](proxy_pool/DOCS.md) — proxy-rotation engine (loop, fetch, cooldown, buffer, logger, janitor, box_lock, proxy_key, pool_loaders, monosans_loader, scrape)
- [proxy_riding/DOCS.md](proxy_riding/DOCS.md) — browser + rotating-proxy engine (rider, reporter, scrape entry point); Stage 2 pipeline wiring pending
