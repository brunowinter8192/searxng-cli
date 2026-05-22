# Rate Limiter — Fail-Fast Policy

## Status Quo (IST)

`src/search/rate_limiter.py` (52 LOC) implements `RateLimiter` as a **pure token-bucket**. Exponential backoff removed 2026-05-22 (this branch).

**Token-bucket pacing:** sliding window `MAX_REQUESTS=10` per `WINDOW_SECONDS=60.0`. Per-engine singletons configured at module import time (e.g. `google.py` sets `max_requests=4, window_seconds=60`). `acquire()` waits for the oldest token to expire if the window is at capacity — normal rate management, not retry-after-failure.

`acquire()` has one code path: remove expired tokens → if at capacity wait for oldest to expire → append new token. No `_backoff_until` check, no sleep-on-failure. `RateLimiter` has no failure state: `_tokens` (sliding window timestamps), `_lock`, `_max_requests`, `_window_seconds` only.

**Fail-fast on CAPTCHA/429/Block:** engine detects failure → returns `([], S.EMPTY_BLOCK)` or analogous status immediately → `_engine_with_timing` in `search_web.py` records it in `engine_stats` → query log captures it. No retry, no session-scoped memory of the failure. Next query tries the engine again from scratch.

**RATE_SKIP still active:** `asyncio.wait_for(get_limiter(engine.name).acquire(), timeout=RATE_WAIT_TIMEOUT=60s)` in `search_web.py` fires if token-bucket wait exceeds 60s. Under normal 4 req/min load this is dormant; it guards against genuine bucket saturation (unlikely) and asyncio event-loop starvation during Chrome CDP floods (bee_fix mechanism).

Removed from all 10 engine files: every `limiter.backoff()`, `limiter.reset_backoff()`, orphan `limiter = get_limiter(self.name)` assignments, and `get_limiter` imports where no longer used.

## Evidenz

**Pre-rip — backoff waste (2026-05-22, `value_eval_probe.py` 16-pair batch):**

| Pair | CAPTCHA event | Backoff applied | Google result |
|------|---------------|-----------------|---------------|
| 1 | yes | 34s (attempt 0: 30 + 4 jitter) | google=0 |
| 2 | yes | 65s (attempt 1: 60 + 5 jitter) | google=0 |
| 3 | (waited 60s = RATE_WAIT_TIMEOUT) | — | google=0 |
| 4 | yes | 123s (attempt 2: 120 + 3 jitter) | google=0 |
| 5–7 | (waited 60s each) | — | google=0 |
| 7 | yes | 244s (attempt 3: 240 + 4 jitter) | google=0 |
| 8-16 | (all waited 60s) | — | google=0 |

Net waste ≈466s; net benefit zero — Google's bot-detection state does not decay in seconds. Source: `decisions/OldThemes/pooling/04_zero_query_diagnosis.md` (cascade mechanism diagnosis, 2026-05-20).

**Post-rip — pipeline smoke baseline (2026-05-22, `11_pipeline_smoke.py`, 30 queries):**

*Evidenz block — to be filled after Phase C smoke run completes. Placeholder: see report at `dev/search_pipeline/01_reports/no_backoff_baseline_<ts>.md`.*

## Recommendation (SOLL)

**Keep — current state matches the `no_backoff_retry` project principle.**

Token-bucket pacing + fail-fast is the correct architecture. No further changes needed to the rate-limiter or engine backoff paths.

## Offene Fragen

- **Should we add an explicit "engine-failed-this-query" status that propagates to the query log?** Currently `EMPTY_BLOCK` is the umbrella reason. A separate `BLOCKED_CAPTCHA` / `BLOCKED_429` would help debugging without re-introducing retry logic. Not blocking the cleanup itself; can follow in a subsequent commit.
- **Should the cross-encoder service (port 8082) and other downstream HTTP services follow the same fail-fast policy?** Yes — the project-wide principle in `decisions/OldThemes/no_backoff_retry.md` applies to every external service call. Concrete change to RAG-server-call paths in `search_web.py` / `preview.py` if any retry-with-backoff has crept in.

## Quellen

- Diagnosed failure mode + formula derivation: `decisions/OldThemes/pooling/04_zero_query_diagnosis.md`
- Reproduced in value-eval: `decisions/OldThemes/pooling/07_value_eval.md` (Caveats section, Google CAPTCHA)
- Probe-run evidence: `/tmp/value_eval_probe_run.log`
- Project-wide principle: `decisions/OldThemes/no_backoff_retry.md`
