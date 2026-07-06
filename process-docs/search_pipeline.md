# Search Pipeline

## Engines

### Current State

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

¹ Class labels are descriptive only — no runtime slot allocation exists. See **Ranking & Pool Architecture** section below for current pool architecture (per-engine dedup pools, no cross-engine ranking).

² `ENGINE_WATCHDOG_OVERRIDE` entries in `search_web.py`: `semantic_scholar` 5.0s (CSR React hydration 0.5-2.5s), `crossref` 6.0s (API response 1-5s range), `open_library` 6.0s (server-dominated latency 1.4-5.8s). All others use `ENGINE_WATCHDOG_TIMEOUT = 3.6s`.

**Rate limiting:** `max_requests=4, window_seconds=60` configured in every engine file's INFRASTRUCTURE section (via `get_limiter()` call at import time). `RATE_WAIT_TIMEOUT = 60.0` in `search_web.py` — outer `asyncio.wait_for` guard on `acquire()` calls; dormant under normal 4 req/min load, guards against token-bucket saturation. See `decisions/rate_limiting.md`.

**Bucket-uniformity invariant:** All 9 engines fire on every query regardless of filter mode. `--books` / `--pdf` / `--docs` apply only per-engine query modifiers and post-merge URL filtering — never restrict which engines participate. `apply_filter_mode()` in `filter_modes.py` returns `excluded={}` in all code paths.

**Inert engine:** `src/search/engines/scholar.py` — file present but nothing imports it. Not in `ENGINES`, `_DEFAULT_ENGINES`, or `ENGINE_WATCHDOG_OVERRIDE`. Parked for g82 pooling-rework re-integration (Google-free pool design required; see Open Questions).

**Plugin engines** (not in `ENGINES` dict, not in this pipeline): ArXiv, GitHub, Reddit — URL discovery via MCP plugins; content fetched by dedicated plugin.

**Tab teardown:** `kill_tab()` in `src/search/browser.py` — calls `_browser._execute_command(TargetCommands.close_target(target_id))` over the browser-level WebSocket (separate from the tab connection). Called in `finally` of all 5 pydoll engine `search_with_reason()` methods. Replaced `tab.close()` (`Page.close` via tab connection → hung renderer → pydoll 60s fallback → 65s total on NONCOOP). 5s `asyncio.wait_for` cap on `close_target` guards against wedged browser channel. Rationale: `decisions/OldThemes/pydoll_noncoop_teardown/01_teardown_design.md`.

**`_diagnose_empty` title-keyword check:** Removed from `google.py`, `duckduckgo.py`, `semantic_scholar.py` (dead code for modern reCAPTCHA Enterprise; prior robust block-detection runs before `_diagnose_empty` in all three). Retained in `mojeek.py`, `lobsters.py` (sole `EMPTY_BLOCK` detection path).

### Evidence

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

**No-backoff baseline (post-removal, 2026-05-22):** `dev/search_pipeline/01_reports/no_backoff_baseline_20260522_211439.md` — 30/30 queries with results, 0 RATE_SKIP events. See `decisions/rate_limiting.md` Evidence.

### Open Questions

- **g82 pooling-rework:** which pool definition places Scholar in a Google-free set? What inter-session CAPTCHA behavior is expected at 4/min in a Scholar-only pool?
- **SE API quota:** 300 req/day anonymous vs 10k/day with free registered key — sufficient for agentic-search volume?
- **`open_library` sub-status labelling:** `ERROR_OTHER` returned for non-book queries (HTTP engine returning `[]`). `search_with_reason()` could provide finer sub-status; not blocking current operation.

---

## Ranking & Pool Architecture

### Current State

**Architecture:** Two-call drilldown. `search_web` returns an engine-breakdown table (URL counts per engine, no URLs shown). URLs retrieved via `search_engine_drilldown` subcommand per engine from cache.

**Pool building (`build_engine_pools` in `src/search/merge.py`):**
1. Group raw engine results by URL — one bucket per URL, one SearchResult per engine.
2. Assign owner: engine with the **lowest position integer** for that URL (`min(positions)`). Random tie-break via `random.choice`.
3. Return `{engine_name → [SearchResult, ...]}` — each engine's list contains ONLY URLs it owns, sorted by that engine's native position ascending.

**Dedup policy:** URL assigned to exactly one engine. Other engines that returned the same URL lose it from their pool. Position gaps in drilldown output (e.g. positions 1, 3, 7) are normal — gaps = URLs owned by other engines.

**No global ranking.** No class/slot allocation (GENERAL/ACADEMIC/QA removed). No cross-engine sort. Per-engine order is the engine's own native result order.

**Filter modes:** `--books` / `--pdf` / `--docs` apply `filter_urls_by_mode(raw_results, mode)` on the flat raw result list BEFORE `build_engine_pools`. Filtered-out URLs never reach any engine's pool. Breakdown counts reflect post-filter state.

