# Rate Limiter — Fail-Fast Policy

## Status Quo (IST)

`src/search/rate_limiter.py` (69 LOC) implements `RateLimiter` with two distinct behaviors:

**1. Token-bucket pacing (lines 39-51):** sliding window `MAX_REQUESTS=10` per `WINDOW_SECONDS=60.0`. Engine-individual instances override with their own caps (e.g. `google.py:65` uses `max_requests=4, window_seconds=60`). `acquire()` waits for the oldest token to expire if the window is at capacity. This is **normal rate management** — pacing to avoid hitting provider limits — and stays.

**2. Exponential backoff after 429/CAPTCHA (lines 53-58):** `RateLimiter.backoff()` sets `_backoff_until = now + delay` where `delay = BACKOFF_BASE × 2^_backoff_attempt + random.uniform(1.0, 10.0)`. `BACKOFF_BASE = 30.0`, so first failure waits 31-40s, second 61-70s, third 121-130s, fourth 241-250s. The counter is per-engine, persistent across queries within the same Python session. `reset_backoff()` (line 60) zeros the counter after a successful request.

`acquire()` lines 33-37 honor the backoff window: `if now < self._backoff_until: await asyncio.sleep(wait)`. Subsequent queries hitting the same engine during the backoff window either wait (capped by `RATE_WAIT_TIMEOUT=60s` from bee_fix) or `RATE_SKIP` if the wait exceeds the cap.

Callers of `backoff()`: `src/search/engines/google.py:90, 109` — fires on Google CAPTCHA detection (`/sorry/` URL) and on any unhandled exception in `search()`.

## Evidenz

**Run 2026-05-22 (`value_eval_probe.py` 16-pair batch):** `/tmp/value_eval_probe_run.log` records the cascade:

| Pair | CAPTCHA event | Backoff applied | Google result |
|------|---------------|-----------------|---------------|
| 1 | yes | 34s (attempt 0: 30 + 4 jitter) | google=0 |
| 2 | yes | 65s (attempt 1: 60 + 5 jitter) | google=0 |
| 3 | (waited 60s = RATE_WAIT_TIMEOUT) | — | google=0 |
| 4 | yes | 123s (attempt 2: 120 + 3 jitter) | google=0 |
| 5 | (waited 60s) | — | google=0 |
| 6 | (waited 60s) | — | google=0 |
| 7 | yes | 244s (attempt 3: 240 + 4 jitter) | google=0 |
| 8-16 | (all waited 60s) | — | google=0 |

**Net waste:** ≈466s of accumulated wallclock spent in backoff sleeps. **Net benefit:** zero — Google CAPTCHA'd every retry because Google's provider-side bot-detection state does not decay in seconds, and re-querying within the same browser session preserves the fingerprint that triggered the original CAPTCHA. The doubling escalation does not work as a recovery mechanism; it just delays the inevitable EMPTY_BLOCK return.

This pattern reproduces the failure mode documented in `decisions/OldThemes/pooling/04_zero_query_diagnosis.md` (2026-05-20) — the formula `30 × 2^attempt + jitter[1..10]` matched observed backoffs there too. The bee_fix changes (RATE_WAIT_TIMEOUT 5s → 60s) prevented the cascade from blocking *other* engines during Chrome's CDP-event-flood window, but did not address the wastefulness of the backoff retry itself.

Independent validation that 4 req/min pacing is correct: `google.py:65` sets `max_requests=4` — code is at the spec. CAPTCHA at 4/min is therefore not a rate-limit problem; it's a browser-fingerprint problem at Google's end, outside the rate_limiter's responsibility. Slower waits cannot fix it.

## Recommendation (SOLL)

**Remove the exponential-backoff retry behavior entirely.** Fail-fast on 429/CAPTCHA/Block:

1. Engine detects failure → records `EMPTY_BLOCK` (or analogous status) and returns immediately. No sleep, no `_backoff_until`, no `_backoff_attempt`.
2. Other engines in the same query proceed normally — bee_fix's `RATE_WAIT_TIMEOUT=60s` cap on `acquire()` already covers the asyncio-event-loop-starvation case during Chrome CDP floods.
3. No session-scoped "engine dead" flag. The next query in the same session tries the failing engine again from scratch. If it fails again, record + continue. If it succeeds, results flow normally. Zero memory between queries.
4. Token-bucket pacing (`MAX_REQUESTS / WINDOW_SECONDS`) stays untouched — that's normal rate-management, not retry-with-backoff.

**Concrete code changes:**

- `src/search/rate_limiter.py`: remove `backoff()`, `reset_backoff()`, `_backoff_until`, `_backoff_attempt` fields. Remove `BACKOFF_BASE = 30.0` constant. Remove lines 33-37 in `acquire()` (the `_backoff_until` check + sleep). The class shrinks to pure token-bucket pacing.
- `src/search/engines/google.py:90`: remove `limiter.backoff()` after CAPTCHA detection. The return-EMPTY_BLOCK already records the failure; the backoff call is the redundant part.
- `src/search/engines/google.py:97`: remove `limiter.reset_backoff()` after successful results — no counter to reset.
- `src/search/engines/google.py:109`: same — remove `get_limiter(self.name).backoff()` in the exception handler.
- Search for any other callers of `backoff()` / `reset_backoff()` across `src/` and remove.

**Why session-stateless re-tries are robust:** provider-side bot-detection state can recover over minutes-to-hours; our session-level sleeps span seconds and never reach the recovery threshold. A naive "try again on next natural query trigger" gives the provider time to reset organically (between Opus sessions, between user queries, between Workflow ticks) without requiring our code to model the provider's internal state. Empirically: the 466s wasted in today's batch produced no Google results — the same outcome as fail-fast in 0 seconds.

## Offene Fragen

- **Should we add an explicit "engine-failed-this-query" status that propagates to the query log?** Currently `EMPTY_BLOCK` is the umbrella reason. A separate `BLOCKED_CAPTCHA` / `BLOCKED_429` would help debugging without re-introducing retry logic. Not blocking the cleanup itself; can follow in a subsequent commit.
- **Should the cross-encoder service (port 8082) and other downstream HTTP services follow the same fail-fast policy?** Yes — the project-wide principle in `decisions/OldThemes/no_backoff_retry.md` applies to every external service call. Concrete change to RAG-server-call paths in `search_web.py` / `preview.py` if any retry-with-backoff has crept in.

## Quellen

- Diagnosed failure mode + formula derivation: `decisions/OldThemes/pooling/04_zero_query_diagnosis.md`
- Reproduced in value-eval: `decisions/OldThemes/pooling/07_value_eval.md` (Caveats section, Google CAPTCHA)
- Probe-run evidence: `/tmp/value_eval_probe_run.log`
- Project-wide principle: `decisions/OldThemes/no_backoff_retry.md`
