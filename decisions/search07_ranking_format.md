# search07 — Ranking, Snippet Selection, Pagination Cache

## Status Quo (IST)

**Code:** `src/search/search_web.py` (`_deduplicate`, `_format_results`)  
**Method:** First-occurrence-wins URL dedup — whichever engine returns a URL first "wins", all subsequent duplicate returns are discarded regardless of quality.  
**Result shape:** `SearchResult(url, title, snippet, engine, position, preview)` — single `engine` field, no cross-engine snippet aggregation.  
**Output format:** Engine snippet shown verbatim + preview_og + preview_meta appended as separate lines.

Problems:
1. **Specialty engines sink**: OpenAlex, CrossRef, StackExchange, and Scholar URL-spaces barely overlap with general engines (0 crossref↔google overlaps, 0 openalex↔google, 1 stack_exchange↔google in 30-query smoke). In a flat dedup their results appear after the general-engine block and are effectively buried.
2. **Snippet bloat**: Google 98% bloated, Scholar 100% bloated. Formatted output shows these raw.
3. **CrossRef empty/broken**: 251/300 entries have empty abstract; 49/300 have JATS/namespace XML tags (`<jats:p>`) unstripped — shown verbatim as `<jats:p>…</jats:p>`.
4. **No pagination**: `--pages` drove `max_results = pages * 10`; no cache or way to fetch results beyond the initial 20 without re-running the full search.

## Evidenz

Source: `dev/search_pipeline/01_reports/snippet_quality_20260505_223506.md` (1856 URL records, 30-query pool smoke 2026-05-04; earlier report deleted, see git history at 1ad627f).

### Per-source snippet quality

| Source | N total | N empty | % bloated | Mean clean len | Usefulness |
|--------|---------|---------|-----------|----------------|------------|
| google | 291 | 41 | 98% | 295 | 177 |
| duckduckgo | 297 | 0 | 1% | 246 | 169 |
| mojeek | 300 | 1 | 7% | 142 | 96 |
| lobsters | 169 | 0 | 0% | 15 | 15 |
| google scholar | 281 | 1 | 100% | 184 | 117 |
| crossref | 300 | 251 | 73% | 364 | 249 |
| openalex | 242 | 27 | 1% | 381 | 260 |
| stack_exchange | 100 | 0 | 0% | 387 | 226 |
| preview_og | 423 | 0 | 2% | 196 | 142 |

_Usefulness = mean_clean_len × lexical_density (EN+DE combined stoplist)_

### Engine overlap matrix (30 queries)

General engines (Google/DDG/Mojeek) overlap with each other (64 Google↔DDG, 32 DDG↔Mojeek, 24 Google↔Mojeek) but specialty engines practically never overlap with general engines: CrossRef↔Google = 0, OpenAlex↔Google = 0, StackExchange↔Google = 1. Consequence: pure overlap-based ranking buries specialty results. Engine-class slot allocation is the correct fix.

### CrossRef critical finding

49/300 non-empty CrossRef snippets contain raw JATS XML (`<jats:p>…</jats:p>`, `<ns4:p>…</ns4:p>`). 251/300 are entirely empty — no abstract field in the API response. Both cases return broken/empty snippet text today.

## Recommendation (SOLL)

### A. Engine Classification

```python
GENERAL  = {"google", "duckduckgo", "mojeek"}
ACADEMIC = {"google_scholar", "openalex", "crossref"}  # "google_scholar" = ScholarEngine.name
QA       = {"stack_exchange", "lobsters"}
```

### B. Slot Allocation (12 / 6 / 2)

| Class | Slots | Sort key |
|-------|-------|----------|
| GENERAL | 12 | (-overlap_count, min_position) — overlap = number of GENERAL engines that returned this URL |
| ACADEMIC | 6 | (min_position, engine_priority) — openalex=1 > google scholar=2 > crossref=3 |
| QA | 2 | (min_position, engine_priority) — stack_exchange=1 > lobsters=2 |

