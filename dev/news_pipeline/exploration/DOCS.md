# dev/news_pipeline/exploration/

Manual UI exploration probes for news sites. Goal: learn page structure (button selectors, DOM shape, load-more mechanics, network patterns) before building production-grade discovery scripts. NOT a production pipeline.

**Convention:** `01_coindesk_ui_probe.py` runs headed (`headless=False` default). `02_coindesk_pagination_probe.py` runs headless-only (Playwright, HAR capture).

## Scripts

### 01_coindesk_ui_probe.py

**Purpose:** Pydoll-driven playthrough of `https://www.coindesk.com/latest-crypto-news`. Learns the "More stories" button selector, click mechanics, article URL pattern, and how many clicks cover a 24h window. Outputs per-batch article URLs + time labels + button descriptor.

**Output:**
- `01_output/probe_<UTC-timestamp>.json` — full per-batch breakdown + button descriptor + summary
- `~/tmp/coindesk_button_pos.png` — screenshot of page with button visible (for selector debugging)

```bash
./venv/bin/python dev/news_pipeline/exploration/01_coindesk_ui_probe.py
./venv/bin/python dev/news_pipeline/exploration/01_coindesk_ui_probe.py --headless
```

### 02_coindesk_pagination_probe.py

**Purpose:** Playwright probe (system Chrome via `channel="chrome"`, headless) of `https://www.coindesk.com/latest-crypto-news`. Two modes: quick (5 clicks + full HAR) and `--depth` (click until disabled/plateau/150-cap + lightweight coindesk-only network log). Reverse-engineers the "More stories" pagination mechanism.

**Key finding (corrected by the depth run):** The first ~5 clicks reveal articles pre-embedded in the initial SSR HTML (Next.js RSC payload) — no network request. Once that buffer is exhausted (~click 6), each click fires a **cursor-based timeline API**:
`GET https://www.coindesk.com/api/v1/articles/timeline?size=16&lastId=<UUID>&lastDisplayDate=<ISO>`.
Depth run: 150 clicks → 2414 unique URLs, oldest 2026-01-23 (~5 months), button still active (no ceiling hit). Pagination is denser AND deeper than CoinDesk's article-sitemap (1198 unique / ~1 year). The API is plain GET 200 in-browser but returns 403 to plain curl AND curl_cffi-chrome — it needs the exact browser request (header/cookie/token set on page load); cracking that is deferred to the production build.

**Output:**
- `02_output/session.har` — quick-mode full network session with response bodies (~19MB)
- `02_output/report_<UTC-timestamp>.md` — quick-mode per-click table + network candidates + Click-1 vs Click-2 diff
- `02_output/depth_report_<UTC-timestamp>.md` — depth-mode trajectory + max-unique + oldest date + the timeline-API requests

```bash
./venv/bin/python dev/news_pipeline/exploration/02_coindesk_pagination_probe.py          # quick (5 clicks + HAR)
./venv/bin/python dev/news_pipeline/exploration/02_coindesk_pagination_probe.py --depth   # ceiling-finder
```

### 03_coindesk_backfill_traversal.py

**Purpose:** Uncapped browser-driven backfill of `https://www.coindesk.com/latest-crypto-news`.
Reuses production `discover.py` Chrome machinery (pydoll headed Chrome via `open -gna`, CDP).
Clicks "More stories" until button GONE / persistently DISABLED (3 retries, 2s wait + scroll
nudge each) / plateau (3 consecutive no-growth clicks). Writes a live-tailable progress log
(flushed per click), crash-safe URL checkpoint every 50 clicks, and final output in production
`build_entries()` shape `{url, lastmod, publication_date, title, section}`. Live-blog URLs
(slug starts with `live-`) filtered from output.

**Known issue:** `timeLabel` DOM walk in `_JS_EXTRACT` causes +3.23s/160-click slowdown —
fix (timeLabel-drop + delta extraction) required before the uncapped Stage B run.

**Output:**
- `03_output/progress_<ts>.log` — live log, one line per click, flush per write (`tail -f` safe)
- `03_output/checkpoint_urls.json` — overwritten every 50 clicks + on exit (crash-safe)
- `03_output/urls_<ts>.json` — final URL set, production entry shape, newest-first
- `03_output/report_stage_a_<ts>.md` — timing summary, DOM growth assessment, Stage B projection

```bash
./venv/bin/python dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py           # Stage A cap 400
./venv/bin/python dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py --cap 160  # custom cap
./venv/bin/python dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py --full     # Stage B uncapped
```

**CLI flags:**

| Flag | Effect |
|------|--------|
| _(none)_ | Bounded run, cap = `STAGE_A_CAP` (400) |
| `--cap N` | Override click ceiling to N |
| `--full` | Uncapped Stage B run |

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `probe_<ts>.json` run results | ✅ yes |
| `02_output/` | `session.har` + `report_<ts>.md` + `depth_report_<ts>.md` | ✅ yes |
| `03_output/` | `progress_<ts>.log` + `checkpoint_urls.json` + `urls_<ts>.json` + `report_stage_a_<ts>.md` | ✅ yes |
