# src/news/platforms/theblock/

## Role

The Block platform implementation. Uses the `proxy_pool` scrape engine (curl_cffi rotation,
no browser) and its own RAG collection `"theblock"`. Discovery is sitemap-based (not feed-scroll).
`dedup_mode = "hash_only"` because no publication_date is available at discover time — the date
comes from JSON-LD post-fetch and is mutated into `entry["publication_date"]` by cleanup.

Imported for side-effects by `__main__.py` — the import registers `TheBlockPlatform()` into the
registry. No other module should import from here directly.

## Public Interface

`__init__.py` exports `TheBlockPlatform` (implements `Platform` Protocol).
Auto-registers via `register(TheBlockPlatform())` at module end.

Extra platform attributes (not in Protocol):
- `timeframe: str` — discovery mode (`"delta"` default); overwritten by `__main__` from `--timeframe`.
- `dedup_mode: str = "hash_only"` — consumed by `pipeline.py` via `getattr`.

## Modules

### config.py (14 LOC)

**Purpose:** Platform constants — `SITEMAP_INDEX`, `DIRECT_TIMEOUT`, `DEFAULT_TIMEFRAME`,
`PROXY_SCRAPE_CONFIG` (`ProxyScrapeConfig(pool_provider=load_backfill_pool, content_type="html")`),
`SCRAPE_CONFIG` (default `ScrapeConfig()`, required by Protocol but ignored by proxy path).
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `__init__.py`, `discover.py`.
**Calls out:** `engine/proxy_pool/pool_loaders.py:load_backfill_pool`.

---

### discover.py (136 LOC)

**Purpose:** Sitemap-based article discovery. Fetches theblock sitemap index (direct httpx →
proxy pool fallback), selects `post_type_post_*` sub-sitemaps by mode (`delta`/`full`/`sub:N`),
parses `<url>/<loc>/<lastmod>` blocks — no date filtering. Returns `[{url, lastmod}]` — NO
`publication_date` (comes from JSON-LD post-fetch in cleanup).
**Reads:** `https://www.theblock.co/sitemap_tbco_index.xml` + selected sub-sitemaps (network).
**Writes:** nothing.
**Called by:** `__init__.py:TheBlockPlatform.discover`.
**Calls out:** `httpx`, `engine/proxy_pool/fetch.py:fetch_url`,
`engine/proxy_pool/pool_loaders.py:load_backfill_pool`.

Three timeframe modes (read from `self.timeframe`); no `lastmod` date filtering in any mode:
- `"delta"` (default) — top-2 highest-numbered `post_type_post_*` subs, all URLs. Rollover-safe recurring run.
- `"full"` — all `post_type_post_*` subs, all URLs. Complete backfill.
- `"sub:N"` — exactly the sub whose trailing index == N (e.g. `sub:0` → `post_type_post_0.xml`), all URLs. Bounded backfill chunk. Raises `RuntimeError` if N not found.

Proxy pool is lazy-loaded into `pool_cache` on first fallback; shared across all XML fetches
in the same discover call (index + sub-sitemaps) to avoid loading the pool twice.

---

### cleanup.py (101 LOC)

**Purpose:** Parse JSON-LD `NewsArticle` block from raw HTML fetched by proxy engine →
extract `articleBody` (HTML) → convert to Markdown via `crawl4ai.html2text.HTML2Text` →
apply `_post_clean()` regex pass → mutate `entry["publication_date"] = datePublished`
(ISO string) so `_run_cleanup` in `pipeline.py` can produce the correct
`theblock__YYYY-MM-DD__{hash}.md` filename.
**Reads:** raw HTML string (proxy engine output), entry dict (scrape manifest).
**Writes:** mutates `entry["publication_date"]` in place.
**Called by:** `__init__.py:TheBlockPlatform.cleanup`.
**Calls out:** `crawl4ai.html2text` (bundled, no new dep).

JSON-LD shape hardening — `_iter_candidates()` handles all common shapes without crashing:
plain dict, dict with `@graph`, top-level array, non-dict values (int/str) silently skipped.

`_post_clean()` regex pass (applied after html2text, in this order):
1. Inline-URL strip: `[text](url)` → `text` (removes SendGrid/tracking URLs embedded in body).
2. Disclaimer line: `^Disclaimer: The Block is an independent media outlet.*$` removed.
3. Copyright line: `^©\s*\d{4}\s+The Block\.\s*All Rights Reserved.*$` removed (year-agnostic).
4. Newsletter CTA: `^_.*subscribe to the .*newsletter.*_\s*$` removed (italic-line anchor).
5. Trailing whitespace per line; blank-run collapse to single blank; final strip.

Fallback: if no `NewsArticle` or no `articleBody` → returns `""` + stderr log, no crash.

---

### __init__.py (31 LOC)

**Purpose:** `TheBlockPlatform` class wrapping config + discover + cleanup; auto-registers on import.
Fields: `name/collection="theblock"`, `scrape_engine="proxy_pool"`, `regwall_signals=[]`,
`proxy_scrape_config=PROXY_SCRAPE_CONFIG`, `timeframe="delta"`, `dedup_mode="hash_only"`.
`precondition_url="https://www.google.com"` (theblock.co returns 403 on plain urllib).
**Called by:** `__main__.py` (side-effect import).
