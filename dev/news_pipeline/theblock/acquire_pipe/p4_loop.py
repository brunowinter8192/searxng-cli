# INFRASTRUCTURE

import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url
from p2_cooldown import PersistentCooldownManager
from p5_logger import AcquireLogger
from p6_buffer import refill_buffer, BUFFER_SIZE, DEFAULT_CONCURRENCY


# ORCHESTRATOR

def run_loop(
    pool_22k: list[tuple[str, str]],
    buf: list[tuple[str, str]],
    target_urls: list[str],
    content_type: str,
    logger: AcquireLogger,
    cm: PersistentCooldownManager,
    concurrency: int = DEFAULT_CONCURRENCY,
    content_handler: Callable[[str, bytes], None] | None = None,
) -> tuple[list[str], list[str]]:
    """Sustained concurrent working-set rotation loop with 2-strikes lifecycle.

    Draws batches from the active buffer (buf); working-set proxies (proven this
    session) fill Slot 1, fresh buffer candidates fill Slot 2. buf is refilled
    from pool_22k (eligible, socks4-first) whenever it drops below BUFFER_SIZE.

    2-strikes lifecycle:
      1st consecutive fail  → URL back to queue; proxy stays eligible (NOT burned).
      2nd consecutive fail  → burn: cm.mark_burned + remove from buf + wset.
      Success               → proxy joins wset; consecutive-fail counter reset.

    cm.flush() is called once per batch (after as_completed) — the only I/O path
    for cooldown writes regardless of how many proxies burned in the batch.

    Returns (done_urls, gap_urls). gap is non-empty when buf + wset are exhausted
    before target is complete; Stage 4 adds wait-on-exhaustion around this function.
    """
    queue         = deque(target_urls)
    done:         list[str]                      = []
    wset:         set[tuple[str, str]]           = set()
    psuccess:     dict[tuple[str, str], int]     = {}
    _consec_fail: dict[tuple[str, str], int]     = {}

    while queue:
        if len(buf) < BUFFER_SIZE:
            buf = refill_buffer(buf, pool_22k, cm)

        batch = _build_batch(queue, wset, buf, concurrency)
        if not batch:
            break   # buf + wset exhausted → caller handles wait / refresh

        for _ in batch:
            queue.popleft()

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
                    if content_handler is not None:
                        content_handler(url, content)
                    done.append(url)
                    wset.add(key)
                    psuccess[key] = psuccess.get(key, 0) + 1
                    _consec_fail.pop(key, None)              # success resets counter
                else:
                    queue.append(url)                        # retry — back of queue
                    fails = _consec_fail.get(key, 0) + 1
                    if fails >= 2:
                        # 2nd consecutive fail → burn
                        logger.record_burn(proto, hp, b_count=psuccess.get(key, 0))
                        cm.mark_burned(proto, hp)
                        wset.discard(key)
                        buf = [p for p in buf if p != key]  # remove from active buffer
                        _consec_fail.pop(key, None)          # reset (proxy now cooling)
                        psuccess.pop(key, None)
                    else:
                        _consec_fail[key] = fails            # 1st fail: proxy stays eligible

        cm.flush()                               # one I/O per batch, covers all burns
        logger.record_working_set(len(wset))

    return done, list(queue)


# FUNCTIONS

# Build one batch: working-set proxies first, then fresh candidates from active buffer
def _build_batch(
    queue:       deque,
    wset:        set[tuple[str, str]],
    buf:         list[tuple[str, str]],
    concurrency: int,
) -> list[tuple[str, str, str]]:
    """Return list of (proto, hp, url) up to concurrency; each proxy appears once."""
    batch:            list[tuple[str, str, str]] = []
    assigned_proxies: set[tuple[str, str]]       = set()
    url_iter = iter(queue)   # front-to-back peek without popping

    # Slot 1: working-set proxies (proven this session)
    for proto, hp in wset:
        if len(batch) >= concurrency:
            break
        url = next(url_iter, None)
        if url is None:
            break
        batch.append((proto, hp, url))
        assigned_proxies.add((proto, hp))

    # Slot 2: fresh candidates from active buffer (already eligible + socks4-first)
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

    return batch
