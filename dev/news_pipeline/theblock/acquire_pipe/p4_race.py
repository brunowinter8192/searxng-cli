# INFRASTRUCTURE

import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url
from p5_logger import AcquireLogger
from p6_buffer import DEFAULT_CONCURRENCY


# ORCHESTRATOR

def run_race(
    pool:            list[tuple[str, str]],
    target_urls:     list[str],
    content_type:    str,
    logger:          AcquireLogger,
    content_handler: Callable[[str, bytes], None] | None = None,
    concurrency:     int = DEFAULT_CONCURRENCY,
) -> tuple[list[str], list[str]]:
    """Continuous race loop: concurrency workers each pull (url, proxy) and fetch immediately.

    URLs are served round-robin; done entries are skipped. At the tail, when fewer
    pending URLs remain than free workers, multiple workers race the same URL — first
    success wins. Pool is shuffled once; each proxy is consumed at most once (no
    cooldown, no burn). Returns (done, gap); gap is non-empty only if the pool is
    exhausted before all URLs are fetched.
    """
    candidates  = pool[:]
    random.shuffle(candidates)
    _proxy_idx  = [0]
    _proxy_lock = threading.Lock()

    _url_list  = list(target_urls)
    _url_idx   = [0]
    done_set:  set[str]  = set()
    done:      list[str] = []
    _lock = threading.Lock()
    total = len(_url_list)

    def _next_proxy() -> tuple[str, str] | None:
        with _proxy_lock:
            if _proxy_idx[0] >= len(candidates):
                return None
            p = candidates[_proxy_idx[0]]
            _proxy_idx[0] += 1
            return p

    def _next_url() -> str | None:
        with _lock:
            n = len(_url_list)
            for _ in range(n):
                url = _url_list[_url_idx[0] % n]
                _url_idx[0] += 1
                if url not in done_set:
                    return url
            return None   # all done

    def _mark_done(url: str, content: bytes) -> None:
        newly  = False
        n_done = 0
        name   = url.split("/")[-1]
        with _lock:
            if url not in done_set:
                done_set.add(url)
                done.append(url)
                newly  = True
                n_done = len(done_set)
        if newly:
            print(f"[race] {n_done}/{total} done: {name}")
            if content_handler is not None:
                content_handler(url, content)

    def worker() -> None:
        while True:
            url = _next_url()
            if url is None:
                return
            proxy = _next_proxy()
            if proxy is None:
                return
            proto, hp = proxy
            status, content = fetch_url(proto, hp, url, content_type)
            logger.record_attempt(proto, hp, url, status == "ok")
            if status == "ok":
                _mark_done(url, content)

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(worker) for _ in range(concurrency)]
        for f in as_completed(futures):
            f.result()

    gap = [u for u in _url_list if u not in done_set]
    return done, gap
