# Google DOM Selector Probe — 20260507_025225

**Query:** `python asyncio`  **num=:** `100`
**URL:** `https://www.google.com/search?q=python+asyncio&hl=en&num=100`

## DOM Counts

| Selector / Metric | Count |
|-------------------|-------|
| `#rso h3` — current parse selector | 9 |
| `div.g` — classic organic container | 0 |
| `div.MjjYud` — modern result wrapper | 19 |
| `div[data-hveid]` — result attribute | 58 |
| `#rso > div` — direct RSO children | 18 |
| `#rso > div` containing an h3 | 8 |
| All `h3` on page | 9 |
| `h3` with a reachable external link | 9 |
| `div.g` with external link child | 0 |
| External `<a>` total (non-google.com) | 65 |
| Featured snippet containers | 2 |
| Knowledge Panel containers | 0 |
| People Also Ask containers | 0 |

## First-6 `#rso h3` Structure

| # | Title | has MjjYud | has #rso>div | parent tag | link (80ch) |
|---|-------|------------|--------------|------------|-------------|
| 1 | asyncio — Asynchronous I/O | True | True | A | https://docs.python.org/3/library/asyncio.html |
| 2 | Asynchronous I/O | True | True | DIV | https://docs.python.org/3/library/asyncio.html |
| 3 | Python's asyncio: A Hands-On Walkthrough | True | True | A | https://realpython.com/async-io-python/ |
| 4 | Python asyncio Module | True | True | A | https://www.w3schools.com/python/ref_module_asyncio.asp |
| 5 | Mastering Python's Asyncio: A Practical Guide | by Moraneus | True | True | A | https://medium.com/@moraneus/mastering-pythons-asyncio-a-practical-guide-0a67326 |
| 6 | A Conceptual Overview of asyncio | True | True | A | https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html |

## Hypothesis

**Dominant cause:** A — selector `#rso h3` captures only a subset; more organic results exist in DOM

`div.g` contains 0 organic results vs `#rso h3` finding 9. `div.MjjYud` = 19. Switching the parse walk to `div.MjjYud` or `div.g` as the result-block root would yield ~19 results per call.