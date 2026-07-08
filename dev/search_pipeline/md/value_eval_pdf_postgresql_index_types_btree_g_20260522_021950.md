# Value Eval — pdf × postgresql index types btree gin gist performance

**Mode:** pdf  
**Query:** postgresql index types btree gin gist performance  
**Pool size (filtered):** 2  
**google_count:** 0  
**full_pool:** 231  | **capped_pool:** 41  
**filtered_capped:** 2  

## Pool (oracle input — url/title/snippet only)

1. https://minervadb.xyz/wp-content/uploads/2025/04/Optimal-Indexing-for-PostgreSQL-Performance.pdf
   Title: PDF Optimal Indexing for PostgreSQL Performance
   Snippet: Both GiST and SP-GiST index types excel in specialized domains where traditional B-tree indexes are inefficient or unsuitable. These indexes enable PostgreSQL to compete with specialized database syst

2. https://momjian.us/main/writings/pgsql/indexing.pdf
   Title: PDF Flexible Indexing with Postgres - Momjian
   Snippet: GIST range-type indexing uses large ranges at the top level of the index, with ranges decreasing in size at lower levels, just like how R-tree bounding boxes are indexed.

## Oracle Selection

1. https://momjian.us/main/writings/pgsql/indexing.pdf
   Rationale: Bruce Momjian (core PostgreSQL developer) 'Flexible Indexing with Postgres' PDF — authoritative practitioner reference covering GiST R-tree indexing, index types, and performance characteristics from a core PG contributor.

2. https://minervadb.xyz/wp-content/uploads/2025/04/Optimal-Indexing-for-PostgreSQL-Performance.pdf
   Rationale: MinervaDB 'Optimal Indexing for PostgreSQL Performance' PDF — practical guide covering B-tree, GiST, SP-GiST, GIN, and performance trade-offs including when non-B-tree indexes are superior.

## C-Method Top-10s

### C1 Overlap-Count — 0ms

1. https://momjian.us/main/writings/pgsql/indexing.pdf
2. https://minervadb.xyz/wp-content/uploads/2025/04/Optimal-Indexing-for-PostgreSQL-Performance.pdf

### C2 BM25 vanilla — 0ms

1. https://minervadb.xyz/wp-content/uploads/2025/04/Optimal-Indexing-for-PostgreSQL-Performance.pdf
2. https://momjian.us/main/writings/pgsql/indexing.pdf

### C2' BM25-Capped — 0ms

1. https://minervadb.xyz/wp-content/uploads/2025/04/Optimal-Indexing-for-PostgreSQL-Performance.pdf
2. https://momjian.us/main/writings/pgsql/indexing.pdf

### C3 Cross-Encoder — 86ms

1. https://minervadb.xyz/wp-content/uploads/2025/04/Optimal-Indexing-for-PostgreSQL-Performance.pdf
2. https://momjian.us/main/writings/pgsql/indexing.pdf

## Comparison (Oracle vs Methods)

| Method | Jaccard | Oracle URLs captured |
|--------|---------|----------------------|
| C1 Overlap-Count | 1.000 | 2 / 2 |
| C2 BM25 vanilla | 1.000 | 2 / 2 |
| C2' BM25-Capped | 1.000 | 2 / 2 |
| C3 Cross-Encoder | 1.000 | 2 / 2 |

### Oracle URLs missed by all methods

_All oracle URLs captured by at least one method._
