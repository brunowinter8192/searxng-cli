# 61 — CoinDesk backfill: browser proxy-riding engine (IP rotation against the regwall)

Process doc for the CoinDesk 61k article-body backfill. Discovery is done (OT47, timeline API → inventory
`data/news/coindesk/inventory/coindesk_{year}.txt`, 61,628 URLs). The blocker is the **scrape**: CoinDesk's
regwall is IP-rate metered, so a single-IP browser scrape (current prod `src/news/engine/scrape.py`) cannot
finish the corpus — the IP goes "hot". This theme builds the IP-rotating backfill engine. All work lives in
`dev/news_pipeline/coindesk_proxy_riding/`; `src/` is UNCHANGED.

## Premise (user-decided, fixed)

- Keep the **crawl4ai browser** fetcher (CoinDesk's body is JS-rendered; The-Block-style curl_cffi was
  rejected as the 17h path — though see Open Questions, the 137h result undercuts that premise).
- Defeat the regwall by **riding proxies**: a proxy rides URLs; **fresh cookie context per URL on the same
  IP** (keeps OT03 cookie-fix, so the only regwall signal is IP-rate); burn the proxy at a cumulative
  regwall threshold (default 2) → rotate IP.
- Regwall detection on `result.markdown.raw_markdown` (visible text), NOT `result.html` (the regwall marker
  `"Create a FREE account…"` is a hidden React component present on EVERY page's raw HTML). Store full
  `result.html` (lossless). No cleanup this session — raw corpus only; cleanup built later on the full corpus.
- **Only termination criterion = global 60-min stall** (no progress → remaining URLs to failure log). No
  per-URL give-up (see Abort-criteria fix).

## Iteration 1 — per-browser-process + curl_cffi alive-feeder

Architecture: a 128-wide curl_cffi alive-feeder pre-validates raw pool proxies (reachable+200 on a CoinDesk
page) and feeds http/socks5 ones to N browser slots; each slot = a fresh `AsyncWebCrawler` PER PROXY with
`BrowserConfig(proxy_config=…)` (proxy at browser-launch = one Chrome PROCESS per proxy).

### 500-run (concurrency 20), `data/news/coindesk/riding_test_500/job.md`

| Metric | Value |
|---|---|
| OK / target | 499 / 500 (1 fail = a Spanish-locale 403) |
| Regwall | 11 (2.2%), ALL recovered on a fresh IP via requeue |
| Connect-fail fetches | 704 |
| Proxies burned | 727 (only 95 produced ≥1 ok) |
| Ride length (URLs/proxy) | mean 1.7, median 1, min 0, max 63 |
| Wall / throughput | 4032s (67min) → **61k projection ≈ 137h** |
| HTML p50 / markdown p50 | 501 KB / 17,168 chars (full bodies, no truncation) |

Feeder smoke: pool 26,540; ~141 browser-eligible proxies/min, 28.4% alive — feeder over-supplies the slots
~13×, slots never proxy-starved.

**Findings:** (a) Premise validated — regwall is a non-issue (11/500, all recovered); good proxies ride long
(max 63). (b) Throughput is killed by **connect-fail churn**, NOT the browser render: a clean fetch is ~7s, so
all-good proxies → ~6h for 61k. The 137h is ~95% wasted slot-time on junk proxies (each junk = full Chrome
launch ~2-3s + 12s page_timeout + teardown). Median ride 1 = half the proxies die after ≤1 URL. (c) The
bottleneck is the per-proxy browser cost, not proxy supply.

## Iteration 2 — per-context proxy redesign (the crawl4ai finding)

Source read of `crawl4ai/browser_manager.py`:
- `BrowserConfig.proxy_config` → browser LAUNCH args (`browser_args["proxy"]`, ~line 1137) = one Chrome
  process per proxy (Iteration 1, expensive).
- `CrawlerRunConfig.proxy_config` → `context_settings["proxy"]` (lines 1334-1341) via `self.browser.new_context()`
  = per-CONTEXT, inside the existing browser process. `_make_config_signature` includes `proxy_config`
  (lines 1401-1409) → one context per distinct proxy, all in ONE browser. `arun()` concurrent-safe across
  riders (contexts_by_config under `_contexts_lock`).

Redesign (`p2_browser_rider.py`): ONE shared `AsyncWebCrawler` (no browser-level proxy) + N rider tasks;
per URL `arun(CrawlerRunConfig(session_id=uuid, proxy_config=ProxyConfig(server=…), page_timeout=8000…))` →
fresh context+cookies+proxy, then `kill_session`. Riders draw RAW proxies directly from the pool (alive-feeder
`p1` DELETED — see Alive-check decision). Proxy switch = `new_context` (~50-100ms) instead of Chrome launch
(~2-3s).

### Findings — two walls hit

- **RAM not free:** Chromium spawns a separate RENDERER PROCESS per context. The 128 attempt showed 135
  renderer processes (+ ~6 gpu/utility) in ONE browser instance. Shared GPU/network/main process saves some
  overhead vs N full browsers, but RAM still scales with concurrency (~17 GB est. at 128). The "one light
  browser" RAM hope is only partly real.
- **128 contexts in one browser DEADLOCKS:** the 128-concurrency / 150-URL smoke hung 12+ min, `arun()`
  never returned for any slot, zero crawl activity. A single browser process cannot coordinate 128
  simultaneous contexts/navigations. **20 works** (12 chrome processes = one tree, ok-scrapes flow).
  → High concurrency needs a POOL of browser PROCESSES (B browsers × C contexts), not one browser × 128.

### Alive-check decision (dropped)

Under per-context, a junk context is nearly as cheap as a curl thread (same ~12s/8s timeout, light cookie-jar
+ CDP target, ~100-200ms create/close). The pre-check's "protect expensive slots" rationale (valid for 20-40
RAM-heavy processes) collapses; it also COSTS one CoinDesk regwall-budget request per proxy. So the
alive-feeder was removed — raw proxies straight to contexts, high concurrency absorbs junk. Cost of dropping
it = more CHURN per URL (connect-fails before a good proxy), NOT lost URLs (completeness is a requeue/retry
question, orthogonal). The only residual pro-filter argument left is the single-browser CPU bottleneck — moot
once we go multi-browser-pool.

