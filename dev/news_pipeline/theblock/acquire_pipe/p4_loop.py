# INFRASTRUCTURE

import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url
from p2_cooldown import PersistentCooldownManager
from p5_logger import AcquireLogger
from p6_buffer import build_active_buffer, refill_buffer, BUFFER_SIZE, DEFAULT_CONCURRENCY

_sleep             = time.sleep    # patchable in tests without affecting stdlib time
REFRESH_INTERVAL_S = 3600          # full pool reload cadence (60 min)
DEFAULT_MAX_WALL_S = 12 * 3600     # hard safety cap default (12 h)


# ORCHESTRATOR

def run_loop(
    pool_provider: Callable[[], list[tuple[str, str]]],
    target_urls: list[str],
    content_type: str,
    logger: AcquireLogger,
    cm: PersistentCooldownManager,
    concurrency: int = DEFAULT_CONCURRENCY,
    buffer_size: int = BUFFER_SIZE,
    content_handler: Callable[[str, bytes], None] | None = None,
    max_wall_s: float = DEFAULT_MAX_WALL_S,
    refresh_interval_s: float = REFRESH_INTERVAL_S,
) -> tuple[list[str], list[str]]:
    """Sustained concurrent rotation loop: 60-min pool refresh + wait-on-exhaustion.

    pool_provider() is called once on startup and again at each refresh_interval_s
    tick to fetch a fresh proxy list; build_active_buffer() filters it through cm
    to rebuild the active buffer (up to buffer_size eligible, socks4-first).
    2-strikes lifecycle (Stage 3) drives burn→cooldown.

    Exhaustion (buf + wset both empty): sleeps until the earlier of (next cooldown
    expiry, next refresh tick), then calls pool_provider() and rebuilds buf — no gap
    reported, no early exit. cap_remaining clamps the sleep so the safety cap is
    never overshot.

    Safety cap: after max_wall_s wall-seconds the loop exits cleanly, leaving any
    unfinished URLs in gap. refresh_interval_s is a separate parameter to allow
    small values in tests without patching module globals.
    """
    run_start     = time.monotonic()
    queue         = deque(target_urls)
    done:         list[str]                  = []
    wset:         set[tuple[str, str]]       = set()
    psuccess:     dict[tuple[str, str], int] = {}
    _consec_fail: dict[tuple[str, str], int] = {}

    pool_22k      = pool_provider()
    logger.record_pool_refresh(len(pool_22k))
    buf           = build_active_buffer(pool_22k, cm, buffer_size)
    _last_refresh = time.monotonic()

    while queue:
        now = time.monotonic()

        if now - run_start >= max_wall_s:
            break   # hard safety cap

        if now - _last_refresh >= refresh_interval_s:
            pool_22k      = pool_provider()
            logger.record_pool_refresh(len(pool_22k))
            buf           = build_active_buffer(pool_22k, cm, buffer_size)
            _last_refresh = time.monotonic()

        if len(buf) < buffer_size:
            buf = refill_buffer(buf, pool_22k, cm, buffer_size)

        batch = _build_batch(queue, wset, buf, concurrency)
        if not batch:
            # buf + wset exhausted — wait until earliest useful wakeup
            now_mono      = time.monotonic()
            cap_remaining = max_wall_s - (now_mono - run_start)
            if cap_remaining <= 0:
                break
            sleep_s = _compute_sleep(cm, _last_refresh, refresh_interval_s)
            sleep_s = min(sleep_s, cap_remaining)
            if sleep_s > 0:
                _sleep(sleep_s)
            pool_22k      = pool_provider()
            logger.record_pool_refresh(len(pool_22k))
            buf           = build_active_buffer(pool_22k, cm, buffer_size)
            _last_refresh = time.monotonic()
            continue

        n_urls_consumed = len({url for _, _, url in batch})
        for _ in range(n_urls_consumed):
            queue.popleft()

        batch_done:   set[str] = set()
        batch_failed: set[str] = set()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(fetch_url, p, hp, url, content_type): (p, hp, url)
                for p, hp, url in batch
            }
            for fut in as_completed(futures):
                proto, hp, url = futures[fut]
                ok, content    = fut.result()
                key            = (proto, hp)

                logger.record_attempt(proto, hp, url, ok)

                if ok:
                    if url not in batch_done:
                        batch_done.add(url)
                        if content_handler is not None:
                            content_handler(url, content)
                        done.append(url)
                    wset.add(key)
                    psuccess[key] = psuccess.get(key, 0) + 1
                    _consec_fail.pop(key, None)
                else:
                    batch_failed.add(url)
                    fails = _consec_fail.get(key, 0) + 1
                    if fails >= 2:
                        logger.record_burn(proto, hp, b_count=psuccess.get(key, 0))
                        cm.mark_burned(proto, hp)
                        wset.discard(key)
                        buf = [p for p in buf if p != key]
                        _consec_fail.pop(key, None)
                        psuccess.pop(key, None)
                    else:
                        _consec_fail[key] = fails

        for url in batch_failed:
            if url not in batch_done:
                queue.append(url)

        logger.record_working_set(len(wset))

    return done, list(queue)


# FUNCTIONS

# Seconds to sleep on exhaustion: min(next cooldown expiry, next refresh tick)
def _compute_sleep(
    cm: PersistentCooldownManager,
    last_refresh_mono: float,
    refresh_interval_s: float,
) -> float:
    """Return seconds to sleep; 0.0 means immediate wakeup."""
    now_mono        = time.monotonic()
    secs_to_refresh = max(0.0, (last_refresh_mono + refresh_interval_s) - now_mono)

    earliest = cm.earliest_eligible_at()
    if earliest is None:
        return secs_to_refresh

    now_utc          = datetime.now(timezone.utc)
    secs_to_eligible = max(0.0, (earliest - now_utc).total_seconds())
    return min(secs_to_refresh, secs_to_eligible)


# Build one batch: working-set proxies first, then fresh candidates from active buffer
def _build_batch(
    queue:       deque,
    wset:        set[tuple[str, str]],
    buf:         list[tuple[str, str]],
    concurrency: int,
) -> list[tuple[str, str, str]]:
    """Return list of (proto, hp, url) up to concurrency; each proxy appears once.

    Phase 1 — Normal: wset proxies first, then fresh buf entries; each gets the next
    distinct URL from queue.
    Phase 2 — Tail: when pending URLs < available proxy slots, surplus proxies race
    the same remaining URLs round-robin so multiple proxies contest each leftover URL.
    """
    batch:            list[tuple[str, str, str]] = []
    assigned_proxies: set[tuple[str, str]]       = set()
    url_iter = iter(queue)

    for proto, hp in wset:
        if len(batch) >= concurrency:
            break
        url = next(url_iter, None)
        if url is None:
            break
        batch.append((proto, hp, url))
        assigned_proxies.add((proto, hp))

    for proto, hp in buf:
        if len(batch) >= concurrency:
            break
        if (proto, hp) in assigned_proxies or (proto, hp) in wset:
            continue
        url = next(url_iter, None)
        if url is None:
            break
        batch.append((proto, hp, url))
        assigned_proxies.add((proto, hp))

    # Phase 2 — Tail: surplus proxy slots race the same pending URLs round-robin
    if len(batch) < concurrency and batch:
        pending_urls = [url for _, _, url in batch]
        url_idx      = 0
        for proto, hp in list(wset) + buf:
            if len(batch) >= concurrency:
                break
            if (proto, hp) in assigned_proxies:
                continue
            batch.append((proto, hp, pending_urls[url_idx % len(pending_urls)]))
            assigned_proxies.add((proto, hp))
            url_idx += 1

    return batch
