# src/news/

## Role

Multi-platform news ingestion pipeline, run as `python -m src.news --source <platform>`. Discovers articles, dedups against the raw corpus, scrapes raw markdown/HTML into `data/news/{name}/raw/`. For The Block (proxy_pool engine) the pipeline also runs an in-pipe clean-pass that writes cleaned articles into the RAG collection dir. Indexing stays fully decoupled — no `rag-cli index` call in any pipe path. Touch this package to add a news source or change pipeline orchestration; the generic scrape engines live in `engine/`, platform implementations in `platforms/`. Do NOT import from `src/crawler/` or `src/scraper/` — this package is self-contained.

## Public Interface

`__init__.py` is empty; the package runs as a module (`python -m src.news` → `__main__.py`). Direct async entry: `run_pipeline(platform)`, `run_discover_only(platform)`, `run_scrape_only(platform, year=…, limit=…)` in pipeline.py.

## Flow

`__main__` parses args, imports the platform module (side-effect registers it), looks it up via `registry.get`, and calls one of pipeline's three entries. `run_pipeline`: discover → dedup(raw) → scrape → raw persist (+ clean-pass for proxy_pool/TheBlock). `run_scrape_only`: date-filtered backfill, discover-free, dispatched on `platform.scrape_engine`. `run_discover_only`: discover + persist only. Scrape dispatch key is `platform.scrape_engine` ∈ {browser, proxy_pool, proxy_riding}.

## Modules

### pipeline.py (428 LOC)

**Purpose:** Async orchestrator. `run_pipeline` runs stages discover → dedup → scrape → raw-persist, plus `_run_clean_pass` for proxy_pool platforms (reads `raw/{hash}.md`, `platform.cleanup()`, writes `{name}__{pubdate}__{hash}.md` to the RAG collection dir; body-less articles logged to `clean/bodyless_urls.txt`). `run_scrape_only` is the decoupled backfill path (dispatch on `scrape_engine`: proxy_riding processes the full entry set at once, browser chunks 200-URL batches). `run_discover_only` discovers + persists (master list for `uses_master_list` platforms, else JSON snapshot / per-year shards). Helpers: `_persist_master_list`, `_append_to_raw_manifest`, `_update_blocked_urls`.
**Reads:** `data/news/{name}/raw/`, `discover/` (dead_urls.txt, failed_urls.txt, per-year shards, master_urls.txt); internet-check via `urllib`.
**Writes:** `raw/{hash}.{md,html}`, `raw/manifest.jsonl`, `discover/` block-lists, `clean/` (proxy_pool), `scrape_jobs/{job_id}/` reports (via reporters), RAG collection dir (clean-pass).
**Called by:** `__main__.py`.
**Calls out:** `platform` (Platform); `engine.dedup` (filter_new_entries); `engine.scrape` (scrape_entries, RegwallGuardError); `engine.proxy_pool` (box_lock, Janitor, AcquireLogger, scrape_entries_proxy); `engine.scrape_job` (scrape_chunks_raw, _append_to_raw_manifest, _update_blocked_urls); `engine.browser_reporter` (write_scrape_report); `engine.proxy_riding` (scrape_entries_riding, RidingScrapeConfig, write_riding_report); `engine.publish` (pub_date_str).

### __main__.py (132 LOC)

**Purpose:** argparse entry point. Flags: `--source`, `--skip-index` (no-op, CLI compat), `--timeframe`, `--discover-only`, `--scrape-only` (+ `--year/--from/--to/--limit/--browsers/--slots/--cooldown-policy/--page-timeout`). Imports the platform modules for side-effect registration, resolves via `registry.get`, dispatches to the matching pipeline entry. When `--timeframe` is not `delta` and not `--discover-only`, auto-forces `skip_index=True` and prints the manual index reminder.
**Reads:** CLI args.
**Writes:** stdout.
**Called by:** the `python -m src.news` entry point.
**Calls out:** `platforms.coindesk`, `platforms.theblock` (side-effect register); `registry` (get); `pipeline` (run_pipeline, run_discover_only, run_scrape_only).

### platform.py (35 LOC)

**Purpose:** The extension seam. Defines the `Platform` Protocol (name, collection, precondition_url, regwall_signals, scrape_engine, scrape_config, proxy_scrape_config; `discover()` + `cleanup()`), plus the `ScrapeConfig` and `ProxyScrapeConfig` dataclasses. `scrape_engine` ∈ {browser, proxy_pool, proxy_riding} is the pipeline dispatch key. Optional attrs (`riding_scrape_config`, `timeframe`, `uses_master_list`) are consumed via `getattr` in pipeline.py, deliberately NOT in the Protocol.
**Called by:** `pipeline.py`, `registry.py`, `platforms/*`, `engine/*`.
**Calls out:** none (stdlib `typing`, `dataclasses`).

### registry.py (19 LOC)

**Purpose:** Name → Platform registry. `register(instance)` (called at platform-module import) and `get(name)` (called by `__main__`).
**Reads / Writes:** in-memory registry dict.
**Called by:** `__main__.py` (get); `platforms/*/__init__.py` (register).
**Calls out:** `platform` (Platform).

## State

`registry`'s in-memory name→Platform dict — populated at platform-module import (side-effect), read by `__main__`. On disk, per-platform corpus under `data/news/{name}/` (raw/, discover/, clean/, scrape_jobs/) is the durable state; `raw/manifest.jsonl` + the discover block-lists (dead/failed/regwall/empty) drive dedup and make re-runs resumable.

## Gotchas

- To add a platform: create `platforms/<name>/__init__.py` defining a `Platform` class that calls `register(instance)` at import, then import that module in `__main__.py` for side-effect registration.
- `--skip-index` is accepted but a no-op — no path ever runs `rag-cli index`.
- proxy_riding (CoinDesk current) writes raw `.html`; browser/proxy_pool write raw `.md`. `filter_new_entries` takes `raw_ext` accordingly.
- `run_scrape_only` reporters are engine-specific: `write_riding_report` for proxy_riding, `write_scrape_report` for browser. They are NOT interchangeable — the browser reporter needs `t_chunk_start`/`elapsed_s` fields absent from riding manifests and would crash.
- Both normal completion and the stall-abort path write the job report to the same `scrape_jobs/{job_id}/` dir; the platform root is never written to by the report step.
- `publish.py` remains on disk but is not called in any path.
