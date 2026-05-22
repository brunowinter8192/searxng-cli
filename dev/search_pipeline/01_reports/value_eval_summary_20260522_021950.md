# Value Eval Summary

**Pairs:** 16 / 16  
**Oracle:** present  
**Timestamp:** 20260522_021950  

## Per-Mode Mean Jaccard

| Mode | C1 Overlap-Count | C2 BM25 vanilla | C2' BM25-Capped | C3 Cross-Encoder | Winner |
|------|---|---|---|---|--------|
| general | 0.179 | 0.181 | 0.162 | 0.302 | **C3 Cross-Encoder** |
| pdf | 0.871 | 0.871 | 0.871 | 0.871 | **C1 Overlap-Count** |
| books | 1.000 | 1.000 | 1.000 | 1.000 | **C1 Overlap-Count** |
| docs | 0.195 | 0.400 | 0.446 | 0.458 | **C3 Cross-Encoder** |

## Overall Winner

| Method | Mean Jaccard (all 16 probes) |
|--------|------------------------------|
| C1 Overlap-Count | 0.498 |
| C2 BM25 vanilla | 0.558 |
| C2' BM25-Capped | 0.565 |
| C3 Cross-Encoder | 0.609  ← **WINNER** |

## Mode-Specific Signals (margin ≥ 0.10 vs second-best)

- **general**: C3 Cross-Encoder leads by 0.121 (vs C2 BM25 vanilla at 0.181)

## Eval Caveats

### Engine Coverage
Google was **out on all 16 pairs** due to a CAPTCHA cascade: the `bee_fix` RATE_WAIT_TIMEOUT cap triggers once Google backoffs exceed 60s, and once Google hit that cap early in the batch it stayed blocked for the full probe run. This is an **8-engine eval** (not 9). All 4 C-methods saw the same reduced pool, so method comparison is internally valid — but Google's absence biases the pool toward DDG, Mojeek, academic APIs. A re-eval with Google included would be needed if a decision is borderline (especially for **general** mode where Google's ranking signal matters most).

### Empty Pools — Skipped Pairs
Two books pairs had pool=0 (no results passed BOOK_WHITELIST):
- `books × postgresql index types btree gin gist performance` — pool=0, skipped
- `books × contrastive learning self-supervised representations` — pool=0, skipped

These pairs are excluded from the books mode mean. **Effective N for books: 2 pairs** (transformer + asyncio), not 4.

### Undersized Pools — Unreliable Jaccard
The following pairs had pools smaller than oracle top-10, making Jaccard scores artificial (all methods trivially score 1.0 or near-1.0 because the oracle set equals the full pool):
- `books × transformer attention mechanism` — pool=4 (oracle includes all 4)
- `books × python asyncio event loop concurrency` — pool=10 (oracle includes all 10)
- `pdf × postgresql index types btree gin gist performance` — pool=2 (B1 report)
- `pdf × python asyncio event loop concurrency` — pool=5 (B1 report)

**Consequence:** the pdf mode (0.871 uniform) and books mode (1.000 uniform) scores are **noise**, not signal — all methods tie because the pool is too small to discriminate. The meaningful signal comes from **general** and **docs** modes only.

### Reliable Signal Modes
| Mode | Effective N | Pool sizes | Reliable? |
|------|-------------|-----------|-----------|
| general | 4 pairs | ~14–20 | ✅ Yes |
| docs | 4 pairs | 23–44 | ✅ Yes |
| pdf | 4 pairs | 2–13 (2 undersized) | ⚠️ Partly (2 pairs marginal) |
| books | 2 pairs | 4–10 (both at-or-near oracle size) | ❌ No (all methods tie) |

### Re-Eval Recommendation
If the decision between C3 and C2' for **docs** mode is borderline (current gap: 0.012 Jaccard), a re-run with Google restored and more queries would sharpen the signal. The 0.121 C3 lead in **general** mode is more robust and unlikely to reverse with Google included.
