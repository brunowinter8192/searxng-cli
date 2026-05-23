# Value Eval Summary v3 — 12-Method Phase 13

**Pairs:** 1 / 16  **Oracle:** pending

## Per-Mode Mean Latency (ms)

| Mode | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 | M11 | M12 |
|------|---|---|---|---|---|---|---|---|---|---|---|---|
| general | 0 | 0 | 0 | 12 | 1 | 1712 | 1773 | 0 | 1606 | 0 | 7654 | 10730 |

## Per-Method Latency Statistics (across 16 pairs)

| Method | Mean | p50 | p95 | Max | Tokens in/out (LLM) |
|--------|------|-----|-----|-----|---------------------|
| M1 C1 Overlap-Count | 0 | 0 | 0 | 0 | — |
| M2 RRF post-bucket | 0 | 0 | 0 | 0 | — |
| M3 Structural URL | 0 | 0 | 0 | 0 | — |
| M4 BM25 vanilla | 12 | 12 | 12 | 12 | — |
| M5 BM25-Capped | 1 | 1 | 1 | 1 | — |
| M6 C3 Cross-Encoder | 1712 | 1712 | 1712 | 1712 | — |
| M7 C3+InstrPrefix | 1773 | 1773 | 1773 | 1773 | — |
| M8 RRF+C3 Hybrid | 0 | 0 | 0 | 0 | — |
| M9 SPLADE | 1606 | 1606 | 1606 | 1606 | — |
| M10 SPLADE+C3 | 0 | 0 | 0 | 0 | — |
| M11 C3→LLM-Filter | 7654 | 7654 | 7654 | 7654 | 1597/283 |
| M12 LLM-Selector | 10730 | 10730 | 10730 | 10730 | 3362/297 |
