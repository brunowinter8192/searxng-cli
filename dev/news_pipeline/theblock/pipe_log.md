---
## 2026-06-11T21:57:12Z | batch=5,000 | conc_liveness=128 | conc_cf=20

| Stage | Count | Rate | Wall-clock |
|---|---|---|---|
| Raw batch (fresh 68-source sample) | 5,000 | — | — |
| Stage 1 neutral-alive | 488 | 9.8% of raw | 442s |
| Stage 2 CF-passing | 4 | 0.8% of neutral / 0.1% of raw | 16s |
| Stage 3 subs fetched this run | 36 | — | 247s |
| Stage 3 cache progress | 36/64 | — | — |

### Per-IP Budget B

Exhausted proxies: n=3  min=4  max=20  mean=9.3

| B (fetches before 403/429) | Count |
|---|---|
| 4 | 2 |
| 20 | 1 |

Active proxies still alive at end: n=1  lower-bound B: min=8  max=8

---
## 2026-06-11T22:34:26Z | batch=5,000 | conc_liveness=128 | conc_cf=20

| Stage | Count | Rate | Wall-clock |
|---|---|---|---|
| Raw batch (fresh 68-source sample) | 5,000 | — | — |
| Stage 1 neutral-alive | 475 | 9.5% of raw | 442s |
| Stage 2 CF-passing | 4 | 0.8% of neutral / 0.1% of raw | 16s |
| Stage 3 subs fetched this run | 3 | — | 330s |
| Stage 3 cache progress | 39/64 | — | — |

### Per-IP Budget B

Exhausted proxies: n=3  min=0  max=3  mean=1.0

| B (fetches before 403/429) | Count |
|---|---|
| 0 | 2 |
| 3 | 1 |

Active proxies still alive at end: n=1  lower-bound B: min=0  max=0

