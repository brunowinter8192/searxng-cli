# INFRASTRUCTURE

import asyncio
import itertools
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests as cffi

# p0_pool lives in the same directory — add it to the path so direct execution works
sys.path.insert(0, str(Path(__file__).parent))

from p0_pool import PersistentCooldownManager, load_backfill_pool

# Three rotating test URLs — known-alive CoinDesk articles from different years.
# Each alive-check picks the next URL in round-robin so no single article
# biases liveness results (a 404/redirect on one URL would falsely fail all proxies).
#
# Regwall check is intentionally ABSENT from the curl_cffi alive-check:
# REGWALL_SIGNALS ("Create a FREE account...", etc.) are embedded in every
# CoinDesk HTML page as always-present React components (hidden by CSS/JS).
# They cannot distinguish regwalled from non-regwalled in raw HTML.
# Regwall detection is handled downstream by the Playwright browser using
# the rendered markdown (where the overlay IS visible text when triggered).
# The alive-check purpose is purely: "can this proxy reach CoinDesk at all?"
COINDESK_TEST_URLS: list[str] = [
    "https://www.coindesk.com/markets/2021/12/31/here-are-the-top-10-cryptocurrencies-of-2021",
    "https://www.coindesk.com/business/2021/12/31/shiba-inu-launches-beta-version-of-dao-to-give-users-more-authority-over-crypto-projects",
    "https://www.coindesk.com/opinion/2021/12/31/5-money-themes-to-watch-in-2022",
]

# Proxy protocols Playwright can ride; socks4 excluded (unreliable in Playwright)
BROWSER_ELIGIBLE_PROTOS = frozenset({"http", "socks5"})

ALIVE_CONCURRENCY     = 128   # concurrent curl_cffi alive-checks
ALIVE_CHECK_TIMEOUT_S = 12    # seconds per alive-check request
POOL_REFRESH_INTERVAL = 3600  # seconds between full pool reloads
FEEDER_QUEUE_MAXSIZE  = 40    # cap the ready-buffer (prevents stampede on browser slots)


# ORCHESTRATOR

class AliveFeeder:
    """Continuously validates proxies against CoinDesk; feeds browser-eligible ones to a queue.

    Runs as an asyncio background task.  The caller owns the proxy_queue and
    reads (proto, host_port) tuples from it to bind to browser slots.

    Protocol filter:
      - http / socks5  → put in proxy_queue (browser-eligible)
      - socks4         → alive-check still runs (counted in stats) but NOT queued
    """

    def __init__(
        self,
        proxy_queue: asyncio.Queue,
        cm: PersistentCooldownManager,
        alive_concurrency: int = ALIVE_CONCURRENCY,
        test_urls: list[str] = COINDESK_TEST_URLS,
        pool_refresh_interval: float = POOL_REFRESH_INTERVAL,
    ):
        self._proxy_queue       = proxy_queue
        self._cm                = cm
        self._alive_concurrency = alive_concurrency
        self._test_urls         = test_urls
        self._url_cycle         = itertools.cycle(test_urls)
        self._refresh_interval  = pool_refresh_interval
        self._stop              = False

        # Stats — read externally for reporting
        self.stats = FeederStats()

    async def run(self) -> None:
        """Main feeder loop.  Run as asyncio.create_task(feeder.run())."""
        print("[feeder] loading proxy pool ...", file=sys.stderr)
        t0           = time.monotonic()
        pool, sources = await asyncio.get_event_loop().run_in_executor(
            None, load_backfill_pool
        )
        load_s = time.monotonic() - t0
        self.stats.pool_size = len(pool)
        print(
            f"[feeder] pool loaded: {len(pool)} proxies in {load_s:.1f}s",
            file=sys.stderr,
        )

        last_refresh   = time.monotonic()
        pool_idx       = 0   # cursor through eligible list
        eligible_cache = self._cm.eligible_candidates(pool)

        with ThreadPoolExecutor(max_workers=self._alive_concurrency) as executor:
            while not self._stop:
                # Periodic pool refresh
                if time.monotonic() - last_refresh >= self._refresh_interval:
                    pool, _ = await asyncio.get_event_loop().run_in_executor(
                        None, load_backfill_pool
                    )
                    self.stats.pool_size = len(pool)
                    eligible_cache       = self._cm.eligible_candidates(pool)
                    pool_idx             = 0
                    last_refresh         = time.monotonic()
                    print(
                        f"[feeder] pool refreshed: {len(pool)} proxies",
                        file=sys.stderr,
                    )

                # Rebuild eligible list on each pass (cooldown may have changed)
                eligible = self._cm.eligible_candidates(pool)
                if pool_idx >= len(eligible):
                    # Full pass done; sleep briefly before restarting
                    pool_idx = 0
                    await asyncio.sleep(10)
                    continue

                # Slice the next batch
                batch = eligible[pool_idx: pool_idx + self._alive_concurrency]
                pool_idx += len(batch)

                if not batch:
                    await asyncio.sleep(5)
                    continue

                # Rotate test URLs across batch positions
                test_urls_for_batch = [next(self._url_cycle) for _ in batch]

                # Run alive-checks in thread pool (curl_cffi is sync)
                loop    = asyncio.get_event_loop()
                futures = [
                    loop.run_in_executor(
                        executor,
                        _check_proxy_alive,
                        proto, hp, url,
                    )
                    for (proto, hp), url in zip(batch, test_urls_for_batch)
                ]
                results = await asyncio.gather(*futures, return_exceptions=True)

                for (proto, hp), alive in zip(batch, results):
                    self.stats.checked += 1
                    if isinstance(alive, Exception) or not alive:
                        self.stats.dead += 1
                        continue

                    # Alive — classify by protocol
                    self.stats.alive_total += 1
                    if proto == "http":
                        self.stats.alive_http += 1
                    elif proto == "socks5":
                        self.stats.alive_socks5 += 1
                    elif proto == "socks4":
                        self.stats.alive_socks4_curl_only += 1

                    if proto in BROWSER_ELIGIBLE_PROTOS:
                        # Don't block the loop if the queue is full — drop and move on
                        try:
                            self._proxy_queue.put_nowait((proto, hp))
                            self.stats.queued += 1
                        except asyncio.QueueFull:
                            self.stats.queue_dropped += 1

    def stop(self) -> None:
        self._stop = True


