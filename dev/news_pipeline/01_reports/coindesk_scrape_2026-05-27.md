# CoinDesk Scrape Run — 2026-05-27

| Field | Value |
|---|---|
| Run date | 2026-05-27 ~16:49 UTC |
| Command | `./venv/bin/python dev/news_pipeline/02_coindesk_scrape.py` |
| Input | `01_output/discover_20260527T164927Z.json` (25 URLs, 24h window) |
| Total URLs | 25 |
| ok | 25 (HTTP-level) |
| empty | 0 |
| failed | 0 |
| Regwall'd | 21 / 25 (84%) |
| Real body | 4 / 25 |
| Total chars | 678,228 |
| Runtime | 107s |

**Non-regwall'd (real body, 34k+ chars):**
- `coindesk-indices/…/crypto-long-and-short-how-the-genius-act-repriced-bitcoin-s-monetary-premium` — 49,322 chars
- `business/…/bis-project-finds-tokenization-could-make-cross-border-payments-faster-safer` — 34,810 chars
- `markets/…/crypto-ipos-could-create-massive-usd1-trillion-market-amid-tokenization-wave-jefferies-says` — 38,209 chars
- `markets/…/bitcoin-etf-accumulation-flattens-to-just-4-500-btc-year-to-date-as-may-flips-to-outflows` — 35,524 chars

**Regwall'd samples (23–26k chars, monthly-limit marker):**
- `business/…/block-kicks-off-cash-app-s-phased-stablecoin-roll-out-to-its-nearly-60-million-users` — 24,981 chars
- `opinion/…/a-bipartisan-bridge-to-the-future-why-the-senate-must-finish-the-job-on-digital-assets` — 25,202 chars
- `markets/…/robinhood-is-letting-ai-trade-for-you-so-you-don-t-have-to-keep-checking-the-markets` — 24,869 chars
- `business/…/dtcc-plans-to-bring-tokenized-assets-to-stellar-in-latest-wall-street-blockchain-push` — 25,096 chars
