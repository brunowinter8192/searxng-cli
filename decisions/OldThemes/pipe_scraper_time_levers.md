# Pipe-Scraper Time Levers — Pacing Overhead & WAF-Rate Tuning

**Topic:** pacing overhead, WAF budget, and the evolution from ad-hoc batch/sleep to Scrapy-style per-domain gate.

---

## Phase 1 — Batch/Sleep Config (superseded)

**Status:** shipped as conservative default. Superseded by Scrapy-style gate.

### Config (batch/sleep — superseded values)

| Knob | Value | Meaning |
|---|---|---|
| `CONCURRENCY` | 5 | global semaphore — WAF burst ceiling (c=10 → 20×429, proven Phase 1) |
| `delay_before_return_html` | 0.5s | per-page render wait after `domcontentloaded` |
| `page_timeout` | 15000ms | hard per-page cap (max observed 6.2s — never fired) |
| `BATCH_SIZE` | 30 | URLs per batch before a pause |
| `INTER_BATCH_SLEEP_S` | 30.0s | pause between batches (WAF budget recovery) |

### Time breakdown (316 URLs → 438s wallclock)

- 316 / 30 = 11 batches.
- One batch of 30 @ c=5 ≈ 10s scrape (Phase 1: c=5 on 30 URLs = 10s).
- 10 inter-batch pauses × 30s = 300s.
- **Total ≈ 110s scrape + 300s pauses + overhead = 438s. Pauses = ~68% of runtime.**

The scraping itself is fast; the pacing dominates. Effective sustained rate ≈ 0.75 req/s.

### WAF characterization (Phases 1+2 sweep results)

WAF = rate/burst budget over time, NOT a pure concurrency cap:
- One 30-URL burst at c=5 in ~8s (3.75 req/s) exhausts the budget
- Budget recovery requires minutes, not seconds (8s intra-sweep gap: insufficient)
- c=10 → 20×429, c=5 = WAF-safe ceiling
- ~1 req/s sustained = fully safe

### Levers + WAF risks (batch/sleep model)

| Lever | Effect | Risk | Finding |
|---|---|---|---|
| ↓ inter_batch_sleep | biggest win (~300s) | 8s gap proved a ban; below threshold = 429 mid-run | unknown minimum |
| ↑ batch_size | fewer pauses | batch = burst; 30 URLs in 8s already exhausts budget | unknown max |
| ↑ concurrency (5→more) | faster bursts | c=10 → 20×429 | OFF THE TABLE |
| ↓ delay (0.5→0) | ~32s | SSR: likely safe; CSR: may miss content | small + site-dependent |

### Why batch/sleep is an ad-hoc approximation

The batch-stop-and-go achieves ~1 req/s sustained, but via burst+pause rather than evenly spaced starts. The 30s inter-batch pause is a guessed recovery time, not derived from a rate model. The Scrapy gate replaces this with a principled reference that achieves the same effective rate with no dead pauses.

---

## Phase 2 — Scrapy-Style Gate (current production)

**Status:** shipped, validated on 316 URLs.

### Approach choice

Two candidates were evaluated:

**(A) Own per-domain logic** — `lastseen` dict + per-domain `asyncio.Lock` + per-domain `asyncio.Semaphore(8)`. Exact Scrapy semantics, fully deterministic.

**(B) crawl4ai `RateLimiter` + `MemoryAdaptiveDispatcher`** — less code, but `RateLimiter` applies ×0.75 delay reduction on each success. Adaptive path → violates the "no adaptive delay reduction, determinism over everything" constraint. Rejected.

**Chosen: A.** Determinism constraint is hard — no adaptive reduce anywhere.

### Gate mechanics

Per domain (key = `urlparse(url).netloc`), state = `{lastseen: float, lock: asyncio.Lock, sem: asyncio.Semaphore(8)}`.

`_gate_domain(state, download_delay)`:
1. Acquire domain `lock`
2. Compute `jitter = random.uniform(0.5 × download_delay, 1.5 × download_delay)`
3. `gap = now - lastseen`; if `gap < jitter`: sleep remainder
4. Stamp `lastseen = time.time()` (at request START, not completion — exact Scrapy semantics)
5. Release lock

Sleep-inside-lock is intentional: it serializes starts per domain. Event loop handles other domains freely during the sleep.

`_scrape_one` flow: `sem.acquire` → `_gate_domain` → `crawler.arun()` (outside lock, inside sem slot).

### Config (current production)

| Knob | Value | Meaning |
|---|---|---|
| `DOWNLOAD_DELAY` | 1.0s | Scrapy base; actual jitter = uniform(0.5×, 1.5×) → 0.5–1.5s |
| `CONCURRENCY_PER_DOMAIN` | 8 | in-flight cap per domain (dormant: at ~1s gate + 1.8s p50, ~2 in flight) |
| retry / backoff / autothrottle | OFF | determinism constraint |

Effective start rate: ~1 req/s per domain — same as old batch config, but evenly spaced.

### Validation result

316 `docs.github.com/de/rest` URLs, `--download-delay 1.0 --concurrency-per-domain 8`:

| Metric | Batch/Sleep | Scrapy Gate | Delta |
|---|---|---|---|
| ok | 316/316 | 316/316 | — |
| WAF 429 | 0 | 0 | — |
| Wallclock | 438s | 319s | −119s (−27%) |

No dead 30s pauses → 27% faster at identical WAF safety.

---

## Quellen

- `decisions/pipe_scraper.md` — current IST/Evidenz/SOLL
- `dev/scrape_pipeline/p1_pipe_scraper.py` — probe (batch/sleep knobs)
- `dev/scrape_pipeline/A_pipe_scrape_eval.py` — Phase 1/2/3 sweep harness
- `dev/scrape_pipeline/A_pipe_scrape_eval_reports/` — Phase 1/2/3 reports (concurrency_sweep, delay_sweep, full_run)
- Scrapy source: `scrapy/core/downloader/__init__.py` — per-domain slot, delay gate, `RANDOMIZE_DOWNLOAD_DELAY`, `CONCURRENT_REQUESTS_PER_DOMAIN`
