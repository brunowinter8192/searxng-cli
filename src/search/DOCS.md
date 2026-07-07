# search/

pydoll-based parallel search pipeline. Exposes `search_web_workflow()` (single-query, fan-out across engines via asyncio.gather, returns engine-breakdown TextContent + writes per-engine pool cache) consumed by `cli.py`. Plus `fetch_search_results()` sync wrapper consumed by dev scripts.

**Active engines (9):** google, duckduckgo, mojeek, lobsters, semantic_scholar (pydoll); crossref, openalex, stack_exchange, open_library (HTTP). Google Scholar (`engines/scholar.py`) is decoupled from the default pool. brave / startpage / bing were dropped from the engine set.

**Two-call drilldown architecture (2026-05-23):** `search_web` returns an engine-breakdown table (counts only, no URLs). URLs per engine retrieved via `search_engine_drilldown` CLI subcommand, which reads the per-engine cache written by `search_web`. Dedup: URLs owned by the engine with the lowest position; random tie-break. No global ranking, no class/slot allocation.

**Filter-flag trio (`--books` / `--pdf` / `--docs`):** three filter flags. Each applies a per-engine query modifier + post-fanout URL filter before `build_engine_pools`. Breakdown table counts reflect filtered pool. Wiring in `search_web_workflow`: `apply_filter_mode` → set query_modifier_map → `filter_urls_by_mode(raw_results, mode)` → `build_engine_pools(filtered)`.

## search_web.py

**Purpose:** Search orchestrator. Two entry points:
- `search_web_workflow(query, language="en", time_range=None, engines=None, ..., engine_timeout=None, _with_timings=False, query_modifier_map=None)` — single query, fan-out across all active engines via `asyncio.gather` of `_engine_with_timing` tasks. After fanout: `filter_urls_by_mode(raw_results, mode)` → `build_engine_pools(filtered)` → **post-dedup pool cap** → `_format_breakdown` → `cache_write(capped_pools)`. **Post-dedup pool cap:** after `build_engine_pools`, K = `len(pools['google'])` if > 0 else 10. Each engine's pool trimmed to `pool[:K]` — engines with fewer than K URLs unaffected. Prevents 200-URL drilldown floods from CrossRef/OpenAlex/Stack Exchange/Open Library. If Google was CAPTCHA'd or not in the engine set, K falls back to 10. **Three-tier timeout architecture:** (1) `ENGINE_WATCHDOG_TIMEOUT=3.6s` global default. (2) `ENGINE_WATCHDOG_OVERRIDE: dict[str, float]` per-engine override — `{"open_library": 6.0, "semantic_scholar": 5.0, "crossref": 6.0}`. (3) `RATE_WAIT_TIMEOUT=60.0s` cap on token-bucket acquire → `RATE_SKIP`. Status sub-classification: `_engine_with_timing` returns 5-tuple `(results, rate_wait_ms, search_ms, status, drop_reason)`. TIMEOUT into 3 sub-statuses (`TIMEOUT_WATCHDOG / TIMEOUT_NONCOOP / TIMEOUT_HTTPX`), ERROR into 4 (`ERROR_BROWSER / ERROR_HTTP / ERROR_PARSE / ERROR_OTHER`). **Two-record logging:** `_query_engines_concurrent` writes `engine_run` record immediately after fanout; `search_web_workflow` writes `workflow_summary` record after pool-build. `_select_engines(engines)` returns `(selected_dict, excluded_dict)`; default 9-engine set via `_DEFAULT_ENGINES`. Per-engine result caps in `ENGINE_MAX_RESULTS` dict. Returns `list[TextContent]` (one element: breakdown table); with `_with_timings=True` returns `(list, dict)` where `dict` has `engine_fanout_ms, pool_build_ms, cache_write_ms, total_ms, engine_details`. **CLI dispatch:** hardcodes `language="en"`, `time_range=None`, `engines=None` — full signature retained for dev-script callers.
- `fetch_search_results()` — sync wrapper for dev scripts; returns raw result list, no pool-building.

**Input:** Query string, language, time range, engine filter, filter-mode flags.
**Output:** `list[TextContent]`. Side effect: writes disk cache `~/.cache/searxng/<key>.json`.

## merge.py

