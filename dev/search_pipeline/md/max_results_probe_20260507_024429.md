# Max Results Per Call Probe — 20260507_024429

**Scope:** 8 engines × 3 queries, direct engine instantiation (bypasses `search_web_workflow` hardcoded cap of 10).
**Per-engine max_results:** Google=100, Scholar=100, SE=100; DDG/Mojeek/Lobsters/OpenAlex/CrossRef=200.
**Queries:** `python asyncio` · `tolkien hobbit` · `sparse retrieval models`

## Detail Table

| Engine | Query | Requested | Returned | Latency ms | Status |
|--------|-------|-----------|----------|------------|--------|
| google | python asyncio | 100 | 9 | 4592 | OK |
| google | tolkien hobbit | 100 | 9 | 607 | OK |
| google | sparse retrieval models | 100 | 11 | 506 | OK |
| google_scholar | python asyncio | 100 | 20 | 844 | OK |
| google_scholar | tolkien hobbit | 100 | 19 | 291 | OK |
| google_scholar | sparse retrieval models | 100 | 20 | 298 | OK |
| duckduckgo | python asyncio | 200 | 10 | 1700 | OK |
| duckduckgo | tolkien hobbit | 200 | 10 | 781 | OK |
| duckduckgo | sparse retrieval models | 200 | 10 | 920 | OK |
| mojeek | python asyncio | 200 | 10 | 1244 | OK |
| mojeek | tolkien hobbit | 200 | 10 | 1565 | OK |
| mojeek | sparse retrieval models | 200 | 10 | 1272 | OK |
| lobsters | python asyncio | 200 | 20 | 480 | OK |
| lobsters | tolkien hobbit | 200 | 9 | 223 | OK |
| lobsters | sparse retrieval models | 200 | 20 | 349 | OK |
| openalex | python asyncio | 200 | 200 | 2106 | OK |
| openalex | tolkien hobbit | 200 | 199 | 1761 | OK |
| openalex | sparse retrieval models | 200 | 200 | 2497 | OK |
| crossref | python asyncio | 200 | 200 | 3315 | OK |
| crossref | tolkien hobbit | 200 | 200 | 2671 | OK |
| crossref | sparse retrieval models | 200 | 200 | 3694 | OK |
| stack_exchange | python asyncio | 100 | 100 | 437 | OK |
| stack_exchange | tolkien hobbit | 100 | 94 | 489 | OK |
| stack_exchange | sparse retrieval models | 100 | 17 | 360 | OK |

## Per-Engine Summary

| Engine | Requested | Ceiling (max returned) | Median latency ms | Notes |
|--------|-----------|----------------------|-------------------|-------|
| google | 100 | 11 | 607 | num= URL param; Google caps at 100 server-side |
| google_scholar | 100 | 20 | 298 | num= URL param; Scholar renders max ~20 per page |
| duckduckgo | 200 | 10 | 920 | No count param; post-fetch slice only — page renders naturally |
| mojeek | 200 | 10 | 1272 | No count param; post-fetch slice only — default 10 per page |
| lobsters | 200 | 20 | 349 | No count param; post-fetch slice only — pool is query-dependent |
| openalex | 200 | 200 | 2106 | per_page= API param; documented max 200 |
| crossref | 200 | 200 | 3315 | rows= API param; documented max 1000 |
| stack_exchange | 100 | 100 | 437 | pagesize= API param; hard cap 100 |