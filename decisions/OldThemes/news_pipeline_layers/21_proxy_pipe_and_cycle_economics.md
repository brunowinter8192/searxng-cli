# Iteration 21 — Proxy Pipe + Cycle Economics

**Date:** 2026-06-11
**State:** Economics + knowns crystallized from the liveness-sweep session (OldThemes 19+20). Pipe build = next.

## What We Concretely Know (measured this session)

| Quantity | Value | Source |
|---|---|---|
| Raw pool (this run) | ~118k unique host:port / ~320k protocol-tagged | OldThemes 19 |
| Neutral-alive rate @ optimal concurrency | **9.2%** (919/10k @ conc 128) | `sweep_log.md` baseline 2026-06-11T21:15Z |
| Optimal check concurrency | **~128** (router-limited) | OldThemes 20 downward sweep |
| alive/s @ 128 | ~1.0/s (10k → 919 in 878.8s) | baseline |
| Pool churn | start-512 = end-512 (51 = 51 over 30 min) → stable over the window | OldThemes 20 bookend |
| Dead taxonomy @ 128 | 60% hard_timeout, 23.3% proxy_handshake (mislabels), 13% refused | baseline histogram |

## What We DON'T Know (the gates)

- **CF-pass rate on the CURRENT pool** — the 18.8% is from OldThemes 17 (older, different pool). Must re-measure.
- **Per-IP budget B** — fetches a CF-passing proxy completes before CF mechanism-2 (403/429) trips. The single number gating backfill feasibility. Hint 1–21, unmeasured.

## Router = Master Constraint

The proxy check saturates the home router's NAT/conntrack (10k connections to 10k mostly-dead proxies). Concurrency above ~128 → router drops live-proxy connections → false `hard_timeout` → alive-rate collapses. Identical 20k sample: 3.9% @ 512 → 0.3% @ 3000; identical 3k sample inverted: 1.7% @ 512 → 9.3% @ 64. Churn ruled out by the 51=51 bookend (alive rises with *descending* concurrency despite *later* time — churn would lower later runs). Throughput scales linearly (44→238/s) but accuracy collapses: the router caps the whole operation's connection throughput.

## Cycle Economics (sketch)

Per cycle: 10k batch → ~919 neutral-alive (9.2%, ~14.6 min) → ×CF-rate → CF-passing. At the old 18.8%: ~173 CF-passing, ~17 min total gen.

Backfill = 27k pages, `cycles = 27,000 / (CF_per_cycle × B)`:

| B (per-IP budget) | pages/cycle | cycles | ~total (×~20 min/cycle) |
|---|---|---|---|
| 21 (optimistic) | 3,633 | ~7 | **~2.5 h** |
| 10 | 1,730 | ~16 | ~5 h |
| 5 | 865 | ~31 | ~10 h |
| 2 (pessimistic) | 346 | ~78 | **~26 h** |

## Key Structural Findings

1. **Within a cycle, proxies survive.** Scrape ≈ 30 s/cycle (173 proxies × ~21 req in parallel) vs ~1 h proxy lifetime. Lifetime is NOT the cycle constraint; the "stale before done" problem applies to the 320k full-pool check, not to one cycle.
2. **Backfill is proxy-GENERATION-bound, not scrape-bound** — ~17 min gen : ~30 s scrape ≈ 17:1. Speed levers = hit-rate (source curation: drop the ~23% protocol-mislabel junk, esp. MuRongPIG) + B. NOT scrape optimization.
3. **Parallelizing gen + scrape saves only ~3%** (scrape is tiny vs gen) and both contend on the router. Worth it as architecture (continuous producer/consumer, resume-safe, peak-freshness) and for short jobs (discovery), NOT as a backfill speed lever.

## Recommendation (SOLL)

Build the pipe in `dev/` (neutral-check → CF-check → fetch), 5k batches, funnel-logged (neutral-alive + CF-pass + per-IP-budget per run). Run on The Block sitemap FIRST — this completes the open discovery (OldThemes 14, ~43 missing sub-sitemaps) AND gathers the current CF-rate + B organically from the real fetch. Source curation (per-source alive-rate ranking) is the parallel generation-speed lever.

## Quellen

Internal: OldThemes 14–20 (theblock discovery + proxy method + liveness sweep), `dev/news_pipeline/theblock/probe_liveness_logs/sweep_log.md`.
