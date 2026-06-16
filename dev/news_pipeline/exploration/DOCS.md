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

### 04_coindesk_timeline_replay_probe.py

**Purpose:** Captures CoinDesk timeline API requests via background Chrome + pydoll HAR recorder (full wire headers incl. `sec-ch-ua*`), replays via `httpx` + `curl_cffi`, and chains cursor-based calls. Establishes the minimum header set for replay (Referer, User-Agent, `sec-ch-ua*` — no cookie/auth required).

**Key finding:** HTTP replay works: a cursor loop of 7 calls returns 200 at ~0.27s each. Endpoint:
`GET https://www.coindesk.com/api/v1/articles/timeline?size=16&lastId=<UUID>&lastDisplayDate=<ISO>&lang=en`
Cursor = last article's `_id` (lastId) + `articleDates.displayDate` (lastDisplayDate).

**Output:** `04_output/report_<ts>.md`

```bash
./venv/bin/python dev/news_pipeline/exploration/04_coindesk_timeline_replay_probe.py
./venv/bin/python dev/news_pipeline/exploration/04_coindesk_timeline_replay_probe.py --loop 20 --delay 0.3
./venv/bin/python dev/news_pipeline/exploration/04_coindesk_timeline_replay_probe.py --rate-test
```

| Flag | Effect |
|------|--------|
| `--loop N` | cursor-loop calls after initial capture (default: 3) |
| `--delay S` | seconds between cursor calls (default: 0.3) |
| `--rate-test` | rerun loop with 2s delay to probe time-vs-count limit |

### 05_coindesk_cursor_probe.py

**Purpose:** Investigates cursor validity and storyType distribution across paginated timeline calls. Walk mode: pages through N calls logging ALL article `_id`, `storyType`, `pathname`, `displayDate` per response, producing a storyType distribution and flagging the target article. Fixed mode: chains cursor calls with optional storyType filtering (now used as retry-fallback: on 403, falls back to N-1/N-2 cursor article).

**Key findings:**
- StoryType distribution (128 articles): `News` 91.4%, `live_news` 5.5%, `Opinion` 3.1%.
- `cc8f264d` (the predecessor's deterministic 403 cursor) is a **standard "News" article** — storyType hypothesis disproved.
- The 403 at `cc8f264d` was **transient article unavailability** (backend rejected that specific article ID at that point in time), NOT a storyType rule. Confirmed: after the walk, `cc8f264d` returned 200 from a fresh session.
- Valid anchor rule: **any article can be a cursor anchor**. On 403, fall back to N-1 article in the same batch.

**Output:** `05_output/walk_<ts>.md`, `05_output/walk_<ts>_articles.json`, `05_output/fixed_<ts>.md`, `05_output/deep_<ts>.md`

```bash
./venv/bin/python dev/news_pipeline/exploration/05_coindesk_cursor_probe.py --mode walk --n 25
./venv/bin/python dev/news_pipeline/exploration/05_coindesk_cursor_probe.py --mode fixed --n 300 --invalid-types "sponsored,video"
```

| Flag | Effect |
|------|--------|
| `--mode walk\|fixed` | walk: log all storyTypes; fixed: skip invalid anchor types |
| `--n N` | number of paginated calls (default: 25) |
| `--invalid-types T1,T2` | comma-separated storyTypes to skip as cursor anchor (fixed mode) |
| `--delay S` | seconds between cursor calls (default: 0.3) |

### 05b_coindesk_warmth_probe.py

**Purpose:** Measures IP warmth duration after a browser session closes. Captures the first timeline API URL + headers via Chrome (same mechanism as 04), saves to `state.json`, closes Chrome, then replays the SAME URL at cumulative intervals (T=0, 10, 20, 30, 60, 120, 180, 300s). At first 403: tests httpx feedpage GET re-warm + subprocess cold call. Since no 403 was observed in 300s, Phase C was not triggered in the first run.

**Key findings:**
- Warmth lasts ≥300s (5 min) for repeated-URL replays after browser close.
- Warmth is **IP-level**: a fresh subprocess (no prior coindesk connection in that process) returns 200 when the IP is warm.
- Phase C (feedpage rewarm + cold path): not triggered — warmth outlasted the 300s ladder.
- Deep loop of 350 cursor advances (~4-5 min) also fully succeeded, consistent with ≥5 min warmth window.

**Output:** `05b_output/warmth_<ts>.md`, `05b_output/state.json`

```bash
./venv/bin/python dev/news_pipeline/exploration/05b_coindesk_warmth_probe.py
```

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `probe_<ts>.json` run results | ✅ yes |
| `02_output/` | `session.har` + `report_<ts>.md` + `depth_report_<ts>.md` | ✅ yes |
| `03_output/` | `progress_<ts>.log` + `checkpoint_urls.json` + `urls_<ts>.json` + `report_stage_a_<ts>.md` | ✅ yes |
| `04_output/` | `report_<ts>.md` | ✅ yes |
| `05_output/` | `walk_<ts>.md` + `walk_<ts>_articles.json` + `fixed_<ts>.md` + `deep_<ts>.md` | ✅ yes |
| `05b_output/` | `warmth_<ts>.md` + `state.json` | ✅ yes |