Hard allocation — no OVERFLOW slot. If a class has fewer results than its target (underflow), total output is less than 20. No auto-fill from other classes. Total output: up to 20 results per `search_web` call; `max_results=10` per engine (constant, `--pages` removed).

URL-level merge aggregates: `engines` list (all engines that found this URL), `snippets` dict (snippet text keyed by engine name), `min_position` (best position across engines), best non-empty title.

#### Class filter via CLI flags

`--general`, `--academic`, `--qa` flags on `search_web`, `search_batch`, `search_more` restrict which slot classes are allocated. Hybrid semantics:

| Flags set | Allocation |
|-----------|-----------|
| None (default) | Hard 12 / 6 / 2 |
| Single class (e.g. `--academic`) | 20 slots to that class, 0 to others |
| Two classes (e.g. `--general --academic`) | Sum of selected defaults: general+academic=18, general+qa=14, academic+qa=8 |
| All three | Same as none — 12 / 6 / 2 |

Class filter is included in the cache key. `search_more` must use the same flags as the original `search_web` call to produce a cache hit.

#### Filter mode fanout (updated 2026-05-21 — bucket-uniformity invariant)

`--books`, `--pdf`, `--docs` flags do NOT restrict which engines participate in the fanout. All 9 engines fire on every query regardless of filter mode. Filter modes act via two mechanisms only:

1. **Per-engine query modifier** — engines in `_BOOKS_ENGINES` / `_PDF_ENGINES` / `_DOCS_ENGINES` (`filter_modes.py`) receive the relevant suffix (`+book`, `+pdf`, `+documentation`). Other engines receive the bare query.
2. **Post-merge URL filter** — `filter_urls_by_mode()` applies `is_book_url` / `is_pdf_url` / `is_docs_url` to the merged ranked list after slot allocation.

No engines are excluded from the `selected` dict in filter mode. `apply_filter_mode()` always returns `excluded={}`. `_ENGINE_BOOKS/PDF/DOCS` constants are modifier-target sets, not restriction sets.

### C. Snippet Selection Priority (per-URL, 7-step)

Rationale: query-relevant extracts beat generic page descriptions when similarly clean. og is a page-author-curated meta description (generic); DDG/Mojeek snippets are search-engine-extracted excerpts based on query terms (query-relevant). For search-result display, query-relevance wins when cleanliness is similar. og remains the right fallback when no clean engine snippet is available.

| Priority | Condition | Source |
|----------|-----------|--------|
| 1 | openalex in engines | openalex snippet (1% bloat, usefulness=260) |
| 2 | stack_exchange in engines | stack_exchange snippet (0% bloat, usefulness=226) |
| 3 | crossref in engines | crossref snippet (JATS-stripped or synthesized — see D) |
| 4 | (none of above) | DDG snippet (1% bloat, query-relevant) |
| 5 | DDG absent | Mojeek snippet (7% bloat, query-relevant) |
| 6 | no DDG/Mojeek | og preview (2% bloat, page-generic, 423 samples) |
| 7 | no og | Google/Scholar snippet after bloat-strip (9 patterns) |
| — | lobsters-only + no og | domain extracted from URL (netloc) |

Bloat-strip patterns (`_strip_bloat`) copied verbatim from `dev/search_pipeline/snippet_quality_analysis.py`. Source of truth lives there.

### D. CrossRef Synthesis Fallback

In `crossref.py._parse_results`: if `abstract` is present → strip all XML tags (`re.sub(r'<[^>]+>', '', abstract).strip()`). If absent or whitespace-only → synthesize from metadata:

```
"{Family}, {I}. [et al.] ({year}), {container-title[0]}"
```

Year source priority: `published-print` → `issued` → `published-online` (first non-empty `date-parts[0][0]`).

Examples:
- `"de Groot, C. (2022), Asynchronous Python Programming with Asyncio and Async/await"`
- `"Brown, J. et al. (2023), Nature Machine Intelligence"`
- `"(2019)"` — no author (anonymous preprint)

