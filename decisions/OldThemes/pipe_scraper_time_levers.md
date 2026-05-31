# Pipe-Scraper Time Levers — Pacing Overhead & WAF-Rate Tuning

**Topic:** the validated pipe-scraper config (`decisions/pipe_scraper.md` SOLL) is deliberately conservative on speed. ~70% of the runtime is WAF-budget pacing, not scraping. This file documents the time breakdown, the speed levers, their WAF risks, and the eval needed to tune them.

**Status:** SOLL shipped as conservative default (Phase 3: 316/316, 0×429, 438s). Time-tuning is a follow-up — NOT yet evaluated.

## Current config (time knobs)

| Knob | Value | Meaning |
|---|---|---|
| concurrency | 5 | pages in parallel — WAF burst ceiling (c=10 → 20×429, proven Phase 1) |
| delay_before_return_html | 0.5s | per-page render wait after `domcontentloaded` |
| page_timeout | 15000ms | hard per-page cap (max observed 6.2s — never fired) |
| batch_size | 30 | URLs per batch before a pause |
| inter_batch_sleep | 30s | pause between batches (WAF budget recovery) |

## Time breakdown (316 URLs → 438s wallclock)

- 316 / 30 = 11 batches.
- One batch of 30 @ c=5 ≈ 10s scrape (Phase 1: c=5 on 30 URLs = 10s).
- 10 inter-batch pauses × 30s = 300s.
- **Total ≈ 110s scrape + 300s pauses + overhead = 438s. Pauses = ~68% of runtime.**

The scraping itself is fast; the pacing dominates.

## Levers + WAF risks

| Lever | Effect | Risk | Status |
|---|---|---|---|
| ↓ inter_batch_sleep (30s → less) | biggest win (~300s) | WAF needs minutes to recover budget; Phase 2 proved an 8s gap → ban. Below threshold = 429 mid-run → incomplete capture | unknown minimum — needs eval |
| ↑ batch_size (30 → more) | fewer pauses | batch = the burst; ~30 URLs in 8s already exhausts the budget. Bigger → 429 mid-batch | unknown max burst — needs eval |
| ↑ concurrency (5 → more) | faster bursts | c=10 proven 20×429 | OFF THE TABLE — capped at 5 |
| ↓ delay (0.5 → 0) | ~32s (316×0.5/5) | SSR: content in initial HTML → likely safe; CSR/lazy-loaded: miss content → incomplete | small + site-dependent |

## WAF characterization (from `decisions/pipe_scraper.md` Evidenz)

WAF = rate/burst budget over time, NOT a concurrency cap. ~30 URLs in 8s (3.75 req/s) exhausts the burst budget; recovery takes minutes, not seconds. Current config ≈ 0.75 req/s sustained (30 URLs / ~40s) — safe with margin. Unknowns: the actual minimum-safe-pause and max-safe-burst.

## Needed eval (to tune)

WAF-rate sweep on the 316 GH URLs (or a fresh discovery set):

- `inter_batch_sleep` ∈ {30, 20, 15, 10}s at batch=30 → where do 429s appear?
- `batch_size` ∈ {30, 45, 60} at sleep=30s → where does the burst break?
- Optional: a bounded-retry strategy (retry 429'd URLs after cooldown) to recover completeness if pushed past the safe edge.
- `delay` ∈ {0, 0.5} byte-completeness comparison on a clean (non-WAF-contaminated) sample — Phase 2's delay sweep was contaminated, so the delay→completeness relationship is still unmeasured.

Output: a less-conservative config that keeps completeness while cutting pacing overhead, OR confirmation that 30 / 30s is near-optimal. The production `pipe_scraper.py` exposes `--batch-size` and `--inter-batch-sleep` flags specifically so this sweep needs no code change.

## Trade-off framing

Speed vs WAF-safety/completeness. Project priority: completeness + determinism > speed → the conservative default ships now. The tuning eval narrows the pacing only as far as the WAF tolerates, holding 0×429.

## Quellen

- `decisions/pipe_scraper.md` — IST/Evidenz/SOLL (validated config + WAF characterization)
- `dev/scrape_pipeline/p1_pipe_scraper.py` — scraper probe (the knobs)
- `dev/scrape_pipeline/A_pipe_scrape_eval.py` — batching/pacing harness (phase3) — sweep-ready
- `dev/scrape_pipeline/A_pipe_scrape_eval_reports/` — Phase 1/2/3 reports (concurrency_sweep, delay_sweep, full_run)
- `src/crawler/pipe_scraper.py` — production module (exposes batch/pacing as CLI flags for the sweep)
