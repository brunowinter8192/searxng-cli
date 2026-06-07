# src/news/platforms/coindesk/

## Role

CoinDesk platform implementation. Imported for side-effects by `__main__.py` — the import
registers `CoinDeskPlatform()` into the registry. No other module should import from here directly.

## Public Interface

`__init__.py` exports `CoinDeskPlatform` (implements `Platform` Protocol).
Auto-registers via `register(CoinDeskPlatform())` at module end.

## Modules

### config.py (15 LOC)

**Purpose:** Platform constants — REGWALL_SIGNALS, SCRAPE_CONFIG (ScrapeConfig()), discovery params.
**Called by:** `__init__.py`, `discover.py`.

### discover.py (185 LOC)

**Purpose:** Pydoll UI pagination of CoinDesk latest-news feed. Launches Chrome via `open -gna`,
connects via CDP, clicks "More stories" up to MAX_CLICK_ROUNDS, extracts article links via JS,
filters live-blogs. Returns entry list `[{url, lastmod, publication_date, title, section}]`.
**Called by:** `__init__.py:CoinDeskPlatform.discover`.
**Calls out:** `pydoll` (Chrome CDP).

Termination: stops when ≥ PRE_48H_THRESHOLD articles older than CUTOFF_DAYS (2) are seen.

### cleanup.py (100 LOC)

**Purpose:** Strip CoinDesk page chrome from raw crawl4ai markdown → pure article body.
Logic: H1 start-anchor → first end-anchor (_END_ANCHORS: MORE_FOR_YOU, PRIVACY, TAG_FOOTER) →
clean_body (tag-footer strip, image strip, byline/date strip, inline-link substitution, paragraph normalization).
**Called by:** `__init__.py:CoinDeskPlatform.cleanup`.
**Calls out:** stdlib re only.

No H1 found → returns `raw_markdown.strip()` (fallback, logged upstream).

### __init__.py (20 LOC)

**Purpose:** `CoinDeskPlatform` class wrapping config + discover + cleanup; auto-registers on import.
**Called by:** `__main__.py` (side-effect import).