# FUNCTIONS

# Sync alive-check: HTTP 200 via proxy → proxy is live and CoinDesk-reachable
def _check_proxy_alive(proto: str, host_port: str, test_url: str) -> bool:
    """Return True if proxy reaches test_url with HTTP 200.

    Regwall check is intentionally absent: REGWALL_SIGNALS are embedded in every
    CoinDesk HTML page as always-present React components (hidden by CSS/JS).
    Raw-HTML regwall detection is unreliable; it is handled downstream by the
    Playwright browser on markdown-rendered output.  This check only validates
    reachability.
    """
    purl = f"{proto}://{host_port}"
    try:
        sess = cffi.Session(impersonate="chrome")
        r    = sess.get(
            test_url,
            proxies={"http": purl, "https": purl},
            timeout=ALIVE_CHECK_TIMEOUT_S,
        )
        return r.status_code == 200
    except Exception:
        return False


@dataclass
class FeederStats:
    pool_size:            int = 0
    checked:              int = 0
    dead:                 int = 0
    alive_total:          int = 0
    alive_http:           int = 0
    alive_socks5:         int = 0
    alive_socks4_curl_only: int = 0
    queued:               int = 0
    queue_dropped:        int = 0

    @property
    def browser_eligible(self) -> int:
        return self.alive_http + self.alive_socks5

    def summary(self) -> str:
        lines = [
            f"Pool size:            {self.pool_size}",
            f"Checked:              {self.checked}",
            f"Dead / fail:          {self.dead}",
            f"Alive total:          {self.alive_total}",
            f"  http:               {self.alive_http}",
            f"  socks5:             {self.alive_socks5}",
            f"  socks4 (curl only): {self.alive_socks4_curl_only}",
            f"Browser-eligible:     {self.browser_eligible}",
            f"Queued:               {self.queued}",
            f"Queue dropped (full): {self.queue_dropped}",
        ]
        return "\n".join(lines)


# Standalone smoke test — run feeder for CAP_SECONDS, report stats
async def _smoke(cap_seconds: float = 120) -> None:
    cm    = PersistentCooldownManager()
    queue = asyncio.Queue(maxsize=FEEDER_QUEUE_MAXSIZE)
    feeder = AliveFeeder(proxy_queue=queue, cm=cm)

    task = asyncio.create_task(feeder.run())
    t0   = time.monotonic()

    while time.monotonic() - t0 < cap_seconds:
        elapsed = time.monotonic() - t0
        s       = feeder.stats
        print(
            f"\r[{elapsed:5.0f}s] checked={s.checked} alive={s.alive_total}"
            f" (http={s.alive_http} socks5={s.alive_socks5}) queued={s.queued}",
            end="", file=sys.stderr, flush=True,
        )
        await asyncio.sleep(5)

    feeder.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    print("", file=sys.stderr)  # newline after progress line
    elapsed = time.monotonic() - t0
    s       = feeder.stats

    report = f"""# AliveFeeder Smoke Test — {int(elapsed)}s cap

## Pool
Pool size: {s.pool_size}

## Alive-Check Results
| Metric | Count |
|---|---|
| Total checked | {s.checked} |
| Dead / connect-fail | {s.dead} |
| Alive total | {s.alive_total} |
| → http (browser-eligible) | {s.alive_http} |
| → socks5 (browser-eligible) | {s.alive_socks5} |
| → socks4 (curl-only, NOT browser) | {s.alive_socks4_curl_only} |
| Browser-eligible subtotal | {s.browser_eligible} |
| Put into queue | {s.queued} |
| Queue-full drops | {s.queue_dropped} |

## Rates
- Checked/s: {s.checked / elapsed:.1f}
- Browser-eligible/min: {s.browser_eligible / elapsed * 60:.1f}
- Alive rate: {s.alive_total / max(s.checked, 1) * 100:.1f}%
- Browser-eligible rate: {s.browser_eligible / max(s.checked, 1) * 100:.1f}%
"""
    print(report)


if __name__ == "__main__":
    asyncio.run(_smoke(cap_seconds=120))
