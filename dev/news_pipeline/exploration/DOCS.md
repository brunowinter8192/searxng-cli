# dev/news_pipeline/exploration/

Manual UI exploration probes for news sites via pydoll headed browser. Goal: learn page structure (button selectors, DOM shape, load-more mechanics) before building production-grade discovery scripts. NOT a production pipeline.

**Convention:** all scripts run headed (`headless=False` default). `--headless` for opt-out.

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

## Output Directories

| Directory | Contents | Gitignored |
|---|---|---|
| `01_output/` | `probe_<ts>.json` run results | ✅ yes |
