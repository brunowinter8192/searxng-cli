# dev/news_pipeline/theblock/acquire_pipe/

## Role
Production-candidate acquire pipeline for theblock.co content. Fetches a defined
TARGET (set of URLs) through a rotating proxy pool using curl_cffi chrome
impersonation. Every request is a productive fetch — no separate proxy-check stage.
Does NOT import from `src/`; self-contained dev implementation.

## Design (LOCKED)

**Concurrent working-set + rotation loop.**
- Fires up to `concurrency` (proxy, URL) pairs concurrently (ThreadPoolExecutor).
- Working-set proxies (proven this session) fill slots first; remaining slots pull
  fresh candidates (socks4-first, then socks5, then http).
- **Success:** URL done + proxy stays in working set.
- **Fail (403 / dead / timeout):** URL back to queue (back) + proxy → 60min cooldown.
- **Uniform lifecycle:** candidate → working/drained → burned → 60min cooldown →
  eligible again. No permanent blacklist, no special-casing.
- **Gap:** working set empty AND no eligible candidates → return (done, gap), no spin-wait.
- `concurrency` is a CLI parameter (default 50); sign-off target is 128.

## Two chained targets
| Target | Input | Output |
|---|---|---|
| DEV-RUN (Stage 5 pending) | sitemap index → 64 sub-sitemap URLs | ~27k article `/post/` URLs |
| BACKFILL (later) | ~27k article URLs | article page content |

## Modules

### p1_fetch.py (41 LOC)
**Purpose:** curl_cffi chrome fetch primitive + XML/HTML content validators.
**Reads:** remote URLs via curl_cffi `Session(impersonate="chrome")`.
**Writes:** returns `(ok: bool, content: bytes)`.
**Called by:** `p3_target._fetch_index_via_proxy`, `p4_loop.run_loop`.
**Calls out:** `curl_cffi`.

---

### p2_cooldown.py (42 LOC)
**Purpose:** Per-run in-process cooldown state. Tracks burned proxies by monotonic
timestamp; provides socks4-first eligible candidate ordering.
**Reads:** `proxy_key()` from `proxy_status_log` (parent dir).
**Writes:** internal `_burned` dict (no file I/O — resets each run).
**Called by:** `p3_target._fetch_index_via_proxy`, `p4_loop.run_loop`.
**Calls out:** `proxy_status_log.proxy_key`.

---

### p3_target.py (68 LOC)
**Purpose:** Sitemap target builder. Fetches theblock index → parses 64 sub-sitemap
`<loc>` URLs. Direct httpx GET first; falls back to proxy rotation on non-XML response
(403, CF challenge, error).
**Reads:** `THEBLOCK_INDEX` via httpx (direct) or `p1_fetch.fetch_url` (proxy fallback).
**Writes:** returns `list[str]` of 64 sub-sitemap URLs.
**Called by:** `acquire_pipe.py` orchestrator (Stage 5, pending).
**Calls out:** `httpx`, `p1_fetch`, `p2_cooldown`, `curated_sources`.

---

### p4_loop.py (115 LOC)
**Purpose:** Core concurrent rotation loop. Runs `concurrency` (proxy, URL) pairs
per round; manages working set, cooldown hand-off, gap detection.
**Reads:** candidate pool + target URL list.
**Writes:** delegates all state to `AcquireLogger`; returns `(done, gap)`.
**Called by:** `acquire_pipe.py` orchestrator (Stage 5, pending).
**Calls out:** `p1_fetch`, `p2_cooldown`, `p5_logger`.

---

### p5_logger.py (162 LOC)
**Purpose:** Accumulates 5 logging surfaces; no I/O until `finalize()`.
**Reads:** events fed by `run_loop` via `record_attempt / record_burn / record_working_set`.
**Writes:** JSONL event log (`acquire_pipe_logs/`) + MD summary (`acquire_pipe_reports/`).
**Called by:** `p4_loop.run_loop`.
**Calls out:** `proxy_status_log.proxy_key`.

**5 surfaces:**
1. Fetch progress — URLs done/total + rate (URLs/min)
2. B-per-proxy distribution — requests-before-burn histogram
3. Working-set size over time — eligible candidate count per round
4. Failed attempts per successful fetch — churn ratio
5. Per-proxy event JSONL — `proxy_key`, `ts`, `url`, `result`, `proxy_success_count`

---

### acquire_pipe.py (PENDING — Stage 5)
**Purpose:** Orchestrator entry point. Wires `load_curated_proxies` → `build_sitemap_target`
→ `run_loop` → `logger.finalize`. CLI: `--concurrency` param.
**Status:** Not yet built.

---

## Status

| Stage | Module(s) | Commit | State |
|---|---|---|---|
| 1 | p1_fetch + p2_cooldown | 5804321 | ✓ built + signed off |
| 2 | p3_target (build_sitemap_target) | ce8679d | ✓ built + signed off |
| 3 | p5_logger | 390b55d | ✓ built + signed off |
| 4 | p4_loop (concurrent working-set) | bd1d763 | ✓ built; 64-sitemap testlauf PENDING |
| 5 | acquire_pipe.py orchestrator | — | PENDING next session |

**Stage 4 note:** The rework from sequential to concurrent (working-set + ThreadPoolExecutor)
was necessary — sequential 15s timeouts at ~1.5% CF-pass rate → multi-hour cold-start.
Concurrent model estimated ~2-3min cold-start at concurrency 128. Testlauf at 128 deferred
to next session together with Stage 5 orchestrator wiring.

## Gotchas
- Home IP is CF-blocked for direct theblock GETs (403) — p3_target proxy fallback handles this.
- Survey passers churn within ~1h (ephemeral proxies) — don't seed stale passers; rely on cold pool + concurrency.
- `concurrency` is the ONLY tunable for the cold-start speed vs router-saturation trade-off.
  128 is the planned sign-off value; clean zone for theblock GETs (heavier than icanhazip) TBD.
- Failed URLs go to the BACK of the queue (not front) to avoid hammering one URL with sequential dead proxies.
- `build_article_target` (Stage 2 extension) depends on `run_loop` — deferred to Stage 5.
