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

**Purpose:** Playwright probe (system Chrome, headless) of `https://www.coindesk.com/latest-crypto-news`. Captures a full HAR + per-click trajectory to reverse-engineer the "More stories" pagination mechanism. Key finding: the button makes **no network request** to `www.coindesk.com` — article data is pre-embedded in the initial SSR HTML (Next.js RSC payload), and the button reveals them client-side only. No pagination API to replay.

**Output:**
- `02_output/session.har` — full network session with response bodies (19MB)
- `02_output/report_<UTC-timestamp>.md` — per-click table, network candidate list, Click-1 vs Click-2 diff

```bash
./venv/bin/python dev/news_pipeline/exploration/02_coindesk_pagination_probe.py
```

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `probe_<ts>.json` run results | ✅ yes |
| `02_output/` | `session.har` + `report_<ts>.md` | ✅ yes |