**Purpose:** Cross-engine URL dedup and per-engine pool builder. `build_engine_pools(results: list[SearchResult]) -> dict[str, list[SearchResult]]`: (1) group all SearchResult objects by URL — one bucket per URL, one entry per engine; (2) for each URL, determine owner = engine with lowest position value; random choice on position ties via `random.choice`; (3) return `{engine_name → [SearchResult, ...]}` where each engine's list contains ONLY URLs it owns, sorted by that engine's native position ascending. `engine_positions: dict[str, int]` field on each returned result records all engines' positions for that URL.
**Public interface:** `build_engine_pools`.
**Input:** `list[SearchResult]` from engine fan-out (may contain same URL from multiple engines).
**Output:** `dict[str, list[SearchResult]]` — per-engine owned pools. Called from `search_web.search_web_workflow`.

## snippet.py

**Purpose:** Snippet text utilities for drilldown display. `_strip_bloat(text)` — HTML unescape + 9 bloat patterns (doubled prefix, Web results prefix, Featured snippet prefix, Read more, social proof, URL breadcrumbs, date prefix, HTML entities, Tagged-with suffix). `_truncate(text, max_len)` — sentence-aware truncation: period+space cut in `[max_len/2, max_len-1]`, else last-space cut + `…`, else hard-cut + `…`. `MAX_SNIPPET_LEN = 500`. Used by `cache.format_engine_pool` for drilldown output.
**Public interface:** `_strip_bloat`, `_truncate`, `MAX_SNIPPET_LEN`.
**Input:** Raw snippet text string.
**Output:** Cleaned/truncated string.

## cache.py

**Purpose:** Disk cache for per-engine pool results. Backs `search_engine_drilldown` CLI subcommand — reads per-engine URL lists without re-running the engine fan-out. **Cache key:** `sha256(query|language|engines|time_range[|modifier_id])[:16]` — `class_filter` removed (no longer a concept); `modifier_id` kept for `--books`/`--pdf`/`--docs` separation. **Path:** `~/.cache/searxng/<key>.json`. **TTL:** 1 hour, mtime-based. **Atomic writes** via `tempfile.mkstemp` + `os.replace`. **JSON structure:** `{query, language, engines, time_range, timestamp, pools: {engine_name: [{url, title, snippet, position}, ...]}}` — `pools` is the full per-engine result dict from `build_engine_pools`; `position` is engine's native rank for re-emitting in drilldown. `format_engine_pool(pool, engine_name, query) -> str` formats one engine's pool as a numbered list with `_strip_bloat`+`_truncate` applied to each snippet.
**Public interface:** `cache_key`, `cache_path`, `cache_write`, `cache_read`, `format_engine_pool`.
**Input:** `cache_write` takes key + `pools: dict[str, list[SearchResult]]` + search params. `cache_read` returns dict or None. `format_engine_pool` takes cached pool list (dicts) + engine name + query.
**Output:** Persisted JSON; `cache_read` returns dict on hit or None on miss/expired.

## browser.py

**Purpose:** pydoll Chrome lifecycle. Starts a single shared Chrome instance on first call, creates a new tab per engine for isolation. Applies fingerprint patches (WebGL, canvas, permissions) at launch. Three cleanup paths:
- `kill_tab(tab)` — async, per-engine tab cleanup in engine `finally` blocks. Uses browser-level `Target.closeTarget` CDP command (via `_browser._execute_command`, NOT the hung tab connection). 5s `asyncio.wait_for` cap. Cleans `_browser._tabs_opened`. Replaces the former `tab.close()` path which caused 65s hangs on TIMEOUT_NONCOOP cases (`Page.close` via tab connection → hung renderer → 60s pydoll fallback).
- `close_browser()` — async, for in-loop shutdown (used by dev scripts). Issues CDP `Browser.close` and waits for response.
- `kill_stale_chrome()` — sync `pkill -f "user-data-dir=<SESSION_DIR>"`, nuclear OS-level fallback.

**Input:** None (singleton on first access).
**Output:** pydoll Chrome instance and new tab contexts.

## rate_limiter.py

**Purpose:** Per-engine token-bucket rate limiter. Module-level `_limiters: dict[str, RateLimiter]` registry; engines populate at module-import (`_limiters["<name>"] = RateLimiter(max_requests=4, window_seconds=60)`), workflow consumes via `get_limiter(name).acquire()` BEFORE invoking engine work in `search_web._engine_with_timing`.
**Input:** Engine name (via `get_limiter`).
**Output:** Async context that blocks until a token is available.