## Fixes landed this session

- **socks4 filter** (`run_coindesk_riding.py`, `7935ec6`): raw pool 26,492 → 20,794 browser-eligible after
  `BROWSER_ELIGIBLE_PROTOS = {"http","socks5"}` (~22% was socks4, which Playwright cannot drive → instant
  connect-fail). The deleted alive-feeder used to do this proto-filter; restored at pool-load.
- **Abort-criteria removal** (`p2_browser_rider.py`, `09480d2`): the worker had invented two per-URL give-up
  criteria that were never agreed — `MAX_URL_RETRIES=3` (regwall gives up after 3) and 403/empty → immediate
  terminal `n_failed`. Both removed. ALL non-ok outcomes (regwall, connect_fail, 403/empty) now requeue
  unbounded; `last_progress_mono` stamps only on `ok`; the 60-min global stall is the sole terminator. (The
  20-smoke's 27 "failures" were ALL 403 anti-bot marked terminal — a 403 is IP-specific, succeeds on a fresh
  IP, so terminal-fail was wrong.)

## Current dev state

`dev/news_pipeline/coindesk_proxy_riding/` on `dev`: `p0_pool` (pool + cooldown, The-Block-copied),
`p2_browser_rider` (shared browser, per-context proxy, raw pool cursor, requeue-all), `p3_url_sampler`
(proportional 500 across years), `p4_reporter` (job.md + 3 plots), `run_coindesk_riding` (CLI:
`--concurrency --burn-threshold --n-urls --page-timeout --output-dir`; raises RLIMIT_NOFILE to 16384 at
startup; http/socks5 filter; empty-pool guard). `p1_alive_feeder` deleted. Validated at concurrency 20;
128 deadlocks. `src/` untouched.

## Open questions (next session — research FIRST, then decide)

1. **Contexts-per-browser limit** — research before coding. Sources, by authority: Chromium renderer-process
   cap (`GetMaxRendererProcessCount` in `render_process_host_impl.cc`; historically ~80 desktop, RAM-scaled —
   likely the deadlock root); Playwright GitHub issues + docs (known "many concurrent contexts hang" + the
   "use multiple browser instances for parallelism" guidance); crawl4ai docs/issues (`arun_many`,
   `MemoryAdaptiveDispatcher`, max sessions); SO/Reddit for practical contexts-per-browser numbers. Goal: the
   safe C between our measured 20 (works) and 128 (hangs).
2. **Multi-browser pool** — B browser processes × C contexts each = total concurrency, sidestepping the
   single-browser deadlock + spreading CPU/crash-radius. Depends on (1).
3. **curl_cffi body question (still untested)** — the 137h browser result contradicts the premise that the
   browser is faster than curl_cffi (The Block: 22k/17h). IF curl_cffi gets CoinDesk's article body, it would
   sidestep the entire browser thicket (deadlock, renderer-RAM, junk-churn) AND the regwall (rotation solves
   it). A ~10-min probe settles it. User has repeatedly chosen the browser path; flagged for honesty.
