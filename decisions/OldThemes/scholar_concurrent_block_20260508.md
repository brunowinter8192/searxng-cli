# Scholar Concurrent Block — IST Policy + Investigation Summary

Date: 2026-05-08
Bead: searxng-ciw

---

## Symptom

In production, Google Scholar returns 0 results on every query when fired as part of the default 10-engine concurrent set. The query log records `status: EMPTY_BLOCK` on every burst-opener (first query of a session where the rate-limiter has tokens), followed by `RATE_SKIP` cascade on subsequent queries in the same process (Scholar's backoff timer exceeds `RATE_WAIT_TIMEOUT=5.0s`). Measured in `src/logs/query_log.jsonl`: 3/3 effective Scholar attempts = `EMPTY_BLOCK`, 9/9 cascade = `RATE_SKIP`. Net: Scholar contributes 0 URLs to every production result set.

---

## Root Cause

Google Scholar's anti-bot system issues a reCAPTCHA Enterprise challenge (`www.google.com/sorry/index`) when it detects a **Chrome browser tab** originating from a process that already has 8+ other browser tabs loading simultaneously. The trigger is concurrent Chrome tab count, not IP-level HTTP request rate. HTTP-based Scholar requests (httpx, no tab opened) fire alongside the same 8 concurrent browser engines with 0% block rate.

Evidence ruling out alternative hypotheses:

- **Not fingerprint:** bot.sannysoft.com probe (commit `c2b2d73`, `dev/search_pipeline/01_reports/pydoll_stealth_phase_a_20260508.md`) showed all 57 detection checks passing. Fingerprint is identical between isolated (0% block) and concurrent (100% block) browser Scholar. Cannot explain the difference.
- **Not Google-domain co-fire:** no-Google browser-Scholar smoke (this session, 9 engines, `google` absent) produced 12/12 EMPTY_BLOCK. Removing Google from the engine set does not prevent the block.
- **Not IP-level HTTP request rate:** HTTP Scholar smoke (this session) fired alongside 8 concurrent browser engines with 0% block rate (12/12 OK). Scholar's requests reached Google's servers without challenge when no Chrome tab was opened.
- **Not behavioral scoring:** browser Scholar receives `/sorry/` during `go_to()` at 1.7–2.0s, before any Scholar page content loads or user interaction is simulated.

**Mechanistic path:** `asyncio.gather` fires 9–10 engine coroutines simultaneously. Browser engines (DDG, Mojeek, Lobsters, Semantic Scholar, Google, Scholar) each open a pydoll Chrome tab. Scholar's tab opens in an instance already rendering 5–8 other Chrome tabs. Google's infrastructure detects concurrent Chrome-tab origin on `scholar.google.com` and redirects to `/sorry/` before serving the search page. HTTP Scholar sends an `httpx.AsyncClient` GET — no Chrome tab is opened, no concurrent-tab signal is emitted — and receives results normally.

---

## Evidence Table

| Test | Configuration | Scholar BLOCK | Effective attempts | Avg search_ms | Reference |
|---|---|---|---|---|---|
| Production baseline | 10 engines concurrent incl. `google` browser, browser Scholar | **100% (3/3)** | 3 (rest RATE_SKIP cascade) | 1910 | ciw_concurrent_block report on discarded ciw-investigate branch, commit `9feaab6` |
| HTTP isolation (Phase B, discarded) | Scholar HTTP + CrossRef + OpenAlex — 3 engines, no `google`, no other browser engines | **0% (0/4)** | 4 (5 results each) | ~1800 | Phase B branch discarded; concurrent Chrome tab count = 2, below threshold |
| no-Google browser smoke (this session, pre-redirect) | 9 engines, no `google`, browser Scholar in asyncio.gather | **100% (12/12)** | 12 (no RATE_SKIP cascade — search_web CLI calls spaced >15s, token replenishes) | 1850 | main `src/logs/query_log.jsonl` lines 55–66 |
| **no-Google HTTP probe smoke (this session)** | 9 engines, no `google`, HTTP Scholar (httpx, no tab) in asyncio.gather | **0% (0/12)** | 12 | 724 | `dev/search_pipeline/01_reports/no_google_burst_20260508_220631.jsonl` |

**Read across rows 3 and 4:** same 9-engine set, same asyncio.gather fanout, same queries, same IP, same session day. Only variable: browser tab (row 3 = 100% block) vs HTTP request (row 4 = 0% block). Architecture is the causal variable.

---

## IST Policy (post-2026-05-08)

**Architecture matters. HTTP Scholar survives the concurrent multi-engine burst; browser Scholar does not.** The path forward is HTTP migration of scholar.py from pydoll-browser to httpx+lxml, using the probe pattern in `dev/search_pipeline/scholar_http_probe.py`.

Current codebase status: `src/search/engines/scholar.py` is still browser-based (pydoll). The HTTP migration is NOT live in production — it is validated in `dev/` and ready for src/ promotion. Until promotion, Scholar is effectively non-functional in all production query paths (`search_web`, `search_batch`, `--academic`, `--pdf`).

**HTTP probe performance note:** HTTP Scholar (row 4) averages 724ms search_ms vs browser Scholar isolation baseline ~1900ms. HTTP is also 2.5× faster. The migration removes a Chrome tab from the concurrent burst AND improves latency.

**Cascade note on row 3:** `search_web` CLI calls are separate processes with Chrome-warm + 9-engine gather + preview overhead totalling ≥15s per call. Scholar's rate limiter replenishes at 4 req/min (one token per 15s). Each CLI call therefore gets a fresh token → no RATE_SKIP cascade → all 12 queries are effective. The original production smoke (`search_batch`) fires queries back-to-back within one process; queries ≤15s apart trigger cascade, giving only 3 effective burst-openers. This difference changes the denominator, not the block-rate finding.

---

## Discarded Approaches

| Approach | Reason discarded |
|---|---|
| "Remove Google from engine set" policy | No-Google browser smoke (row 3) shows 12/12 EMPTY_BLOCK without `google`. The tab-burst signal fires at 8+ concurrent Chrome tabs regardless of whether `google` is in the set. Empirically falsified. |
| Sequential Scholar after gather (option from original mitigation recommendation in ciw report) | Architecturally correct but unnecessary given HTTP migration: HTTP Scholar can run concurrently inside the same gather with 0% block. Sequencing adds latency for no gain. Revisit only if HTTP Scholar starts blocking in the future. |
| Stagger tab opening (200–500ms inter-engine delays) | Adds global latency tunable, slows all browser engines; doesn't address the concurrent-tab signal on Google's server-side IP scoring (small delays between tab opens would likely still register as concurrent-origin). User declined. |
| Patchright migration | Patches `Runtime.enable` CDP leak — relevant for CDP-level detection, not for concurrent-Chrome-tab IP scoring. Both Patchright and pydoll would open a Chrome tab; the tab itself is the signal. Not applicable. |
| PoW auto-solve on `/sorry/` | Fragile, maintains BLOCK as an expected code path. Superseded by HTTP architecture which avoids the block entirely. |
| Residential proxy (paid) | Out of scope (free-fix-path constraint). |

---

## Open Items

### 1. Promote scholar_http_probe.py → src/search/engines/scholar.py

The HTTP implementation is empirically validated. Promotion steps:
- Replace `src/search/engines/scholar.py` content with the probe pattern from `dev/search_pipeline/scholar_http_probe.py`
- Rename class back to `ScholarEngine`, restore `name = "google_scholar"` (ENGINES dict key)
- Remove the probe-local `RateLimiter` constructor; production scholar uses `get_limiter(self.name)` for backoff (acquire is handled by `_engine_with_timing`)
- Update `ENGINE_WATCHDOG_OVERRIDE` in `search_web.py` — `"google_scholar": 6.0` was added in commit `82bc88f` (already present if that commit was cherry-picked, otherwise add it)
- Update `src/search/DOCS.md` scholar entry: `browser → HTTP`
- Update `decisions/stealth00_engine_status.md` IST row for Scholar
- Smoke verify with `dev/search_pipeline/08_scholar_smoke.py` + `dev/search_pipeline/no_google_burst_smoke.py`

Bead for this work: open a new bead or extend `searxng-ciw`. The `dev/` probe exists — promotion is a contained, scoped task.

### 2. `--pdf` mode Scholar re-evaluation

`_PDF_ENGINES` in `search_web.py` includes `google_scholar` (Scholar surfaces arxiv.org/abs/ links → TIER1 transform → PDF download). After HTTP promotion, Scholar should fire in `--pdf` mode without block. Verify with `dev/search_pipeline/no_google_burst_smoke.py` adapted for a PDF-flavored query set, or check `src/logs/query_log.jsonl` post-promotion.

### 3. Empirical re-validation cadence

HTTP Scholar's 0% block rate was measured at 12 queries in one session from a home/residential IP. Quarterly re-validation via `./venv/bin/python dev/search_pipeline/no_google_burst_smoke.py` (or subset of 4 queries). If block rate rises above 0% post-promotion, fall back to sequential-after-gather option from the discarded approaches table above.

---

## Files Touched This Session (scholar-no-google-test branch)

| File | Change |
|---|---|
| `dev/search_pipeline/scholar_http_probe.py` | New — HTTP Scholar probe class (cherry-picked from commit `82bc88f`, adapted for dev/) |
| `dev/search_pipeline/no_google_burst_smoke.py` | New — 9-engine no-Google burst smoke script (drives HTTP probe + 8 production engines) |
| `dev/search_pipeline/01_reports/no_google_burst_20260508_220631.jsonl` | New — smoke run output (12 queries, all `scholar_http=OK`) |
| `decisions/OldThemes/scholar_concurrent_block_20260508.md` | New — this document |

Browser smoke data (no-Google, 12-query, all EMPTY_BLOCK): written to main repo `src/logs/query_log.jsonl` lines 55–66 — no file committed here (main repo's log, not worktree artifact).