## status.py

**Purpose:** Engine-status string constants for query log + audit. 17 constants total: 5 legacy (`OK / EMPTY / TIMEOUT / ERROR / RATE_SKIP`) + 5 EMPTY sub-statuses + 3 TIMEOUT sub-statuses + 4 ERROR sub-statuses. Imported as `from src.search import status as S` in `search_web.py`.
**Public interface:** all 17 constants are module-level strings.

## query_logger.py

**Purpose:** Append-only JSONL query log. `log_query(record: dict)` writes one JSON line. Path from `SEARXNG_QUERY_LOG_PATH` env var, fallback `src/logs/query_log.jsonl`. **Two record types:** `engine_run` (written by `_query_engines_concurrent` for every call) and `workflow_summary` (written by `search_web_workflow` after pool-build — no `preview` field in new architecture). Inspector: `dev/search_pipeline/inspect_query_log.py --tail N`.
**Record fields:** `ts`, `query`, `language`, `engines_requested`, `engines_excluded`, `total_wall_ms`, `bottleneck_engine`, `engines` ({name: {rate_wait_ms, search_ms, status, result_count, drop_reason}}).
**Calls out:** `src/log_janitor.py` (`maybe_prune_jsonl`).

## result.py

**Purpose:** `SearchResult` dataclass. Fields: `url, title, snippet, engine, position, preview, engines, snippets, engine_positions`. `engine_positions: dict[str, int]` — populated by `build_engine_pools`; maps engine name → that engine's native position for this URL (covers all engines that returned the URL, not just the owner). `engines: list[str]` and `snippets: dict[str, str]` retained for backward compat with dev scripts that call `engine.search()` directly. `preview: dict | None` retained for backward compat (no longer populated in production path).

## filter_modes.py

**Purpose:** Engine restriction and URL filtering for the three CLI filter flags (`--books` / `--pdf` / `--docs`), plus `_DEFAULT_ENGINES` constant. `apply_filter_mode(selected, books, pdf, docs, query_modifier_map)` resolves the 3-way mutex (`pdf > docs > books`), sets the effective `query_modifier_map` (per-engine query suffix), returns `(selected, qmm, mode_id, excluded)`. `filter_urls_by_mode(raw_results, mode)` applies the post-fanout URL filter via `is_book_url` / `is_pdf_url` / `is_docs_url` on the flat `raw_results` list BEFORE `build_engine_pools` — filtered-out URLs never reach any engine's pool. Engine subsets: `_DEFAULT_ENGINES = {google, crossref, duckduckgo, mojeek, lobsters, openalex, stack_exchange, semantic_scholar, open_library}`, `_BOOKS_ENGINES`, `_PDF_ENGINES`, `_DOCS_ENGINES` are modifier-target sets, not restriction sets — all engines still fire on every query regardless of filter mode.
**Public interface:** `apply_filter_mode`, `filter_urls_by_mode`, `_DEFAULT_ENGINES`.

## book_whitelist.py / pdf_filter.py / docs_filter.py

See prior DOCS.md entries — these modules are unchanged. `is_book_url`, `is_pdf_url`, `is_docs_url` called from `filter_modes.filter_urls_by_mode` on flat raw_results pre-pool-build.

## engines/

Per-engine parser modules. Each exports an `Engine` class with `search(query, language, max_results)` returning `list[SearchResult]`. Rate-limiter integration, entity decoding, sub-status interface unchanged — see individual engine entries in prior DOCS.md. Engine parsers were NOT modified by the drilldown migration. Post-migration changes: all 5 pydoll engines switched `finally: await tab.close()` → `finally: await kill_tab(tab)` (bead 7u5); title-keyword CAPTCHA check removed from `_diagnose_empty` in google/duckduckgo/semantic_scholar (bead 18v).

### engines/base.py (18 LOC)
Abstract `BaseEngine` parent — `search()` + default `search_with_reason()` that delegates to `search()`.

## Stealth Configuration

Active stealth configuration lives in `src/search/browser.py` (hardcoded JS patches, UA, window size, Chrome options) and per-engine files (SOCS cookie for Google).
