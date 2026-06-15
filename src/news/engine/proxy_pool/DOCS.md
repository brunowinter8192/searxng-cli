# src/news/engine/proxy_pool/

## Role

Generic proxy-rotation scrape engine. Called by `pipeline.py` via `scrape_entries_proxy()` when
`platform.scrape_engine == "proxy_pool"`. Manages a rotating pool of HTTP/SOCKS4/SOCKS5 proxies
with sustained concurrent fetching via curl_cffi chrome impersonation, 60-min pool refresh,
2-strikes lifecycle, per-job lock, and audit trail.

No platform-specific logic lives here — target URLs, content type, and pool provider are all
caller-supplied. Touch this package when changing rotation mechanics, pool loader sources, or
the job lifecycle (lock, janitor). Do NOT touch when adding a browser-engine platform.

## Public Interface

`__init__.py` is empty — callers import modules directly.

- `scrape_entries_proxy(entries, output_dir, proxy_cfg)` in `scrape.py` — sole entry point for `pipeline.py`.
- `load_backfill_pool()` in `pool_loaders.py` — used by platform `ProxyScrapeConfig.pool_provider`.

## Flow

1. `scrape_entries_proxy` acquires `box_lock`, instantiates `Janitor` + `PersistentCooldownManager` + `AcquireLogger`.
2. `run_loop` sustains concurrent rotation: `pool_provider()` → `build_active_buffer` → batches of `(proxy, URL)` → `fetch_url` via `ThreadPoolExecutor`.
3. Per ok fetch: `content_handler` decodes bytes → writes `output_dir/{hash}.md`.
4. `logger` streams events to JSONL; `janitor.end_job` derives `job.md` + `cumulative_hits.png`.
5. `_build_manifest` maps `(done, dead, gap)` → `[{url, hash, status, file, char_count, error}]` matching the browser engine manifest contract.

## Modules

### scrape.py (106 LOC)

**Purpose:** Proxy-pool scrape entry point — wires `run_loop`, `box_lock`, `Janitor`, `AcquireLogger` into the pipeline manifest contract.
**Reads:** `entries` list (in-memory) + `proxy_cfg.pool_provider()`.
**Writes:** `output_dir/{url_hash}.md` per ok fetch.
**Called by:** `pipeline.py:run_pipeline`.
**Calls out:** `loop.py`, `cooldown.py`, `logger.py`, `janitor.py`, `box_lock.py`.

---

### loop.py (201 LOC)

**Purpose:** Sustained concurrent rotation loop — 60-min pool refresh, 2-strikes lifecycle, tail-race, wait-on-exhaustion.
**Reads:** `pool_provider()` callback + target URL list (in-memory).
**Writes:** delegates state to `AcquireLogger` + `PersistentCooldownManager`; calls `content_handler` per ok fetch. Returns `(done, dead, gap)`.
**Called by:** `scrape.py:scrape_entries_proxy`.
**Calls out:** `fetch.py`, `cooldown.py`, `logger.py`, `buffer.py`.

Key: `_sleep = time.sleep` is a module-level alias — patch it in tests, not `time.sleep`.

---

### fetch.py (46 LOC)

**Purpose:** curl_cffi chrome-impersonating HTTP fetch primitive + content-type gate (`"html"` | `"xml"`).
**Reads:** remote URL via curl_cffi Session (routed through proxy).
**Writes:** nothing — returns `(status, content)` where `status ∈ {"ok", "dead", "fail"}`.
**Called by:** `loop.py:run_loop`.
**Calls out:** `curl_cffi`.

---

### cooldown.py (47 LOC)

**Purpose:** In-memory per-job cooldown tracking — clean slate per instantiation, 60-min burn window.
**Reads:** nothing (in-memory only).
**Writes:** nothing.
**Called by:** `buffer.py`, `loop.py`, `scrape.py`.
**Calls out:** `proxy_key.py:proxy_key`.

---

### buffer.py (45 LOC)

