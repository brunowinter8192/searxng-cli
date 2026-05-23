# search07 — Ranking, Pool Architecture, Cache Schema

## Status Quo (IST)

**Architecture:** Two-call drilldown. `search_web` returns an engine-breakdown table (URL counts per engine, no URLs shown). URLs retrieved via `search_engine_drilldown` subcommand per engine from cache.

**Pool building (`build_engine_pools` in `src/search/merge.py`):**
1. Group raw engine results by URL — one bucket per URL, one SearchResult per engine.
2. Assign owner: engine with the **lowest position integer** for that URL (`min(positions)`). Random tie-break via `random.choice`.
3. Return `{engine_name → [SearchResult, ...]}` — each engine's list contains ONLY URLs it owns, sorted by that engine's native position ascending.

**Dedup policy:** URL assigned to exactly one engine. Other engines that returned the same URL lose it from their pool. Position gaps in drilldown output (e.g. positions 1, 3, 7) are normal — gaps = URLs owned by other engines.

**No global ranking.** No class/slot allocation (GENERAL/ACADEMIC/QA removed). No cross-engine sort. Per-engine order is the engine's own native result order.

**Filter modes:** `--books` / `--pdf` / `--docs` apply `filter_urls_by_mode(raw_results, mode)` on the flat raw result list BEFORE `build_engine_pools`. Filtered-out URLs never reach any engine's pool. Breakdown counts reflect post-filter state.

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

## Evidenz

**Pivot rationale:** `decisions/OldThemes/pooling/10_eyeball_engine_provenance.md` (Phase 13.5) — 12-method eval with M11 winner (Jaccard 0.259). Eyeball test showed 30/39 useful (77%) but general-mode worst-case 5/10 useful + 2 SEO-Spam. Engine-provenance analysis showed per-engine signal varies dramatically (DDG 24.4% signal%, Lobsters 0% in the probe). Pooling-as-unified-ranking aborted; pivot to engine-breakdown + drilldown for user-driven engine selection.

**Pre-migration snippet quality data** (retained for reference, from `dev/search_pipeline/01_reports/snippet_quality_20260505_223506.md`):

| Source | N total | N empty | % bloated | Mean clean len |
|--------|---------|---------|-----------|----------------|
| google | 291 | 41 | 98% | 295 |
| duckduckgo | 297 | 0 | 1% | 246 |
| openalex | 242 | 27 | 1% | 381 |
| stack_exchange | 100 | 0 | 0% | 387 |

Engine snippet quality differences now visible to the user via drilldown (they choose which engine's snippets to see).

## Recommendation (SOLL)

Keep — new IST matches the chosen architecture from `decisions/OldThemes/pooling/10_eyeball_engine_provenance.md`.

## Offene Fragen

- **Dedup fairness for engines with many results:** engines with high result-count ceilings (openalex: 200, crossref: 200) win more URLs by position-race vs. engines capped at 10 (duckduckgo, mojeek, semantic_scholar). Whether this is correct behavior or needs a per-engine normalization step is an open question — addressable if user feedback shows certain engines consistently empty in drilldown.
- **Engine result ceilings in breakdown display:** the breakdown table currently shows owned URLs after dedup. A "raw results before dedup" column could help users understand how many URLs each engine contributed before losing URLs to other engines. Not in current scope.

## Quellen

| Source | Type | Notes |
|--------|------|-------|
| `decisions/OldThemes/pooling/10_eyeball_engine_provenance.md` | Internal | Phase 13.5 eyeball test + engine-provenance analysis; pivot rationale |
| `dev/search_pipeline/01_reports/snippet_quality_20260505_223506.md` | Internal | Pre-migration per-source snippet quality data |
