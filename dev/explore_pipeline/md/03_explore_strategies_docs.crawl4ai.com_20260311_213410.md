# Explore Strategy Comparison

URL: https://docs.crawl4ai.com
Depth: 2 | Max Pages: 50
Date: 2026-03-11 21:34

## Results

| Strategy | Pages | Time (s) | Per Page (ms) | Duplicates |
|----------|-------|----------|---------------|------------|
| baseline_domcontentloaded | 49 | 668.3 | 13639 | 1 |
| prefetch_domcontentloaded | 49 | 13.6 | 278 | 1 |
| prefetch_no_wait | 49 | 14.2 | 289 | 1 |

## Speedup vs Baseline

- **prefetch_domcontentloaded**: 49.1x faster
- **prefetch_no_wait**: 47.1x faster

## Depth Distribution

### baseline_domcontentloaded
- Depth 0: 1 pages
- Depth 1: 48 pages

### prefetch_domcontentloaded
- Depth 0: 1 pages
- Depth 1: 48 pages

### prefetch_no_wait
- Depth 0: 1 pages
- Depth 1: 48 pages
