# Engine Report — books × postgresql index types btree gin gist performance

**Mode:** books
**Query:** postgresql index types btree gin gist performance
**Fetched:** 2026-05-22T23:14:34

## Pool Sizes

| Stage | Count |
|-------|------:|
| Raw results | 241 |
| Capped (K=google_count) | 47 |
| Filtered (books filter) | 1 |
| Oracle pool (filtered+capped) | 1 |

## Engine Breakdown

| Engine | URLs | Status | Reason | ms |
|--------|-----:|--------|--------|----|
| crossref | 200 | OK |  | 909 |
| duckduckgo | 10 | OK |  | 983 |
| google | 10 | OK |  | 657 |
| mojeek | 10 | OK |  | 572 |
| lobsters | 6 | OK |  | 2488 |
| openalex | 5 | OK |  | 620 |
| open_library | 0 | EMPTY | empty | 1048 |
| semantic_scholar | 0 | EMPTY_NO_CONTAINER | no DOM container | 3053 |
| stack_exchange | 0 | EMPTY | empty | 294 |

## Pool URL Listing (oracle pool — 1 URLs, sorted by URL)

1. https://pganalyze.com/ebooks/postgres-indexing
   Title: Indexing Postgres: Creating The Best Index For Your Queries
   Snippet: Indexing can make a significant impact on the performance of your application's query workload. Too many indexes will slow down your write performance, but creating the right indexes can often improve
