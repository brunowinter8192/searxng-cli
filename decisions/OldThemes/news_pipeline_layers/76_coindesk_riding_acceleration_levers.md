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

## Empirical: first instrumented run (120 slots, 8 browsers, job 20260624T204129Z)

868 target, 777 OK, **24,238 connect-fails**, fixed cooldown, SIGINT-interrupted. Findings:

- **Concurrency is NOT the throughput lever.** 120 slots → 16.6 OK/min vs the earlier 80-slot ~18.4 OK/min — 120 is *slightly worse*. The live-proxy set is a fixed scarce subset of the pool; more contexts pull+burn it faster, they do not create more live proxies. Raising contexts just front-loads then starves. Supply-via-concurrency refuted.
- **Pool exhaustion is the cooldown ceiling, not a bug.** "Eligible pool over time": min-eligible 17.6k → 0 over 50 min, in-cooldown → 24k. At 120 slots with ~1-attempt rides + 60-min `fixed` cooldown, burn-rate drains the eligible pool faster than cooldowns expire → slots exit ("pool exhausted"). 120 is unsustainable under fixed-60min. → `exp` cooldown (re-admits productive proxies) is the supply-side lever, same as OT74.
- **Pool loaded = 20,831 is browser-eligible only.** `_pool_provider` filters to `BROWSER_ELIGIBLE_PROTOS = {http, socks5}`; the ~32.7k full pool includes ~12k socks4 that Chromium/Playwright cannot use. Not a bug — the riding engine runs on ~64% of the pool. (socks4 usable only by curl_cffi / TheBlock.)
- **CPU at limit at 120** (user-observed) — consistent with CPU-bound post-nav processing (markdown gen), see below. Going down from 120, not up.

## Instrumentation evolution (this session)

Built incrementally on the riding reporter (`src/news/engine/proxy_riding/reporter.py` + `rider.py`):
1. **Success load-time distribution** — `load_s = max(0, elapsed − DELAY_BEFORE_HTML)`, OK-only; inclusive-quantile percentiles + histogram. **Caveat discovered:** `load_s` is NOT navigation time — it lumps nav (#4, the only phase `page_timeout` bounds) with markdown generation (#7, CPU-bound) + context setup. p50=8.7s / p99=14.6s on the 120 run while `page_timeout`=8s proves a large non-nav component. So `load_s` cannot cleanly tune `page_timeout`.
2. **Histogram auto-range fix** — x-axis was hard-clipped to `[0, page_timeout_s]`, hiding the >8s bulk; now auto-ranges to data with a `page_timeout` reference line.
3. **Connect-fail breakdown** — `connect_fail`s previously discarded their timing (`break` before `job_records.append`). Now collected as `(elapsed_s, subtype)` in `state.connect_fail_records`; reporter emits elapsed-percentiles + histogram + subtype counts. Classifier `_classify_connect_fail`: `"ms exceeded"` → `page_timeout` (Playwright nav cap; crawl4ai wraps as RuntimeError), `"net::err_timed_out"` → `net_timed_out` (TCP), `err_proxy|err_tunnel|socks` → `proxy_connect`, else `other`. Discriminator note: `"timeout"` alone is ambiguous (both nav-cap and TCP contain it) — `"ms exceeded"` is the unique Playwright-nav-cap signature.

**Why connect-fail breakdown matters for the timeout question:** live proxies that get cut at the 8s cap are currently INVISIBLE — a nav-timeout errors with "Timeout 8000ms exceeded" → classified `connect_fail`. The `page_timeout` subtype count is the addressable population for "lives cut at 8s" (a mix of dead-no-response + live-slow; the error string can't separate them — a timeout A/B disambiguates). The connect-fail elapsed histogram shows whether dead proxies hang to ~8s (→ lowering frees slots) or fail fast (→ lowering doesn't help cycling).

## Open

- **`page_timeout` raise-vs-lower** — pending an instrumented 1000-on-80 run: read the connect-fail breakdown (page_timeout subtype share + whether cf-elapsed piles at 8s) + success distribution. Big page_timeout bucket → lives may be cut → A/B a higher timeout; near-zero + dead proxies hanging to 8s → lower.
- **Cooldown policy** — `fixed` exhausts the pool at high concurrency; `exp` is the supply-side lever (separate from timeout). Pending its own run.
- **Navigation vs markdown split** — `load_s` conflates them; a clean `page_timeout` tune would need nav (#4) isolated from markdown (#7), which crawl4ai does not expose at the `arun` return (would require a two-phase dev probe).
