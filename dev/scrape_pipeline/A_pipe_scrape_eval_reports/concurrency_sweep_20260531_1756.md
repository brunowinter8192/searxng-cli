# Phase 1 — Concurrency Sweep (WAF Detection)

Input: 06_discovered_urls.txt (30 stratified URLs)  
Fixed: `delay=1.0s`, `page_timeout=15000ms`, `wait_until=domcontentloaded`

| Concurrency | Success | Empty | HTTPErr | 429s | p50_ms | p95_ms | max_ms | Wall_s | WAF-Safe |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 30/30 | 0 | 0 | 0 | 2193 | 2515 | 2749 | 66s | ✓ |
| 3 | 30/30 | 0 | 0 | 0 | 1412 | 1773 | 2028 | 15s | ✓ |
| 5 | 30/30 | 0 | 0 | 0 | 1640 | 2010 | 2298 | 10s | ✓ |
| 10 | 9/30 | 1 | 0 | 20 | 2081 | 2471 | 2471 | 5s | ✗ |

## Conclusion

**WAF-safe concurrency: 5** — highest level with 0×429

→ Use `concurrency=5` for Phase 2 (delay sweep) and Phase 3 (full run).

## Phase 2 + 3 Plan (Successor)

Phase 2 — Delay sweep on 30 stratified URLs at `concurrency=5`:  
  Sweep `delay_s` ∈ {0.5, 1.0, 2.0, 3.0}. Metric: bytes_p50 as completeness proxy.

Phase 3 — Full run on all URLs at best (concurrency, delay):  
  Save raw markdown to `A_pipe_scrape_eval_reports/full_run_<ts>/`.  
  Report: p50/p95/max latency, success/empty/timeout rates, total wallclock.

Then write `decisions/pipe_scraper.md` (NEW file, separate from scrape_pipeline.md).