**Pool Cap (post-dedup):** applied in `search_web_workflow` after `build_engine_pools` returns:
```python
google_count = len(pools.get("google", []))
K = google_count if google_count > 0 else 10
capped_pools = {eng: pool[:K] for eng, pool in pools.items()}
```
Each engine's pool is trimmed to `pool[:K]`. Engines with fewer than K URLs are unaffected. K = google's dedup-pool size; fallback K=10 when google returned 0 results (CAPTCHA) or was not in the selected engine set. Both `_format_breakdown` and `cache_write` receive `capped_pools`. Rationale: CrossRef/OpenAlex return up to 200 URLs, Stack Exchange up to 100, Open Library up to 100 — uncapped drilldown would flood context. The google-anchored K provides a natural, query-adaptive bound (typical 8-11 URLs). The capped-pool idea originates from `decisions/OldThemes/pooling/05_capped_pool_probe.md` (Phase 9 probe, K=google_count architecture) — not shipped then because the broader pooling investigation was abandoned; reintroduced now in the two-call architecture as a sanity bound on drilldown context size.

**Cache schema (`~/.cache/searxng/<key>.json`, 1h TTL, atomic write):**
```json
{
  "query": "rust async runtime",
  "language": "en",
  "engines": null,
  "time_range": null,
  "timestamp": 1748038800,
  "pools": {
    "google": [{"url": "...", "title": "...", "snippet": "...", "position": 1}, ...],
    "lobsters": [...],
    "duckduckgo": [],
    "mojeek": [],
    "openalex": [...],
    "crossref": [...],
    "stack_exchange": [...],
    "semantic_scholar": [...],
    "open_library": []
  }
}
```

**Cache key:** `sha256(query|language|engines|time_range[|modifier_id])[:16]` — `class_filter` removed (concept eliminated); `modifier_id` kept for `--books`/`--pdf`/`--docs` separation.

**Snippet display:** drilldown output applies `_strip_bloat` + `_truncate(MAX_SNIPPET_LEN=500)` from `snippet.py` to each engine snippet. No preview-fetch, no og/meta enrichment — engine-provided snippet is the only snippet source.

**Output format (`search_web`):**
```
Engine breakdown for "rust async runtime":
  google               9
  duckduckgo           8
  mojeek               6
  lobsters             4
  openalex            11
  crossref             7
  stack_exchange       5
  semantic_scholar     3
  open_library         0

Use `searxng-cli search_engine_drilldown "rust async runtime" --engine <name>` to see URLs per engine.
```

**Output format (`search_engine_drilldown`):** numbered list in engine's native position order, stripped snippet per URL, position gaps allowed.

### Evidence

**Pivot rationale:** `decisions/OldThemes/pooling/10_eyeball_engine_provenance.md` (Phase 13.5) — 12-method eval with M11 winner (Jaccard 0.259). Eyeball test showed 30/39 useful (77%) but general-mode worst-case 5/10 useful + 2 SEO-Spam. Engine-provenance analysis showed per-engine signal varies dramatically (DDG 24.4% signal%, Lobsters 0% in the probe). Pooling-as-unified-ranking aborted; pivot to engine-breakdown + drilldown for user-driven engine selection.

**Pre-migration snippet quality data** (retained for reference, from `dev/search_pipeline/01_reports/snippet_quality_20260505_223506.md`):

| Source | N total | N empty | % bloated | Mean clean len |
|--------|---------|---------|-----------|----------------|
| google | 291 | 41 | 98% | 295 |
| duckduckgo | 297 | 0 | 1% | 246 |
| openalex | 242 | 27 | 1% | 381 |
| stack_exchange | 100 | 0 | 0% | 387 |

Engine snippet quality differences now visible to the user via drilldown (they choose which engine's snippets to see).

### Open Questions

- **Dedup fairness for engines with many results:** engines with high result-count ceilings (openalex: 200, crossref: 200) win more URLs by position-race vs. engines capped at 10 (duckduckgo, mojeek, semantic_scholar). Whether this is correct behavior or needs a per-engine normalization step is an open question — addressable if user feedback shows certain engines consistently empty in drilldown.
- **Engine result ceilings in breakdown display:** the breakdown table currently shows owned URLs after dedup. A "raw results before dedup" column could help users understand how many URLs each engine contributed before losing URLs to other engines. Not in current scope.

---

## Sources

| Source | Notes |
|--------|-------|
| `src/search/search_web.py` | ENGINES dict, ENGINE_WATCHDOG_OVERRIDE, RATE_WAIT_TIMEOUT — ground truth |
| `src/search/filter_modes.py` | _DEFAULT_ENGINES, apply_filter_mode() — uniformity invariant |
| `src/search/engines/*.py` | Per-engine max_requests=4/60s |
| `decisions/OldThemes/engine_expansion_2026-05/` | Per-engine implementation history |
| `decisions/OldThemes/bee_cdp_starvation/fix_summary.md` | Cascade fix rationale, Scholar removal, uniformity |
| `decisions/rate_limiting.md` | RATE_WAIT_TIMEOUT policy, fail-fast, no-backoff baseline |
| `decisions/OldThemes/pooling/10_eyeball_engine_provenance.md` | Phase 13.5 eyeball test + engine-provenance analysis; pivot rationale |
| `dev/search_pipeline/01_reports/snippet_quality_20260505_223506.md` | Pre-migration per-source snippet quality data |