**Purpose:** Active-buffer helpers — `build_active_buffer`, `refill_buffer`; holds `BUFFER_SIZE = 1280`, `DEFAULT_CONCURRENCY = 128`.
**Reads:** proxy pool + `PersistentCooldownManager` eligibility (in-memory).
**Writes:** returns new buffer lists (pure — no mutation of inputs).
**Called by:** `loop.py:run_loop`.
**Calls out:** `cooldown.py:PersistentCooldownManager`.

---

### logger.py (45 LOC)

**Purpose:** Streams per-fetch events to JSONL (line-buffered, kill-safe). Stats derived by `janitor.end_job`.
**Reads:** events pushed by `run_loop` via `record_attempt` / `record_pool_refresh`.
**Writes:** `{platform_dir}/proxy_pool_logs/acquire_events_{ts}.jsonl` (streamed, line-buffered).
**Called by:** `scrape.py`, `loop.py`.
**Calls out:** `proxy_key.py:proxy_key`.

---

### janitor.py (164 LOC)

**Purpose:** Job lifecycle — `Janitor(jobs_dir, log_dir, report_dir)`; wipes transient dirs at start; reads JSONL → `job.md` + `cumulative_hits.png` at end.
**Reads:** JSONL at `jsonl_path` passed to `end_job`.
**Writes:** `{jobs_dir}/{job_id}/job.md`, `cumulative_hits.png`; wipes `log_dir` + `report_dir` at start and end.
**Called by:** `scrape.py:scrape_entries_proxy`.
**Calls out:** `matplotlib.pyplot` (lazy import in `_write_plot`), `statistics` (stdlib).

---

### box_lock.py (102 LOC)

**Purpose:** System-wide single-job flock — `acquire(job, target, lock_name="proxy_pool")`; crash-safe (kernel releases flock on process death). Raises `LockBusyError` on contention.
**Reads:** `~/.searxng-cli-locks/{lock_name}.lock` sidecar (in `cleanup_stale` + busy message).
**Writes:** `~/.searxng-cli-locks/{lock_name}.{flock,lock}`.
**Called by:** `scrape.py:scrape_entries_proxy`.
**Calls out:** `fcntl`, `os` (stdlib).

---

### proxy_key.py (16 LOC)

**Purpose:** Canonical proxy key — `proxy_key(proto, host_port) → "proto://host:port"` (auth stripped if present).
**Reads:** nothing.
**Writes:** nothing (pure).
**Called by:** `cooldown.py`, `logger.py`, `pool_loaders.py`.
**Calls out:** stdlib only.

---

### pool_loaders.py (259 LOC)

**Purpose:** 13 Top-Repo proxy loaders + `load_backfill_pool()` (combines all → ~22k unique `[(protocol, host:port)]`).
**Reads:** 13 GitHub raw proxy-list URLs via httpx.
**Writes:** nothing.
**Called by:** platform `ProxyScrapeConfig.pool_provider` (Stage B — not yet called from `src/`).
**Calls out:** `httpx`, `monosans_loader.py:load_monosans_proxies`, `proxy_key.py:proxy_key`.

---

### monosans_loader.py (36 LOC)

**Purpose:** Fetch monosans/proxy-list JSON; return `[(protocol, host:port)]` in source order.
**Reads:** monosans GitHub raw JSON URL via httpx.
**Writes:** nothing.
**Called by:** `pool_loaders.py:load_backfill_pool`.
**Calls out:** `httpx`.

## Gotchas

- `pool_loaders.py` at 259 LOC exceeds the 200-LOC heuristic — no extractable concern exists (flat list of 13 loader functions sharing one `_merge_dedup` utility). Do not split.
- `janitor.end_job` calls `jsonl_path.unlink()` then wipes `log_dir`. Interrupt between these two orphans the JSONL in `log_dir`. Non-critical: `start_job` wipes `log_dir` at the next run.
- `box_lock`: SIGTERM kills Python before `finally` runs → sidecar stays; kernel releases flock. Next `acquire()` recovers via `cleanup_stale()` (dead-PID detection).
- `_sleep` in `loop.py` is a module alias (`_sleep = time.sleep`) — patch this alias in tests, not `time.sleep` directly.
