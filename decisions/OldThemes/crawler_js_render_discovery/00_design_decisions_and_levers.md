# crawler_js_render_discovery — Design Decisions & Lever Trade-offs

Framing doc for the topic. Empirical phase results live in `A_recall_probe.md` (Phase A) and `B_playwright_bfs_probe.md` (Phase B, pending). This file = the architectural decisions + the time↔completeness lever analysis + hard constraints + open questions, captured from the design discussion.

## Problem

`searxng-cli explore_site` on `https://docs.github.com/de/rest` finds only ~230 of ~305 real pages. The 305 is a deterministic gold standard derived from the `github/docs` `content/rest` repo tree (`dev/explore_pipeline/goldstandard/docs_github_rest.txt`). Repo-derivation is a one-off WORKAROUND — most doc sites have no backing repo. Goal: a discovery method that is **reliable cross-website**, not a per-site crutch.

## Investigation arc (numbers → `A_recall_probe.md`)

No sitemap on docs.github.com (`/sitemap.xml` → 404) → falls to prefetch BFS → SPA (Next.js) sidebar/category-link lists are client-rendered → `BFSDeepCrawlStrategy` extracts links via HTTP (proven: 0.18s/page = HTTP speed, not ~1s+ browser) → JS-rendered links never seen → ceiling ~67–75% recall, `agent-tasks/agent-tasks` never found. External convergence: crawl4ai issue #1665 ("BFSDeepCrawlStrategy ... captures page before JavaScript loads") + IR textbook (JS-generated links require browser JS execution).

## Decisions

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| D1 | Discovery method = **Playwright-per-page BFS** (single consistent method). Custom BFS: `crawler.arun(url)` per frontier URL (real browser render) → extract `result.links.internal` from rendered DOM → enqueue. | Correct-by-construction (sees links like a browser). Cross-website TRUST: future sites have no gold standard to verify completeness, so the method must be right by design, not tuned per-site. | Chosen. Phase B validates against 305. |
| D1b | REJECTED: cheap `delay_before_return_html` on existing `BFSDeepCrawlStrategy`. | BFS link-extraction is HTTP-structural (180ms proof) — delay affects content capture, not link discovery, so likely no effect. Even if it worked on GH, gives no cross-website trust. | Rejected in favor of D1. |
| D2 | REMOVE the sitemap cascade short-circuit. | The cascade trusts a sitemap that passes `SITEMAP_MIN_THRESHOLD` (5) and STOPS — an incomplete sitemap then silently swallows content. Documented shallow-sitemap cases: ReadTheDocs (root only), Cookiebot (homepage only). | Direction agreed. Sub-decision OPEN (D2a). Executes at src-port. |
| D2a | OPEN: drop sitemap ENTIRELY vs keep as ADDITIVE union (never short-circuit). | Additive union can only ADD URLs (never swallow) AND catches orphan pages a link-BFS can't reach → strictly ≥ completeness. Opus lean: additive union (max completeness). User lean: single-path simplicity (orphans rare on doc sites). | Undecided. Port-time. |
| D3 | Wait strategy = `wait_until="domcontentloaded"` + fixed `delay_before_return_html` + explicit `page_timeout`. **NO `networkidle`.** | `networkidle` is unbounded → waiting loops on telemetry/polling sites (own decisions/scrape_pipeline.md documents `domcontentloaded`-fallback rescuing networkidle-hangs). HARD user constraint: no waiting loops. | Fixed. |
| D4 | 429 policy = back-off ONCE, then STOP + report. No retry loops. | HARD user constraint: never enter waiting/retry loops. Incomplete-then-rerun (with stealth/cooldown) preferred over blind waiting. | Fixed. |
| D5 | Concurrency = **10** (user directive; probe default was sequential / ≤3). | User treats parallelism as a speed knob to max. Trade-off: 10 parallel = exactly the load that tripped the WAF; risk of 429-truncated run. | To apply next probe iteration. WAF behavior pending. |
| D6 | GH config (max_pages, depth, include-pattern, delay) = baseline defaults for future crawls. | One validated baseline, tune per saturation signal (D7). | Agreed. |
| D7 | Add a **saturation/stop-reason message** to probe + eventual prod output. | Cross-website "did we get everything?" answer: report WHY discovery stopped. | To add next probe iteration. |

## Lever trade-offs (within Playwright-per-page BFS)

