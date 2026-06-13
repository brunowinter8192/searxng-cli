# INFRASTRUCTURE

import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url
from p2_cooldown import CooldownManager
from p5_logger import AcquireLogger

DEFAULT_CONCURRENCY = 50


# ORCHESTRATOR

def run_loop(
    candidates: list[tuple[str, str]],
    target_urls: list[str],
    content_type: str,
    logger: AcquireLogger,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[list[str], list[str]]:
    """Concurrent working-set rotation loop. Return (done_urls, gap_urls).

    Each round fires up to CONCURRENCY (proxy, URL) pairs concurrently — every
    request targets a real URL (no wasted proxy-check stage).
    Working-set proxies (proven) fill slots first; remaining slots pull fresh
    candidates. Success keeps the proxy in the working set; failure burns it
    to 60min cooldown and returns the URL to the back of the queue.
    Gap when working set is empty AND no eligible candidates remain.
    """
    queue    = deque(target_urls)
    done: list[str]                          = []
    cm       = CooldownManager()
    wset:    set[tuple[str, str]]            = set()   # (proto, hp) proven working
    psuccess: dict[tuple[str, str], int]     = {}      # (proto, hp) → ok count this session

    while queue:
        batch = _build_batch(queue, wset, cm, candidates, concurrency)
        if not batch:
            break   # no eligible candidates, working set empty → gap

        # Pop exactly the URLs allocated to this batch (failed ones go to queue back)
        for _ in batch:
            queue.popleft()

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(fetch_url, p, hp, url, content_type): (p, hp, url)
                for p, hp, url in batch
            }
            for fut in as_completed(futures):
                proto, hp, url = futures[fut]
                ok, _content   = fut.result()
                key            = (proto, hp)

                logger.record_attempt(proto, hp, url, ok)

                if ok:
                    done.append(url)
                    wset.add(key)
                    psuccess[key] = psuccess.get(key, 0) + 1
                else:
                    queue.append(url)   # retry later — back of queue
                    logger.record_burn(proto, hp, b_count=psuccess.get(key, 0))
                    cm.mark_burned(proto, hp)
                    wset.discard(key)
                    psuccess.pop(key, None)

        logger.record_working_set(len(wset))

    gap = list(queue)
    return done, gap


# FUNCTIONS

# Build one batch: working-set proxies first, then fresh eligible candidates
def _build_batch(
    queue:       deque,
    wset:        set[tuple[str, str]],
    cm:          CooldownManager,
    candidates:  list[tuple[str, str]],
    concurrency: int,
) -> list[tuple[str, str, str]]:
    """Return list of (proto, hp, url) up to concurrency; each proxy appears once."""
    batch:            list[tuple[str, str, str]] = []
    assigned_proxies: set[tuple[str, str]]       = set()
    url_iter = iter(queue)   # front-to-back peek without popping

    # Slot 1: working-set proxies (already proven this session)
    for proto, hp in wset:
        if len(batch) >= concurrency:
            break
        url = next(url_iter, None)
        if url is None:
            break
        batch.append((proto, hp, url))
        assigned_proxies.add((proto, hp))

    # Slot 2: fresh eligible candidates (socks4-first from CooldownManager)
    for proto, hp in cm.eligible_candidates(candidates):
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
