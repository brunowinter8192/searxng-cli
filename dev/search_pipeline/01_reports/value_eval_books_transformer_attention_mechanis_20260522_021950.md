# Value Eval — books × transformer attention mechanism

**Mode:** books  
**Query:** transformer attention mechanism  
**Pool size (filtered):** 4  
**google_count:** 0  
**full_pool:** 441  | **capped_pool:** 62  
**filtered_capped:** 4  

## Pool (oracle input — url/title/snippet only)

1. https://openlibrary.org/works/OL12439399W
   Title: Cartesian meditations
   Snippet: Edmund Husserl (1960) — 13 eds, ebook: no_ebook

2. https://openlibrary.org/works/OL15311250W
   Title: The origin of ideas
   Snippet: Antonio Rosmini (1883) — 7 eds, ebook: public

3. https://openlibrary.org/works/OL1618262W
   Title: History of the World's Fair
   Snippet: Benjamin Cummings Truman (1893) — 5 eds, ebook: public

4. https://openlibrary.org/works/OL18481636W
   Title: Understanding events
   Snippet: Jeffrey M. Zacks (2007) — 3 eds, ebook: borrowable

## Oracle Selection

1. https://openlibrary.org/works/OL12439399W
   Rationale: 

2. https://openlibrary.org/works/OL15311250W
   Rationale: 

3. https://openlibrary.org/works/OL1618262W
   Rationale: 

4. https://openlibrary.org/works/OL18481636W
   Rationale: 

## C-Method Top-10s

### C1 Overlap-Count — 0ms

1. https://openlibrary.org/works/OL18481636W
2. https://openlibrary.org/works/OL1618262W
3. https://openlibrary.org/works/OL15311250W
4. https://openlibrary.org/works/OL12439399W

### C2 BM25 vanilla — 0ms

1. https://openlibrary.org/works/OL18481636W
2. https://openlibrary.org/works/OL1618262W
3. https://openlibrary.org/works/OL15311250W
4. https://openlibrary.org/works/OL12439399W

### C2' BM25-Capped — 0ms

1. https://openlibrary.org/works/OL18481636W
2. https://openlibrary.org/works/OL1618262W
3. https://openlibrary.org/works/OL15311250W
4. https://openlibrary.org/works/OL12439399W

### C3 Cross-Encoder — 111ms

1. https://openlibrary.org/works/OL18481636W
2. https://openlibrary.org/works/OL15311250W
3. https://openlibrary.org/works/OL12439399W
4. https://openlibrary.org/works/OL1618262W

## Comparison (Oracle vs Methods)

| Method | Jaccard | Oracle URLs captured |
|--------|---------|----------------------|
| C1 Overlap-Count | 1.000 | 4 / 4 |
| C2 BM25 vanilla | 1.000 | 4 / 4 |
| C2' BM25-Capped | 1.000 | 4 / 4 |
| C3 Cross-Encoder | 1.000 | 4 / 4 |

### Oracle URLs missed by all methods

_All oracle URLs captured by at least one method._
