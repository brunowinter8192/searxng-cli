# CoinDesk Scrape Run — 2026-05-27 (Fresh Context / Iter 2)

| Field | Value |
|---|---|
| Run date | 2026-05-27 ~17:49 UTC |
| Command | `./venv/bin/python dev/news_pipeline/02b_coindesk_scrape_fresh_context.py --input dev/news_pipeline/01_output/discover_20260527T164927Z.json` |
| Input | `discover_20260527T164927Z.json` (25 URLs — same as iter 1) |
| Total URLs | 25 |
| ok | 23 |
| empty | 2 (networkidle timeout at 60.5s each) |
| failed | 0 |
| Regwall hits | **0** (vs 21 in iter 1) |
| Real body | **23 / 25** (92%, vs 4/25 in iter 1) |
| Total chars | 832,897 |
| Runtime | 284s |

**Timeout empties (networkidle 60s, unrelated to regwall):**
- `business/…/dtcc-plans-to-bring-tokenized-assets-to-stellar-in-latest-wall-street-blockchain-push`
- `policy/…/singapore-charges-former-hodlnaut-ceo-zhu-juntao-over-terra-collapse-claims`

**Sample previously-regwall'd URL now returning body:**
- `business/…/block-kicks-off-cash-app-s-phased-stablecoin-roll-out-to-its-nearly-60-million-users` — 35,612 chars (was 24,981 chars regwall in iter 1)

**Verdict:** PASS. Fresh context per URL resolves regwall. Filter-design unblocked.

See `decisions/OldThemes/news_pipeline_layers/03_coindesk_fresh_context_iteration2.md` for full analysis.
