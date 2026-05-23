# scrape06 — Per-URL Download Logging

## Status Quo (IST)

**Architecture:** Structured JSONL log only — no sidecar files. Every `download_pdf_workflow` call emits one record to `src/logs/download_log.jsonl`. The PDF itself is the artifact; its path is recorded in `output_path`.

**Log path:** `SEARXNG_DOWNLOAD_LOG_PATH` env var → fallback `src/logs/download_log.jsonl`. Gitignored. Fail-soft: write errors are logged as WARNING, download result still reaches caller.

**Implementation:** `src/scraper/download_logger.py` — `log_download(record: dict)`. Called at every return path of `download_pdf_workflow` via the `_emit(outcome, **kwargs)` inner helper.

**Why no sidecar:** The downloaded PDF is already on disk at `output_path`. Duplicating it as a sidecar would double disk usage for no analytical gain. The `content_path` concept from `scrape_logger` does not apply here.

**JSONL record schema:**
```json
{
  "ts": "2026-05-23T22:30:01.234Z",
  "url": "https://arxiv.org/abs/2310.01526",
  "domain": "arxiv.org",
  "output_dir": "/Users/brunowinter2000/Downloads",
  "output_path": "/Users/brunowinter2000/Downloads/2310.01526.pdf",
  "outcome": "ok",
  "chain_resolution": "tier1",
  "chain_attempted": ["blacklist_check", "github_blob_check", "tier1_transform", "download"],
  "final_pdf_url": "https://arxiv.org/pdf/2310.01526",
  "http_status": 200,
  "content_type": "application/pdf",
  "bytes_downloaded": 1245678,
  "timings_ms": {
    "blacklist_check": 0,
    "github_blob_check": 0,
    "tier1_transform": 1,
    "direct_pdf_check": null,
    "citation_pdf_url_hop1": null,
    "download": 2341,
    "total_wall": 2343
  },
  "error_message": null
}
```

**Field semantics:**

| Field | Values / Notes |
|-------|---------------|
| `outcome` | `"ok"` \| `"blacklisted"` \| `"github_blob"` \| `"no_pdf_path"` \| `"http_error"` \| `"network_error"` \| `"io_error"` |
| `chain_resolution` | `"tier1"` \| `"direct"` \| `"multi_step"` \| null on failure-before-resolution |
| `chain_attempted` | ordered stage names that ran. Stage names: `blacklist_check`, `github_blob_check`, `tier1_transform`, `direct_pdf_check`, `citation_pdf_url_hop1`, `download` |
| `final_pdf_url` | URL actually downloaded (or attempted); null if resolution failed |
| `http_status` | from download response; null if download didn't happen |
| `content_type` | Content-Type header from download; null if download didn't happen |
| `bytes_downloaded` | file size of saved PDF in bytes; null on failure |
| `timings_ms.citation_pdf_url_hop1` | time for `extract_citation_pdf_url()` HTML GET (Hop 1). null unless chain went multi_step |
| `timings_ms.download` | streaming download wall time. null if download stage never ran |
| `timings_ms.total_wall` | always set |
| `error_message` | short typed category: `"HTTPError 403"`, `"ConnectionError"`, `"PermissionError"`, `"non_pdf_response"`, etc. Null on success. NOT full traceback. |

**Chain-stage taxonomy:**
- `blacklist_check` — always first; instant lookup in `HARD_BLACKLIST`
- `github_blob_check` — runs unless blacklisted; regex match on URL path
- `tier1_transform` — runs unless blacklisted/github_blob; `apply_tier1_transform()` returns URL or None
- `direct_pdf_check` — runs if tier1 returned None; `path.endswith(".pdf")` string check
- `citation_pdf_url_hop1` — runs if direct=False AND not TIER1 domain; `extract_citation_pdf_url()` HTTP GET
- `download` — runs if any resolution stage produced a URL; `requests.get(..., stream=True)`

**Note on `citation_pdf_url_hop2`:** omitted from schema. In the current code the "second hop" (downloading the extracted citation PDF URL) IS the `download` stage — there is no separate step. If a future refactor separates the hops, the field can be added to the schema then.

## Evidenz

Design session 2026-05-23. No dev/ probe needed — logging-emission feature with no empirical tradeoffs. Goal: build data basis over weeks to (a) identify systematic download failure patterns (blacklist too broad, citation_pdf_url miss rate, HTTP error distribution), (b) measure chain effectiveness (tier1 vs direct vs multi_step success rates).

## Recommendation (SOLL)

Keep — architecture is the IST.

## Offene Fragen

- **`error_message` granularity:** currently captures exception class name or a short typed category string. If analysis surfaces a need for finer granularity (e.g. HTTP status distribution, DNS vs timeout breakdown for `network_error`), dedicated fields can be added. Full exception tracebacks explicitly excluded — `logger.exception()` handles those.
- **Log rotation:** `src/logs/download_log.jsonl` grows unboundedly. No rotation logic. Same policy as `scrape_log.jsonl` — address when file size becomes uncomfortable.

## Quellen

None — internal design decision.
