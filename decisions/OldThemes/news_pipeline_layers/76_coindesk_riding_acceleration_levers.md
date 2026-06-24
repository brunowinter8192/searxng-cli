# 76 — CoinDesk riding: acceleration levers + success-load-time instrumentation

Process record of the throughput analysis on the `proxy_riding` backfill engine and the instrumentation built to drive timeout/concurrency tuning. Backfill state at analysis time: 12,564 / 61,628 raw HTMLs (~20%); per-year remaining computed via `url_hash(url)=sha256[:12]` vs `data/news/coindesk/raw/*.html` (2025 + 2026 fully untouched).

## Diagnostic finding — the engine is I/O-bound

From job `20260620T163141Z` (442 OK, 5 browsers × 16 ctx = 80 slots, fixed cooldown):

| Signal | Value | Reading |
|---|---|---|
| OK | 442 | productive fetches |
| Connect-fail fetches | 9728 | ~96% of fetches hit dead proxies |
| Ride length | mean 1.1 | each proxy does ~1 attempt then burns |
| Mean s/fetch (OK+rw+failed) | 8.31s | dominated by `page_timeout=8000ms` |
| Wall | 1442s | |

Estimate: 9728 dead-proxy attempts × ~8s ≈ 78k slot-seconds vs 80×1442 ≈ 115k available → **~2/3 of slot-time spent waiting on dead proxies**. Slots block on `await crawler.arun` (network wait), not compute. This is why CPU sat ~43% and GPU idle during runs — idle compute is a *symptom* of I/O-bound, not spare acceleration headroom.

## Levers evaluated

| Lever | Verdict | Reason |
|---|---|---|
| Pre-flight proxy liveness check | **REJECTED** | The fetch at the target is the only valid liveness test. A separate pre-check is either as expensive as scraping or inaccurate (weaker test → discards good / keeps dead). No public scraper does this. |
| Lower `page_timeout` | **valid, data-gated** | Dominant cost per dead proxy. But where to set it = needs the SUCCESS load-time distribution (set just above p95/p99 so live-but-slow proxies aren't cut). Built instrumentation (below) before tuning. |
| More slots / browsers | **biggest immediate lever** | I/O-bound with idle compute → can pack many more concurrent waits before CPU saturates. Ceiling = RAM (Chromium ctx ~50–100MB each) + Playwright stability, NOT CPU. Scale 80 → 128 → measure. |
| GPU offload | **won't help** | No compute bottleneck to move. Rendering is the small fraction (~442 real page loads); time goes to network wait (~10k proxy attempts). Idle GPU = I/O-bound symptom. |
| Better/more proxy sources | **at free-proxy limit** | ~4% live is the free reality (~32.7k pool, 18 sources, 0 fail). Step-change = paid residential/datacenter proxies (~95% live, collapses the 9728 connect-fails) — a cost decision, not a code lever. |

## Instrumentation built (this session)

Goal: measure the SUCCESS load-time distribution — serves BOTH the timeout floor AND the concurrency-scaling test (does the distribution shift right at higher slot counts = local contention).

- `rider.py`: `JobRecord.load_s` — populated OK-only as `max(0, elapsed_s − DELAY_BEFORE_HTML)` (0.5s). crawl4ai's `CrawlResult` (models.py) exposes **no** navigation/domcontentloaded timing at the direct `arun()` return (timing submodels are dispatcher-layer; `dispatch_result` unreliable without the dispatcher) → fallback approximation. Residual ≈ constant context-setup overhead → curve shifts right by a near-constant → timeout reading slightly conservative (safe direction).
- `reporter.py`: job.md section "Success load-time distribution" — percentiles p50/p90/p95/p99/max (n) + `success_load_hist.png` histogram, x-axis fixed `[0, page_timeout_s]` for cross-run comparability, 0.25s bins. Guard: <2 OK samples → note, no plot, no crash (reporter also runs on stall/abort).
- **`statistics.quantiles` method = `inclusive`** (not the default `exclusive`): exclusive extrapolates beyond the sample (`k/(n+1)`) → on small n, p99 > observed max, misleading for "set timeout above observed tail". inclusive interpolates within `[min,max]`. On large n the two converge; the divergence only bites on small/stall runs.

## Experiment design (pending data)

Run the 10k backfill once at `--slots 80` and once at `--slots 120` (`--from 2025-01-01 --to 2026-12-31 --limit 10000`, both years untouched so limit-before-dedup yields 10k new). Compare the two `success_load_hist.png` + percentile tables:
- distribution unchanged → not locally bound → scale slots up freely.
- distribution shifts right → local contention ceiling found → throughput optimum below that.
Caveat: live-proxy set varies between runs; thousands of OK per run averages it out.

## Open

- Actual `page_timeout` value — pending the success-distribution from an instrumented run.
- Optimal `--slots` — pending the 80-vs-120 comparison.
