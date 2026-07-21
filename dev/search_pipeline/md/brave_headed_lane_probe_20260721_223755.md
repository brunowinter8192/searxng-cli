# Brave Headed-Background Lane Probe — 20260721_223755

Dev-only probe: headed-but-backgrounded Chrome (macOS `open -g`, isolated profile) against Brave Search, one query at a time. Gate: real results, <=5s per query, and a usable run of 3-4+ consecutive clean (no-PoW) queries (relaxed bar — does not need to be block-free forever).

## Verdict

**DROP — PoW/CAPTCHA triggered on 8/10 queries, longest clean run only 2**

## Launch Mechanism

- `Chrome(options)` constructed normally, then `browser._browser_process_manager` is swapped for `BrowserProcessManager(process_creator=_open_process_creator)` BEFORE `await browser.start()` (`Chrome.__init__` does not expose `process_creator`).
- `_open_process_creator(command)` drops `command[0]` (resolved binary_location, unused) and runs `open -g -n -a "Google Chrome" --args --remote-debugging-port=<port> --user-data-dir=<isolated dir> ...` — `-g` = no focus steal, `-n` = force new instance.
- Isolated profile: `~/.searxng-mcp/brave-headed-probe-session` (NOT the shared engine session dir) — block-isolation + forces a genuinely fresh Chrome process.
- Teardown: CDP `browser.stop()` (works — it's a real `Browser.close` CDP command against the real Chrome instance) PLUS an unconditional `pkill -f user-data-dir=<isolated dir>` safety net, because `open -g` returns immediately so pydoll's own `stop_process()` only ever had the short-lived `open` wrapper process to reap, not Chrome itself.

## Headline

- **Queries:** 10
- **OK (results returned):** 2
- **PoW/CAPTCHA triggered:** 8
- **ERROR:** 0
- **Latency <= 5.0s:** 10/10
- **Latency distribution (ms):** min=1742, median=1753, max=3420
- **Longest consecutive clean (no-PoW) run:** 2

## Per-Query Results

| # | Query | Axis | Status | Count | PoW | Elapsed ms | <= 5s? |
|---|-------|------|--------|-------|-----|------------|--------|
| 1 | beste kaffeemaschine test | mainstream-de | OK | 10 | False | 3420 | yes |
| 2 | python asyncio tutorial | docs-en | OK | 10 | False | 2152 | yes |
| 3 | gebrauchte waschmaschine frankfurt | local-biz-de | POW_BLOCKED | 0 | True | 1751 | yes |
| 4 | hausgeräte händler frankfurt | local-biz-de | POW_BLOCKED | 0 | True | 1912 | yes |
| 5 | gebrauchtwagen ankauf frankfurt | local-biz-de | POW_BLOCKED | 0 | True | 1743 | yes |
| 6 | best noise cancelling headphones 2025 | mainstream-en | POW_BLOCKED | 0 | True | 1742 | yes |
| 7 | how does DNS work | docs-en | POW_BLOCKED | 0 | True | 1751 | yes |
| 8 | fastapi websocket reconnect handler | docs-en | POW_BLOCKED | 0 | True | 1756 | yes |
| 9 | climate change carbon capture technology 2025 | mainstream-en | POW_BLOCKED | 0 | True | 1817 | yes |
| 10 | Mietvertrag Kündigungsfrist gesetzliche Regel | docs-de | POW_BLOCKED | 0 | True | 1742 | yes |

## Sample Results (quality eyeball)

### [1] beste kaffeemaschine test (mainstream-de) — 10 results

- **Die 12 besten Kaffeemaschinen im aktuellen Vergleich 07/2026** — https://www.testsieger.de/kaffeemaschinen/
  - Im ETM Testmagazin (Ausgabe 02/2026) treten zwei Kaffeepadmaschinen gegeneinander an. Testsieger ist die Tchibo Call Me Pad, die mit schneller Zubereitung, einf
- **Beste Kaffeevollautomaten in Tests: Aktueller Vergleich 2026** — https://www.mediamarkt.de/de/content/heim-garten/kueche/kaffeevollautomaten-in-tests
  - 18. Juni 2026 - In der aktuellen Liste der besten Kaffeevollautomaten bei Computer Bild (08/25) ist der De'Longhi Rivelia EXAM440.55.B Testsieger mit der Note „
- **Kaffeemaschinen im Test: Diese Maschine bringt Aroma in Rekordzeit - IMTEST** — https://www.imtest.de/haushalt-kueche/kaffeemaschinen-test-schnell-guten-kaffee-mit-aroma/315529
  - vor 2 Wochen - Die Severin Filka 2.0 KA 4853 ist als Testsieger im Vergleich der Kaffeemaschinen hervorgegangen. Gründe dafür sind das integrierte Mahlwerk, der
- **Kaffeemaschine Test 2026: Die besten Filterkaffeemaschinen - testit.de** — https://www.testit.de/tag/kaffeemaschine.html
  - vor 5 Tagen - Optisch macht sie mit Edelstahl, cleanem Display und großem Drehregler richtig was her, und die 1,8-Liter-Kanne ist die größte im Test und versorg
- **Die beste Kaffeemaschine | Test 07/2026 | F.A.Z. Kaufkompass** — https://www.faz.net/kaufkompass/test/die-beste-kaffeemaschine/
  - 3. Juni 2026 - Wir haben 26 Kaffeemaschinen getestet. Testsieger Sage Precision Brewer brüht köstlichen Kaffee und bietet viele Einstellungen.

### [2] python asyncio tutorial (docs-en) — 10 results

- **Python's asyncio: A Hands-On Walkthrough – Real Python** — https://realpython.com/async-io-python/
  - 30. Juli 2025 - Python’s asyncio library enables you to write concurrent code using the async and await keywords. The core building blocks of async I/O in Pytho
- **asyncio — Asynchronous I/O** — https://docs.python.org/3/library/asyncio.html
  - Hello World!: asyncio is a library to write concurrent code using the async/await syntax. asyncio is used as a foundation for multiple Python asynchronous frame
- **A Conceptual Overview of asyncio — Python 3.14.6 documentation** — https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html
  - How does asyncio differentiate between a task which doesn’t need CPU time (such as a network request or file read) as opposed to a task that does (such as compu
- **Mastering Python’s Asyncio: A Practical Guide | by Moraneus | Medium** — https://medium.com/@moraneus/mastering-pythons-asyncio-a-practical-guide-0a673265cf04
  - 17. Mai 2024 - First off, asyncio is all about writing code that can do multiple things at once, without actually doing them at the same time. It’s like having 
- **Python Tutorial: AsyncIO - Complete Guide to Asynchronous Programming with Animations - YouTube** — https://www.youtube.com/watch?v=oAkLSJNr5zY
  - 

## Non-OK Details

### [POW_BLOCKED] gebrauchte waschmaschine frankfurt (local-biz-de)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=gebrauchte+waschmaschine+frankfurt"}`

### [POW_BLOCKED] hausgeräte händler frankfurt (local-biz-de)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=hausger%C3%A4te+h%C3%A4ndler+frankfurt"}`

### [POW_BLOCKED] gebrauchtwagen ankauf frankfurt (local-biz-de)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=gebrauchtwagen+ankauf+frankfurt"}`

### [POW_BLOCKED] best noise cancelling headphones 2025 (mainstream-en)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=best+noise+cancelling+headphones+2025"}`

### [POW_BLOCKED] how does DNS work (docs-en)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=how+does+DNS+work"}`

### [POW_BLOCKED] fastapi websocket reconnect handler (docs-en)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=fastapi+websocket+reconnect+handler"}`

### [POW_BLOCKED] climate change carbon capture technology 2025 (mainstream-en)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=climate+change+carbon+capture+technology+2025"}`

### [POW_BLOCKED] Mietvertrag Kündigungsfrist gesetzliche Regelung (docs-de)

- **Diagnosis:** `{"marker": "captcha", "pow_link": true, "title": "Brave Search", "url": "https://search.brave.com/search?q=Mietvertrag+K%C3%BCndigungsfrist+gesetzliche+Regelung"}`
