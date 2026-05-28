# Search Pipeline Step 1: Engines

## Status Quo (IST)

**Code:** `src/search/search_web.py` (`ENGINES` dict, `ENGINE_WATCHDOG_OVERRIDE`, `RATE_WAIT_TIMEOUT`); `src/search/filter_modes.py` (`_DEFAULT_ENGINES`, `apply_filter_mode()`); `src/search/engines/` (9 active engine files)

**Active engines: 9** — 5 pydoll Chrome browser + 4 httpx HTTP API. Uniform 4 req/min token-bucket per engine.

| Engine | Class¹ | Implementation | Watchdog | Max Results |
|--------|--------|----------------|----------|-------------|
| google | GENERAL | pydoll Chrome | 3.6s | 100 |
| duckduckgo | GENERAL | pydoll Chrome | 3.6s | 10 |
| mojeek | GENERAL | pydoll Chrome | 3.6s | 10 |
| lobsters | QA | pydoll Chrome | 3.6s | 20 |
| semantic_scholar | ACADEMIC | pydoll Chrome | 5.0s² | 10 |
| crossref | ACADEMIC | httpx | 6.0s² | 200 |
| openalex | ACADEMIC | httpx | 3.6s | 200 |
| stack_exchange | QA | httpx | 3.6s | 100 |
| open_library | GENERAL | httpx | 6.0s² | 100 |

¹ Class labels are descriptive only — no runtime slot allocation exists. See `decisions/search07_ranking_format.md` for current pool architecture (per-engine dedup pools, no cross-engine ranking).

² `ENGINE_WATCHDOG_OVERRIDE` entries in `search_web.py`: `semantic_scholar` 5.0s (CSR React hydration 0.5-2.5s), `crossref` 6.0s (API response 1-5s range), `open_library` 6.0s (server-dominated latency 1.4-5.8s). All others use `ENGINE_WATCHDOG_TIMEOUT = 3.6s`.

**Rate limiting:** `max_requests=4, window_seconds=60` configured in every engine file's INFRASTRUCTURE section (via `get_limiter()` call at import time). `RATE_WAIT_TIMEOUT = 60.0` in `search_web.py` — outer `asyncio.wait_for` guard on `acquire()` calls; dormant under normal 4 req/min load, guards against token-bucket saturation. See `decisions/rate_limiting.md`.

**Bucket-uniformity invariant:** All 9 engines fire on every query regardless of filter mode. `--books` / `--pdf` / `--docs` apply only per-engine query modifiers and post-merge URL filtering — never restrict which engines participate. `apply_filter_mode()` in `filter_modes.py` returns `excluded={}` in all code paths.

**Inert engine:** `src/search/engines/scholar.py` — file present but nothing imports it. Not in `ENGINES`, `_DEFAULT_ENGINES`, or `ENGINE_WATCHDOG_OVERRIDE`. Parked for g82 pooling-rework re-integration (Google-free pool design required; see Offene Fragen).

**Plugin engines** (not in `ENGINES` dict, not in this pipeline): ArXiv, GitHub, Reddit — URL discovery via MCP plugins; content fetched by dedicated plugin.

## Evidenz

Per-engine implementation probes and smoke baselines — `decisions/OldThemes/engine_expansion_2026-05/`:

| Engine | OldThemes file | Key finding |
|--------|---------------|-------------|
| google | _(pre-engine-cut baseline)_ | DOM selectors in `config.yml`; no browser changes post-cut |
| duckduckgo | `duckduckgo.md` | URL cleaning required (uddg param); no consent banner |
| mojeek | `mojeek.md` | 403 at >1.2 req/s burst; 4 req/min safe; arc=none param |
| lobsters | `lobsters.md` | No body text on search page; snippet = domain label |
| semantic_scholar | `semantic_scholar.md` | TLDR selector (DOM drift 2026-05-08); CSR watchdog 5.0s |
| crossref | _(HTTP API, no probe needed)_ | 4 req/min; `rows=` param; watchdog 6.0s |
| openalex | `openalex.md` | Abstract inverted index reconstruction; `mailto=` polite pool |
| stack_exchange | `stack_exchange.md` | 300 req/day anon; `filter=withbody`; 15/30 smoke OK |
| open_library | `open_library.md` | A/B: 9/10 book queries widened; 81.2 avg OL URLs; watchdog 6.0s |
| bing | `bing_dropped.md` | Dropped 2026-05-04: DOM drift + no added value over DDG |
| HN | `hn_dropped.md` | Dropped 2026-05-04: cascade-hostile empty-backoff mechanism |
| Scholar | `scholar_reeval.md` | _JS_PARSE fix 2026-05-03; removed 2026-05-21 (see below) |

**Scholar removal + uniformity invariant rationale:** `decisions/OldThemes/bee_cdp_starvation/fix_summary.md` — Phase 3 probe identified tokencap-path as primary cascade mechanism. RATE_WAIT_TIMEOUT=60 + Scholar removal + bucket-uniformity eliminated RATE_SKIP cascade. 20-query smoke post-fix: 0 RATE_SKIP events, 294s total wall (9 engines × 20 queries).

**No-backoff baseline (post-removal, 2026-05-22):** `dev/search_pipeline/01_reports/no_backoff_baseline_20260522_211439.md` — 30/30 queries with results, 0 RATE_SKIP events. See `decisions/rate_limiting.md` Evidenz.

## Recommendation (SOLL)

**Keep** — current 9-engine set stable post-bee_fix. 30/30 queries OK, 0 RATE_SKIP events (30-query baseline 2026-05-22).

**Pending — Scholar re-integration:** requires g82 pooling-rework. `scholar.py` logic intact and ready; blocked on pool constant design in `filter_modes.py`.

**Pending — Marginalia probe:** try-or-drop at hosted endpoint `search.marginalia.nu` when there is a concrete use-case gap in the current pool. See `decisions/OldThemes/engine_expansion_2026-05/00_research_context.md`.

## Offene Fragen

- **g82 pooling-rework:** which pool definition places Scholar in a Google-free set? What inter-session CAPTCHA behavior is expected at 4/min in a Scholar-only pool?
- **SE API quota:** 300 req/day anonymous vs 10k/day with free registered key — sufficient for agentic-search volume?
- **`open_library` sub-status labelling:** `ERROR_OTHER` returned for non-book queries (HTTP engine returning `[]`). `search_with_reason()` could provide finer sub-status; not blocking current operation.

## Quellen

| Source | Notes |
|--------|-------|
| `src/search/search_web.py` | ENGINES dict, ENGINE_WATCHDOG_OVERRIDE, RATE_WAIT_TIMEOUT — ground truth |
| `src/search/filter_modes.py` | _DEFAULT_ENGINES, apply_filter_mode() — uniformity invariant |
| `src/search/engines/*.py` | Per-engine max_requests=4/60s |
| `decisions/OldThemes/engine_expansion_2026-05/` | Per-engine implementation history |
| `decisions/OldThemes/bee_cdp_starvation/fix_summary.md` | Cascade fix rationale, Scholar removal, uniformity |
| `decisions/search07_ranking_format.md` | Current pool/drilldown architecture; class labels removed |
| `decisions/rate_limiting.md` | RATE_WAIT_TIMEOUT policy, fail-fast, no-backoff baseline |
