# DDG + Mojeek DOM Selector Probe — 20260507_030048

**Query:** `python asyncio`

---

## DuckDuckGo

**URL:** `https://html.duckduckgo.com/html/?q=python+asyncio&kl=wt-wt`

### DOM Counts

| Selector / Metric | Count |
|-------------------|-------|
| `#links > div.web-result` — current container | 10 |
| `#links > div` — all direct div children | 13 |
| `#links > div:not(.web-result)` — non-organic blocks | 3 |
| web-results with `h2 a` (current title selector) | 10 |
| web-results with `a.result__snippet` (current snippet) | 10 |
| `h2` anywhere in `#links` | 10 |
| `a.result__snippet` anywhere in `#links` | 10 |
| `div.result__body` | 10 |
| `div.results_links` | 10 |
| `div.result__title` | 0 |
| Ad/sponsored blocks | 0 |
| External `<a>` total (non-duckduckgo.com) | 0 |

### First-5 web-result Structure

| # | has h2 a | Title | Link (80ch) | has snippet |
|---|----------|-------|-------------|-------------|
| 1 | True | asyncio — Asynchronous I/O — Python 3.14.5rc1 documenta | https://duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.python.org%2F3%2Flibrary%2Fasy | True |
| 2 | True | Python's asyncio: A Hands-On Walkthrough - Real Python | https://duckduckgo.com/l/?uddg=https%3A%2F%2Frealpython.com%2Fasync%2Dio%2Dpytho | True |
| 3 | True | asyncio in Python - GeeksforGeeks | https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.geeksforgeeks.org%2Fpython%2Fas | True |
| 4 | True | Python asyncio Module - W3Schools | https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.w3schools.com%2Fpython%2Fref_mo | True |
| 5 | True | Python asyncio: Kompletter Leitfaden zur asynchronen Pr | https://duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.kanaries.net%2Fde%2Ftopics%2FP | True |

### Diagnosis

**Verdict:** `#links > div.web-result` misses 3 non-web-result divs in `#links` (ads=0).

Total divs in `#links` = 13, web-result = 10, non-web-result = 3. External links = 0.

---

## Mojeek

**URL:** `https://www.mojeek.com/search?q=python+asyncio&safe=1`

### DOM Counts

| Selector / Metric | Count |
|-------------------|-------|
| `ul.results-standard > li` — total result items | 10 |
| `ul.results-standard > li > a.ob` — current wait/parse anchor | 10 |
| li containing `a.ob` | 10 |
| li WITHOUT `a.ob` (missed by current selectors) | 0 |
| li containing `h2 a` (title) | 10 |
| li containing `p.s` (snippet) | 10 |
| `ul.results-standard` count | 1 |
| Other `<ul>` elements on page | 13 |
| `div.result` containers | 0 |
| Pagination links | 5 |
| External `<a>` total (non-mojeek.com) | 22 |

### First-5 li Structure

| # | has a.ob | ob_href (80ch) | has h2 a | Title | has p.s |
|---|----------|---------------|----------|-------|---------|
| 1 | True | https://docs.python.org/3/library/asyncio-task.html | True | Coroutines and Tasks — Python 3.14.3 documentation | True |
| 2 | True | https://docs.python.org/3/library/asyncio-queue.html | True | Queues — Python 3.14.3 documentation | True |
| 3 | True | https://stackoverflow.com/questions/36336330/multi-threaded-asyncio-in-python | True | multithreading - Multi-threaded asyncio in Python - Sta | True |
| 4 | True | https://stackoverflow.com/questions/65277825/python-asyncio-does-not-seem-to-be- | True | Python Asyncio - does not seem to be working in asynchr | True |
| 5 | True | https://github.com/python/asyncio | True | GitHub - python/asyncio: asyncio historical repository  | True |

### Diagnosis

**Verdict:** Coverage complete — every `li` has `a.ob` and `h2 a`. Current selectors are sound.

All 10 li have both `a.ob` and `h2 a`. The 10-result ceiling is Mojeek's default page size — no count parameter is available in the current URL.