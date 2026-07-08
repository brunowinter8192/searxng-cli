# With-Google Decoupling Smoke — 20260509_011034

**Queries:** 5  
**Pass:** 5  
**Fail:** 0  
**Log lines written:** 5

## Invariants Checked (per query)

1. `google_scholar` NOT in `engines_requested`
2. `google` IS in `engines_requested`
3. `engines_excluded["google_scholar"] == "decoupled_from_google"`
4. `engines_excluded` field present in log entry

## Results

| # | Query | Pass | Scholar absent | Google present | Excluded correct | engines count |
|---|-------|------|----------------|----------------|-----------------|---------------|
| 1 | python asyncio concurrent programming | ✓ | ✓ | ✓ | ✓ | 9 |
| 2 | machine learning gradient descent optimization | ✓ | ✓ | ✓ | ✓ | 9 |
| 3 | docker kubernetes container orchestration | ✓ | ✓ | ✓ | ✓ | 9 |
| 4 | REST API authentication JWT OAuth | ✓ | ✓ | ✓ | ✓ | 9 |
| 5 | database indexing B-tree performance | ✓ | ✓ | ✓ | ✓ | 9 |