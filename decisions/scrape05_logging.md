# scrape05 — Per-URL Scrape Logging

## Status Quo (IST)

**Architecture:** Sidecar split. Every `scrape_url` and `scrape_url_raw` call emits two artifacts:
1. One structured JSONL record → `src/logs/scrape_log.jsonl` (append-only, gitignored)
2. One content sidecar → `src/logs/scrape_content/<ts>_<url_slug>.md` — the exact final content the caller received

**What is logged:** the FINAL output the caller receives, not intermediate state. For `scrape_url` (filtered mode): the truncated `fit_markdown` (or `raw_markdown` after fallback), after `truncate_content` is applied. For `scrape_url_raw`: the full `raw_markdown` that gets saved to `output_dir`. Pre-filter and pre-truncation content is NOT logged as sidecar — only the bytes the agent sees.

**Sidecar policy by outcome:**
- `outcome == "ok"` → sidecar written (final content)
- `outcome == "garbage"` → sidecar written (`garbage_content` field from `try_scrape` — content that triggered garbage classification, for inspection)
- `outcome == "empty"` | `"timeout"` | `"error"` → `content_path: null`, no sidecar written

**Log path:** `SEARXNG_SCRAPE_LOG_PATH` env var → fallback `src/logs/scrape_log.jsonl`. Sidecar dir: `<log_dir>/scrape_content/`. Fail-soft: write errors are logged as WARNING, scrape result still reaches caller.

**Implementation:** `src/scraper/scrape_logger.py` — `log_scrape(record)` + `write_sidecar(url, ts, content, outcome, mode) -> str | None`. Called at every return path of `scrape_url_workflow` and `scrape_url_raw_workflow`.

**JSONL record schema:**
```json
{
  "ts": "2026-05-23T22:30:01.234Z",
  "url": "https://example.com/article",
  "domain": "example.com",
  "mode": "filtered",
  "outcome": "ok",
  "phase_used": "browser_1a",
  "phases_attempted": ["fastpath", "browser_1a"],
  "timings_ms": {
    "fastpath": 412,
    "browser_1a": 3187,
    "browser_1b": null,
    "browser_2_stealth": null,
    "filter": null,
    "total_wall": 3622
  },
  "http_status": 200,
  "content_type": "text/html; charset=utf-8",
  "bytes_returned": 5104,
  "bytes_raw_markdown": 14823,
  "fallback_to_raw": false,
  "truncated": false,
  "consent_stripped": false,
  "garbage_type": null,
  "fastpath_hit": false,
  "fastpath_miss_reason": "wrong_content_type",
  "content_path": "scrape_content/2026-05-23T22-30-01.234Z_example-com-article.md"
}
```

**Field semantics:**

| Field | Values / Notes |
|-------|---------------|
| `mode` | `"filtered"` (scrape_url) \| `"raw"` (scrape_url_raw) |
| `outcome` | `"ok"` \| `"garbage"` \| `"empty"` \| `"timeout"` \| `"error"` |
| `phase_used` | `"fastpath"` \| `"browser_1a"` \| `"browser_1b"` \| `"browser_2_stealth"` \| null on failure |
| `phases_attempted` | ordered list of phases that ran |
| `timings_ms.filter` | always null — PruningContentFilter runs inside Crawl4AI `arun`, not separable |
| `http_status` | from phase that produced final content; null on failure |
| `content_type` | Content-Type header from winning phase; null if N/A |
| `bytes_returned` | byte length of final content (after truncation); null on failure |
| `bytes_raw_markdown` | raw_markdown length before filter/fallback; for raw mode = `bytes_returned`; for fastpath = `bytes_returned` |
| `fallback_to_raw` | true iff `fit_markdown < 200` triggered fallback to `raw_markdown`; null for raw mode |
| `truncated` | true iff 15K cap applied; null for raw mode |
| `consent_stripped` | true iff `strip_consent_prefix()` changed content; null for raw mode |
| `garbage_type` | 7 values from `is_garbage_content()` or null; always null for raw mode |
| `fastpath_hit` | true iff fastpath returned content |
| `fastpath_miss_reason` | `"http_error"` \| `"wrong_content_type"` \| `"sub_threshold"` \| `"network_error"` \| null (on hit) |
| `content_path` | relative path under log dir, e.g. `"scrape_content/<file>.md"`; null when no content |

**Sidecar file format:**
```markdown
<!-- url: https://example.com/article -->
<!-- ts: 2026-05-23T22:30:01.234Z -->
<!-- outcome: ok -->
<!-- bytes: 5104 -->
<!-- mode: filtered -->

<actual final markdown content exactly as the agent received it>
```

**URL slug derivation** (deterministic, no randomness): strip `https://` or `http://` → replace non-alphanumeric with `-` → collapse runs → strip leading/trailing `-` → cap at 80 chars.

**ts sanitization for filenames:** replace `:` with `-` (so `2026-05-23T22:30:01.234Z` → `2026-05-23T22-30-01.234Z`).

## Evidenz

Design session 2026-05-23. No dev/ probe — this is a logging-emission feature with no empirical tradeoffs to measure. The sidecar split (structured analytics vs. raw content) mirrors the pattern used in `src/search/query_logger.py` (structured JSONL only, no content). Goal: build a data basis over weeks/months to (a) find scraping problems systematically and (b) enable future benchmarks of current Crawl4AI+PruningContentFilter vs. alternatives (Trafilatura, Mozilla Readability) without re-scraping.

## Recommendation (SOLL)

Keep — architecture is the IST.

## Offene Fragen

- **Rotation policy:** The per-scrape content sidecar directory grows unboundedly (gitignored, not committed). No rotation or cleanup logic exists. To be addressed if storage becomes uncomfortable (> N GB). Options: TTL-based cleanup script, size cap with LRU eviction, move old sidecars to cold storage.
- **Schema versioning:** no version field in the record schema. If future analysis surfaces fields to add/rename, existing records won't have the new fields. Options: add `"schema_v": 1` to all records, or handle missing fields in analysis scripts. Unresolved.
- **Raw mode garbage outcome:** `try_scrape_raw` returns `""` for garbage content (garbage → next phase tried), so garbage can never be an explicit `outcome` in raw mode — it manifests as `"empty"` if all phases fail. If distinguishing garbage-as-empty is needed for raw mode, `try_scrape_raw` would need a garbage sentinel (analog to `CLOUDFLARE_SENTINEL`).

## Quellen

None — internal design decision, no external sources.
