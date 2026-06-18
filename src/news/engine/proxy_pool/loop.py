# INFRASTRUCTURE

import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from src.news.engine.proxy_pool.fetch import fetch_url
from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.buffer import build_active_buffer, refill_buffer, BUFFER_SIZE, DEFAULT_CONCURRENCY

_sleep             = time.sleep    # patchable in tests without affecting stdlib time
REFRESH_INTERVAL_S = 3600          # full pool reload cadence (60 min)
STALL_TIMEOUT_S    = 3600          # stall: no done/dead progress for one full pool cycle → terminate


# ORCHESTRATOR

def run_loop(
    pool_provider: Callable[[], tuple[list[tuple[str, str]], list[dict]]],
    target_urls: list[str],
    content_type: str,
    logger: AcquireLogger,
    cm: PersistentCooldownManager,
    concurrency: int = DEFAULT_CONCURRENCY,
    buffer_size: int = BUFFER_SIZE,
    content_handler: Callable[[str, bytes], None] | None = None,
    refresh_interval_s: float = REFRESH_INTERVAL_S,
) -> tuple[list[str], list[str], list[str]]:
    """Sustained concurrent rotation loop: 60-min pool refresh + wait-on-exhaustion.

    pool_provider() is called once on startup and again at each refresh_interval_s
    tick to fetch a fresh proxy list; build_active_buffer() filters it through cm
    to rebuild the active buffer (up to buffer_size eligible).
    2-strikes lifecycle drives burn→cooldown.

    Exhaustion (buf + wset both empty): sleeps until the earlier of (next cooldown
    expiry, next refresh tick), then calls pool_provider() and rebuilds buf.

    Returns (done, dead, gap):
      done — URLs successfully fetched with valid content.
      dead — URLs whose origin returned 404/410 (permanently gone; proxy confirmed working).
      gap  — URLs remaining in queue (should be empty on clean termination).
    """
    queue         = deque(target_urls)
    done:         list[str]                  = []
    dead:         list[str]                  = []
    wset:         set[tuple[str, str]]       = set()
    _consec_fail: dict[tuple[str, str], int] = {}

    pool, sources = pool_provider()
    logger.record_pool_refresh(len(pool))
    for s in sources:
        logger.record_pool_source(s["url"], s["ok"], s["count"])
    buf            = build_active_buffer(pool, cm, buffer_size)
    _last_refresh  = time.monotonic()
    _last_progress = time.monotonic()  # stall detection: last time a URL resolved to done or dead

    while queue:
        now = time.monotonic()

        if now - _last_progress >= STALL_TIMEOUT_S:
            print(
                f"[proxy_pool] stall: no progress for {STALL_TIMEOUT_S}s, "
                f"terminating with {len(queue)} urls unresolved → failed",
                file=sys.stderr,
            )
            break

        if now - _last_refresh >= refresh_interval_s:
            pool, sources = pool_provider()
            logger.record_pool_refresh(len(pool))
            for s in sources:
                logger.record_pool_source(s["url"], s["ok"], s["count"])
            buf           = build_active_buffer(pool, cm, buffer_size)
            _last_refresh = time.monotonic()

        if len(buf) < buffer_size:
            buf = refill_buffer(buf, pool, cm, buffer_size)

        batch = _build_batch(queue, wset, buf, concurrency)
        if not batch:
            # buf + wset exhausted — sleep until next eligible proxy or scheduled refresh
            sleep_s = _compute_sleep(cm, _last_refresh, refresh_interval_s)
            if sleep_s > 0:
                _sleep(sleep_s)
            buf = build_active_buffer(pool, cm, buffer_size)
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
                status, content = fut.result()
                key             = (proto, hp)

                logger.record_attempt(proto, hp, url, status == "ok")

                if status == "ok":
                    if url not in batch_done:
                        batch_done.add(url)
                        if content_handler is not None:
                            content_handler(url, content)
                        done.append(url)
                        _last_progress = time.monotonic()
                    wset.add(key)
                    _consec_fail.pop(key, None)
                elif status == "dead":
                    if url not in batch_done:
                        batch_done.add(url)
                        dead.append(url)
                        _last_progress = time.monotonic()
                    wset.add(key)
                    _consec_fail.pop(key, None)
                else:
                    batch_failed.add(url)
                    fails = _consec_fail.get(key, 0) + 1
                    if fails >= 2:
                        cm.mark_burned(proto, hp)
                        wset.discard(key)
                        buf = [p for p in buf if p != key]
                        _consec_fail.pop(key, None)
                    else:
                        _consec_fail[key] = fails

        for url in batch_failed:
            if url not in batch_done:
                queue.append(url)

    return done, dead, list(queue)


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
