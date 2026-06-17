# src/news/platforms/coindesk/

## Role

CoinDesk platform implementation. Imported for side-effects by `__main__.py` — the import
registers `CoinDeskPlatform()` into the registry. No other module should import from here directly.

## Public Interface

`__init__.py` exports `CoinDeskPlatform` (implements `Platform` Protocol).
Auto-registers via `register(CoinDeskPlatform())` at module end.

## Modules

### config.py (38 LOC)

**Purpose:** Platform constants — REGWALL_SIGNALS, SCRAPE_CONFIG (ScrapeConfig()), timeline-API
discovery params (TIMELINE_BASE, COINDESK_BASE, TARGET_URL, CALL_DELAY, REWARM_EVERY,
CLICKS_WARMUP, CLICKS_REWARM, MAX_CURSOR_FALLBACKS, CHECKPOINT_EVERY, DEFAULT_DELTA_DAYS,
FULL_MODE_FLOOR, INVENTORY_DIR, SKIP_HEADERS).
**Called by:** `browser.py`, `discover.py`, `__init__.py`.

### browser.py (170 LOC)

**Purpose:** Chrome browser launch + pydoll HAR-capture machinery for the initial feed warmup.
`browser_load_feed(n_clicks)` launches Chrome via `open -gna`, navigates to latest-crypto-news,
clicks "More stories" n times under HAR record, captures the first `/api/v1/articles/timeline`
request (URL + headers + first response body). Returns `(headers, api_url, body_bytes)`.
**Called by:** `discover.py:discover`, `discover.py:try_rewarm`.
**Calls out:** `pydoll` (Chrome CDP), `httpx` (first response replay).

### discover.py (337 LOC)

**Purpose:** Timeline-API cursor loop + master inventory management.
`discover(timeframe)` orchestrates: warmup → load inventory → `cursor_loop` →
incremental inventory write → return entry list.

Cursor loop pages backward in reverse-chronological order. Each 16-article batch: parse, filter
live-blogs, append genuinely new URLs to per-year inventory shards (`data/news/coindesk/inventory/
coindesk_{year}.txt`, format `YYYY-MM-DD\t<url>`). Termination: oldest article in batch < stop_date.
Re-warm strategy: httpx feedpage GET first; browser re-warm as fallback. Crash-safe: URLs written
per-article; re-run skips already-present URLs via load_inventory() diff.

**Called by:** `__init__.py:CoinDeskPlatform.discover`.
**Calls out:** `httpx` (cursor loop), `browser.py:browser_load_feed` (warmup + re-warm).

Timeframe parsing: `"full"` → FULL_MODE_FLOOR (`"2018-01-01"`);
integer string N → today − N days; anything else (incl. `"delta"`) → DEFAULT_DELTA_DAYS (30).

### cleanup.py (123 LOC)

**Purpose:** Strip CoinDesk page chrome from raw crawl4ai markdown → pure article body.
Logic: H1 start-anchor → first end-anchor (_END_ANCHORS: MORE_FOR_YOU, PRIVACY, TAG_FOOTER) →
clean_body (tag-footer strip, image strip, byline/date strip, inline-link substitution, paragraph normalization).
**Called by:** `__init__.py:CoinDeskPlatform.cleanup`.
**Calls out:** stdlib re only.

No H1 found → returns `raw_markdown.strip()` (fallback, logged upstream).

### __init__.py (30 LOC)

**Purpose:** `CoinDeskPlatform` class wrapping config + discover + cleanup; auto-registers on import.
Attribute `timeframe: str = "30"` set by `__main__` via `--timeframe`.
**Called by:** `__main__.py` (side-effect import).
