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

---

## Pipe Build + First Sitemap Run

**Date:** 2026-06-12  
**Script:** `dev/news_pipeline/theblock/pipe_theblock.py`  
**Run timestamp:** 2026-06-11T21:57:12Z  
**Log:** `dev/news_pipeline/theblock/pipe_log.md` (first entry)

### Funnel

| Stage | Count | Rate | Wall-clock |
|---|---|---|---|
| Raw batch (68-source fresh sample) | 5,000 | — | — |
| Stage 1 neutral-alive | 488 | 9.8% of raw | 442s |
| Stage 2 CF-passing | 4 | **0.8% of neutral** / 0.1% of raw | 16s |
| Stage 3 subs fetched this run | 36 | — | 247s |
| Stage 3 cache progress | 36/64 | — | — |

**Total elapsed: 705s (~11.8 min)**

### Stage 2 — CF-Pass Rate: 0.8% (vs old 18.8%)

OldThemes 17 measured 18.8% (80/425) on a smaller, older pool with `probe_curl_cffi_discriminator`. This run: **0.8% (4/488)** on a fresh 5k sample from the full 68-source pool. The collapse is real:
- Pool is now 24.9× larger (118k unique); dilution with low-quality IP ranges is substantial
- Time gap between OldThemes 17 run and this run — IP reputation may have shifted for the specific IPs in the older pool
- The 4 CF-passing proxies ARE genuine (they successfully fetched sub-sitemaps in Stage 3)

Absolute yield: 4 CF-passing proxies per 5k sample ≈ ~0.26 CF-passing per 1k raw. At 118k pool, estimated ~31 CF-passing total in the live pool (single check cycle).

### Stage 3 — Per-IP Budget B

Sequential exhaustion B-capture (one proxy drained until 403/429, then rotate):

| Proxy | B (fetches before block) | Block type |
|---|---|---|
| socks5h://103.18.77.4:1080 | 3 (index + 3 subs) | 403 |
| socks5h://134.122.1.61:11679 | **20** | 429 (rate-limit) |
| socks5h://170.64.170.204:1080 | 4 | 403 |
| socks5h://103.18.77.4:1080 | 4 | 403 |
| socks5h://206.123.156.233:6458 | ≥8 (still active at run end) | — |

Exhausted proxies (n=3): B values = 4, 4, 20 → min=4, max=20, mean=9.3  
Active proxy at end: lower-bound B=8

**B summary:** Two proxies hit CF block at B=4 (fast burn), one lasted B=20 (possibly better IP/session). Realistic working estimate: **B ≈ 4–10** for free-pool proxies. The cycle economics from §"Cycle Economics" used B=2–21 as range; the measured data falls in B=4–20.

**Discovery gaps:** 28 subs skipped (all-transient failures on last remaining proxy — types: `linked`, `daily`, `page`, `token`, `index`, `etf`, `stock`, `press-release`, `converter`, `rating`, `treasury`, `category taxonomies`, `authors`, `news`). These are lower-priority content types (non-`post_type_post`). The 23 `post_type_post` subs (the main article content) are all in the cached 36.

### Revised Cycle Economics

Updated with measured CF-rate (0.8%) and B data:

| B | CF-passing / 5k cycle | pages/cycle | cycles for 27k pages | ~total |
|---|---|---|---|---|
| 20 (optimistic) | 4 | 80 | 338 | **~66 h** |
| 9 (mean) | 4 | 36 | 750 | ~150 h |
| 4 (pessimistic) | 4 | 16 | 1,688 | **~328 h** |

The 0.8% CF-rate (vs assumed 18.8%) makes backfill via this approach prohibitively slow at 5k batch size. **Effective lever: increase sample size per cycle to 50k+ to extract more CF-passing proxies per run.** At 50k sample: expect ~40 CF-passing → ~360 pages/cycle at mean B=9 → ~75 cycles → ~15h total. Source curation (dropping low-yield sources) would also improve throughput.

### Structural Finding

The pipe architecture (Stage 1→2→3) is validated and working. The main variable is CF-pass rate per cycle, which scales with batch size. 5k batch is intentionally conservative (dev run); production runs should use larger samples.
