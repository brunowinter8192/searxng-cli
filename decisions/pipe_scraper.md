# decisions/pipe_scraper.md — Pipe-Scraper Configuration

Covers `src/crawler/pipe_scraper.py` — the production capture-pipeline scrape step.  
Separate from `decisions/scrape_pipeline.md` (filter/garbage/browser config for the ad-hoc CLI scraper).

**Note:** `crawl_urls()` in `src/crawler/crawl_site.py` is out of scope here — it serves the BFS-discovery workflow (`crawl_site_workflow`) and is unchanged.

## Status Quo (IST)

`scrape_urls_workflow()` in `src/crawler/pipe_scraper.py`:

| Parameter | Value |
|---|---|
| `wait_until` | `"domcontentloaded"` |
| `delay_before_return_html` | `0.5s` (`DELAY_S`) |
| `page_timeout` | `15000ms` (`PAGE_TIMEOUT_MS`) |
| `concurrency` | `5` (`CONCURRENCY`) |
| markdown | `DefaultMarkdownGenerator()` raw (no `PruningContentFilter`) |
| garbage-drop | none — saves every page (content completeness is scraper's job) |
| `batch_size` | `30` (`BATCH_SIZE`) |
| `inter_batch_sleep_s` | `30.0s` (`INTER_BATCH_SLEEP_S`) |

Output contract:
- Per-URL raw markdown → `--output-dir`, each file with `<!-- source: URL -->` header
- Short console line: `Scraped N/M ok, K errors in Xs`
- Full per-URL report → `/tmp/<domain>_scrape_report.md` (outcome / status / bytes / wall_ms per URL)
- Runnable as `python -m src.crawler.pipe_scraper --url-file <list> --output-dir <dir>`
- CLI flags `--batch-size` / `--inter-batch-sleep` allow WAF-rate tuning without code changes

`scrape_urls_workflow()` also importable — capture-and-index skill Phase 2 calls it directly.

## Evidenz

All measurements on `06_discovered_urls.txt` (316 `docs.github.com/de/rest` URLs).  
Scraper probe module: `dev/scrape_pipeline/p1_pipe_scraper.py` — `scrape_urls()` with `wait_until=domcontentloaded`, raw `DefaultMarkdownGenerator`, no filter, no garbage-drop, configurable knobs.

### Phase 1 — Concurrency Sweep (WAF Detection)

Script: `dev/scrape_pipeline/A_pipe_scrape_eval.py phase1`  
Report: `dev/scrape_pipeline/A_pipe_scrape_eval_reports/concurrency_sweep_20260531_1756.md`  
Dataset: 30 stratified URLs, fixed `delay=1.0s`, `page_timeout=15000ms`

| Concurrency | Success | Empty | 429s | p50_ms | p95_ms | Wall_s | WAF-Safe |
|---|---|---|---|---|---|---|---|
| 1 | 30/30 | 0 | 0 | 2193 | 2515 | 66s | ✓ |
| 3 | 30/30 | 0 | 0 | 1412 | 1773 | 15s | ✓ |
| 5 | 30/30 | 0 | 0 | 1640 | 2010 | 10s | ✓ |
| 10 | 9/30 | 1 | 20 | 2081 | 2471 | 5s | ✗ |

**Finding:** WAF hard boundary at c=10 (20×429, only 9/30 succeed). c=5 = WAF-safe ceiling (0×429, p50=1640ms).

### Phase 2 — Delay Sweep (Completeness Proxy)

Script: `dev/scrape_pipeline/A_pipe_scrape_eval.py phase2`  
Report: `dev/scrape_pipeline/A_pipe_scrape_eval_reports/delay_sweep_20260531_1804.md`  
Dataset: 30 stratified URLs, fixed `concurrency=5`, `page_timeout=15000ms`

| delay_s | Success | 429s | bytes_p50 | Valid? |
|---|---|---|---|---|
| 0.5 | 30/30 | 0 | 20,232 | ✓ |
| 1.0 | 5/30 | 25 | — | ✗ WAF ban |
| 2.0 | 0/30 | 30 | — | ✗ WAF ban |
| 3.0 | 0/30 | 30 | — | ✗ WAF ban |

Rounds 2–4 are WAF-contaminated: the delay=0.5 burst exhausted the rate budget; subsequent rounds fired without recovery time. Only delay=0.5 is a valid content measurement.

**Finding:** bytes_p50=20KB at delay=0.5 is full content — GH Docs is Next.js SSR; content is present in the initial DOMContentLoaded response. Additional delay adds nothing.

**WAF characterization (central finding from Phase 1+2):**

The WAF is NOT a pure concurrency cap. It is a rate/burst budget over time with a likely repeat-access heuristic:
- One 30-URL burst at c=5 in ~8s (3.75 req/s) exhausts the budget
- Budget recovery requires minutes, not seconds (8s intra-sweep gap: insufficient; inter-phase gap of several minutes: sufficient)
- Repeated scraping of the same URL set amplifies the signal (same 30 URLs hit 4× in 50s raised suspicion)
- c=5 is safe as a one-shot burst ceiling — NOT as an uncapped sustained rate

### Phase 3 — Full Run (316 URLs, Batched+Paced)

Script: `dev/scrape_pipeline/A_pipe_scrape_eval.py phase3 --delay 0.5`  
Report: `dev/scrape_pipeline/A_pipe_scrape_eval_reports/full_run_20260531_1813.md`  
Dataset: all 316 URLs, `concurrency=5`, `delay_s=0.5`, `batch_size=30`, `inter_batch_sleep=30s`

| Metric | Value |
|---|---|
| Success (ok) | 316/316 |
| Empty | 0 |
| WAF 429 | 0 |
| 429-onset | N/A |
| Wallclock | 438s |
| lat_p50 | 1793ms |
| lat_p95 | 3104ms |
| lat_max | 6217ms |
| lat_std | 776ms |
| bytes_p50 | 29,110 |
| bytes_p95 | 139,285 |

**Finding:** 100% capture, 0 empty, 0 WAF hits at full scale. Batched pacing (30 URLs + 30s pause → ~1 req/s sustained) completely neutralizes WAF. lat_max=6.2s << 15s timeout; lat_std=776ms = deterministic.

## Recommendation (SOLL)

**Keep** — IST = SOLL. `src/crawler/pipe_scraper.py` implements both tiers as validated.

- Tier 1 (generalized core): `domcontentloaded`, `delay=0.5s`, `timeout=15000ms`, `c=5`, raw markdown, no garbage-drop — all in production.
- Tier 2 (pacing): `batch_size=30`, `inter_batch_sleep=30s` as module constants + overridable CLI flags — in production.
- `crawl_urls()` in `crawl_site.py` is out of scope (serves BFS workflow, not the capture pipe).

**src/ port is a separate later task.** Do NOT modify src/ from this decision record.

## Offene Fragen

- Is `delay_s=0.5` sufficient for client-side-rendered (CSR) sites? Proven for Next.js SSR; heavy CSR may need more.
- What pacing parameters are appropriate for other target hosts (SearXNG result sites vary in WAF aggressiveness)?

## Quellen

Internal eval only — no external sources.