### E. OpenAlex Citation Suffix (threshold=50)

If `cited_by_count > 50`: append ` (Cited {n}×)` to snippet. Threshold 50 is a first-cut tuning parameter — papers below 50 citations are in the "normal to unknown" range; appending `(Cited 0×)` on most academic results would be noise.

### F. Disk Cache Schema + search_more Pagination

**Cache location:** `~/.cache/searxng/<sha256_16char>.json`  
**Key:** `sha256(f"{query.lower().strip()}|{language}|{engines or ''}|{time_range or ''}|{sorted_class_filter}").hexdigest()[:16]`  
**TTL:** 1 hour (mtime-based). Expired = cache miss.  
**Write:** atomic via `tempfile.NamedTemporaryFile` + `os.replace`.

**JSON structure:**
```json
{
  "query": "...", "language": "en", "engines": null, "time_range": null,
  "timestamp": 1746391200, "returned_count": 23,
  "slot_counts": {"general": 12, "academic": 5, "qa": 2},
  "urls": [
    {"url": "...", "title": "...", "snippet": "...", "engines": [...], "snippets": {...}, "snippet_source": "openalex"},
    ...
  ]
}
```

`urls` = full `_merge_and_rank` output (not just top-20). `search_more` slices from index 20. `slot_counts` records actual fill per class (may be below target on underflow). `snippet_source` per URL reflects the score-based selection applied (highest `clean_len × lexical_density`); null for URLs beyond position 20 (not passed through snippet selection).

**`search_more` semantics:**

| Cache state | Behavior | Header note |
|-------------|----------|-------------|
| Hit + fresh | Slice `urls[20:20+count]`, format numbered from 21 | `# search_more (cached)` |
| Hit + fresh but slice empty | Exit with message | `# search_more: no further URLs in cached pool` |
| Miss or expired | Run fresh `search_web_workflow`, return `urls[:count]` | `# search_more (cache miss — fresh ranking, only first N shown)` |

## Offene Fragen

- **og vs DDG priority** — og (2% bloat) is marginally cleaner than DDG (1%), but DDG mean clean length (246) > og (196) and DDG is query-relevant. Current order (DDG > og) is theory-correct; confirm with a side-by-side eyeball after D8 demo. Candidate to revisit if og descriptions prove more useful in practice.
- **Citation threshold tuning** — 50 is first-cut for OpenAlex citation suffix. Adjust after smoke: if most academic results in top slots have >50 citations → lower threshold; if many spurious `(Cited 51×)` annotations appear → raise it.
- **Slot share tuning** — 12/6/2 is the current hard allocation. Smoke may reveal consistent underflows (e.g. fewer than 6 academic results for general queries) → adjust ACADEMIC target down, GENERAL up.
- **Cross-site StackExchange probe** — only `stackoverflow.com` has been seen in smoke results. StackExchange covers 170+ sites (math, serverfault, etc.). Pending: broader query set to confirm coverage.
- **search_more offset fixed at 20** — `search_more` always slices from index 20. If the user wants a different window (e.g. results 10-20 from a sub-query), a `--offset` flag could be added. Not in current scope.

## Quellen

| Source | Type | Notes |
|--------|------|-------|
| `dev/search_pipeline/01_reports/snippet_quality_20260505_223506.md` | Internal | Data basis: per-source bloat %, overlap matrix, side-by-side examples |
| dev/search_pipeline/01_reports/search_smoke_20260504_023641.md (deleted, see git 1ad627f) | Internal | 30-query 8-engine pool smoke |
| `dev/search_pipeline/snippet_quality_analysis.py` | Internal | Bloat detection + strip_bloat patterns |
| Bead `searxng-a45` | Internal | Problem framing and KPI definition |
| CrossRef REST API (`api.crossref.org/works`) | External | JSON shape verified via live probe 2026-05-04 |