| Lever | Trades | Current | Notes |
|-------|--------|---------|-------|
| `delay_before_return_html` | **time ↔ completeness (the real dial)** | 3.0s | +X sec EVERY page. ~3s sweet spot (#1665: 0s partial, 3s full, 5s/20s no gain). With no networkidle, this is the ONLY guard for slow-rendering pages — a page rendering links after the delay is missed → raise delay for slower sites. |
| `page_timeout` | worst-case load bound | 15s (15000ms) | Ceiling for the LOAD phase (nav→domcontentloaded), NOT the render wait. On healthy pages (load <1s) it never fires. Distinct clock from delay — see Parameter semantics below. |
| concurrency | **wall-clock ↔ WAF/429 risk** | →10 (was 1) | Indirect completeness hit: pages lost to 429 = missing pages. Pure speed-vs-rate-limit otherwise. |
| `max_pages` | completeness ceiling | 400 | Set > true site size so it never truncates. If hit → more pages likely exist (D7 signal). |
| `max_depth` | completeness reach | 10 | Generous; with focused include-pattern rarely binds. |
| include/exclude pattern | scope (precision + time) | `/de/rest/` | Tighter = faster + less noise, but too tight excludes legit pages. Only scope lever that also saves time. |
| stealth (`enable_stealth` + `UndetectedAdapter`) | 429-avoidance ↔ overhead/fragility | off | Mirrors Phase-2 in `src/scraper/scrape_url.py`. Toggle to dodge Cloudflare WAF. UndetectedAdapter has known fingerprint weaknesses + site-incompat risk. |

**Summary:** `delay` is the one genuine time↔completeness dial. `max_pages`/`depth`/pattern are ceiling/scope (set generous → don't truncate). concurrency + stealth are speed-vs-WAF (touch completeness only via avoided 429s).

## Parameter semantics — `delay` (3s) vs `page_timeout` (15s)

Two different clocks, two phases — NOT contradictory:
- `page_timeout=15s` = max time for the page to LOAD (navigation → `domcontentloaded`). Bites only on a pathologically slow/stuck page; then abort instead of hanging.
- `delay_before_return_html=3s` = fixed wait AFTER load completes, before grabbing HTML, to let JS render.
- Healthy page timeline: nav → domcontentloaded (~0.3s) → +3s delay → capture ≈ 3.3s total. The 15s never engages. "Between 3s and 15s" nothing happens on a normal page — that window only exists for a still-loading stuck page.

## WAF / 429 context

docs.github.com sits behind Cloudflare. WAF returns 429 on parallel HTTP load (`prefetch=True` made parallel requests → 429 after ~100 reqs/session in Phase A; sequential survived). Browser-render + low concurrency is gentler. Stealth (`enable_stealth=True` + `UndetectedAdapter` + `AsyncPlaywrightCrawlerStrategy`) exists in `src/scraper/scrape_url.py` (Phase-2 scrape fallback) but the crawler (`src/crawler/crawl_site.py`) does NOT use it — available as the D5 toggle.

Single-page scrape of a docs.github.com page already verified clean (no 429, real content) post plugin-routing-unblock — see `decisions/plugin_routing.md`. So per-page SCRAPING is solved; the open problem is purely URL DISCOVERY completeness. Scrape phase shares only the volume-429 concern, not the completeness one.

## Saturation message (D7) — spec

End-of-crawl stop-reason, so a user can decide crawl-further vs stop on sites without a gold standard:
- `frontier exhausted at N pages (max_pages=400 not hit, max depth reached D < 10)` → everything reachable found; raising limits won't help.
- `hit max_pages=400 (K URLs still queued)` → capped; more pages likely exist → raise + rerun.
- `hit max_depth=10 at frontier edge` → depth-capped → raise depth.

## Open questions / pending

- Phase B result: does Playwright-per-page BFS reach ~100% recall + find `agent-tasks/agent-tasks`? (single-page check already confirmed the link IS in the rendered DOM). → `B_playwright_bfs_probe.md`.
- concurrency=10 (D5): does the WAF 429 it? stealth needed?
- D2a: drop sitemap entirely vs additive union — port-time decision.
- chroma_docs Strategy-C outlier (1.09s/page) from Phase A: does `prefetch=False + networkidle` trigger Playwright on some JS-heavy sites where HTTP returns minimal content? Unverified; if true, a simpler fix than custom BFS might exist for SOME sites — but not cross-website-reliable.
- src-port: only after Phase B confirms recall. `decisions/explore01_discovery.md` IST/SOLL updated at port time, not before.

## Cross-refs

- `A_recall_probe.md` — Phase A empirical (3-strategy recall, HTTP-finding, regression).
- `B_playwright_bfs_probe.md` — Phase B empirical (pending).
- `decisions/explore01_discovery.md` — current production discovery IST (sitemap→prefetch cascade); src-port target.
- `decisions/plugin_routing.md` — plugin-routing blocking removal (this session; enabled scraping docs.github.com at all).
- `dev/explore_pipeline/04_render_recall.py` (Phase A probe), `05_playwright_bfs.py` (Phase B, pending).
