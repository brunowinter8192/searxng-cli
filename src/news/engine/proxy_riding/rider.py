# INFRASTRUCTURE

import asyncio
import hashlib
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import (
    AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, ProxyConfig,
)
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager

# Regwall signals checked on result.markdown.raw_markdown (browser-rendered visible text).
# NOT on result.html — signals are embedded as hidden React components in all CoinDesk pages.
REGWALL_SIGNALS: list[str] = [
    "from_regwall",
    "Create a FREE account to continue reading",
    "You've reached your monthly limit",
]

PAGE_TIMEOUT_MS   = 8_000    # default; overridden per-call via page_timeout_ms param
DELAY_BEFORE_HTML = 0.5      # s wait after domcontentloaded
STALL_TIMEOUT_S   = 3_600.0  # 60 min no progress → terminate
FAIL_THRESHOLD    = 2        # failed/empty strikes before dropping a proxy (mirrors burn_threshold for regwall)

# Playwright error substrings that indicate a proxy-side failure (not CoinDesk)
_PROXY_ERR = ("timeout", "proxy", "err_proxy", "tunnel", "socks",
              "err_empty", "connection refused", "connection failed", "net::err")

RAW_SUBDIR = "raw"


@dataclass
class RideRecord:
    proxy_str:        str
    proto:            str
    host_port:        str
    n_ok:             int
    n_regwall:        int
    n_connect_fail:   int
    n_failed:         int        # URLs that triggered the fail-rotation (2-strike drop)
    n_urls_attempted: int
    burned_threshold: bool
    burned_connect:   bool
    ride_s:           float
    positions:        list = field(default_factory=list)  # (url, status, elapsed_s)


@dataclass
class JobRecord:
    url:           str
    url_hash:      str
    status:        str        # ok | regwall | connect_fail | failed | empty
    char_count:    int | None
    markdown_len:  int | None
    elapsed_s:     float | None
    error:         str | None
    file:          str | None
    t_start:       datetime
    ride_position: int        # which URL on this proxy (1st, 2nd, …)
    proxy_str:     str


@dataclass
class RiderState:
    url_queue:       asyncio.Queue
    proxy_pool:      list               # raw (proto, hp) tuples from load_backfill_pool()
    cooldown_mgr:    PersistentCooldownManager
    output_dir:      Path               # raw HTML target: output_dir/raw/{hash}.html
    job_dir:         Path               # report target: scrape_jobs/{job_id}/
    burn_threshold:  int
    page_timeout_ms: int
    total_urls:      int
    target_urls:     frozenset               # all distinct target URLs; open = target_urls − done_urls

    n_ok:            int   = 0
    n_regwall:       int   = 0
    n_failed:        int   = 0
    n_connect_fail:  int   = 0
    in_flight:       int   = 0
    job_records:     list  = field(default_factory=list)
    ride_records:    list  = field(default_factory=list)
    last_progress_mono: float      = field(default_factory=time.monotonic)
    stall_timeout_s:    float      = STALL_TIMEOUT_S
    termination:        str        = "running"   # all-done | stall | pool-exhausted
    proxy_cursor:       int        = 0
    proxy_lock:         asyncio.Lock = field(default_factory=asyncio.Lock)
    n_browsers:         int        = 1
    n_slots:            int        = 0
    in_flight_urls:     set        = field(default_factory=set)
    done_urls:          set        = field(default_factory=set)    # URLs written; first-writer guard
    t_job_start:        datetime   = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def all_resolved(self) -> bool:
        return len(self.done_urls) >= len(self.target_urls)


# ORCHESTRATOR

# Launch n_slots concurrent rider tasks across n_browsers browser instances; return shared state when done.
async def run_riding_pool(
    url_queue:       asyncio.Queue,
    proxy_pool:      list,
    cooldown_mgr:    PersistentCooldownManager,
    output_dir:      Path,
    job_dir:         Path,
    target_urls:     frozenset,
    burn_threshold:  int,
    n_slots:         int,
    page_timeout_ms: int   = PAGE_TIMEOUT_MS,
    n_browsers:      int   = 1,
    stall_timeout_s: float = STALL_TIMEOUT_S,
) -> RiderState:
    (output_dir / RAW_SUBDIR).mkdir(parents=True, exist_ok=True)
    state = RiderState(
        url_queue=url_queue,
        proxy_pool=proxy_pool,
        cooldown_mgr=cooldown_mgr,
        output_dir=output_dir,
        job_dir=job_dir,
        burn_threshold=burn_threshold,
        page_timeout_ms=page_timeout_ms,
        total_urls=url_queue.qsize(),
        target_urls=target_urls,
        stall_timeout_s=stall_timeout_s,
    )
    state.n_browsers = n_browsers
    state.n_slots    = n_slots
    crawlers = [AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) for _ in range(n_browsers)]
    await asyncio.gather(*[c.start() for c in crawlers])
    watchdog = asyncio.create_task(_watchdog(state))
    try:
        tasks = [asyncio.create_task(_run_slot(i, crawlers[i % n_browsers], state)) for i in range(n_slots)]
        await asyncio.gather(*tasks)
    finally:
        watchdog.cancel()
        results = await asyncio.gather(*[c.close() for c in crawlers], return_exceptions=True)
        for idx, r in enumerate(results):
            if isinstance(r, Exception):
                print(f"[rider] crawler[{idx}].close warn: {r}", file=sys.stderr)
    if state.termination == "running":
        state.termination = "all-done"
    return state


# FUNCTIONS

# One rider task: pull proxy → ride URL queue → burn/rotate → repeat.
async def _run_slot(slot_id: int, crawler: AsyncWebCrawler, state: RiderState) -> None:
    print(f"[slot {slot_id}] started", file=sys.stderr)

    while not state.all_resolved:
        if time.monotonic() - state.last_progress_mono > state.stall_timeout_s:
            print(f"[slot {slot_id}] stall — stopping", file=sys.stderr)
            state.termination = "stall"
            break

        entry = await _next_proxy(state)
        if entry is None:
            if state.all_resolved:
                break
            print(f"[slot {slot_id}] pool exhausted", file=sys.stderr)
            state.termination = "pool-exhausted"
            break

        proto, hp = entry
        pstr      = f"{proto}://{hp}"
        t_bind    = time.monotonic()
        burn_count = 0
        fail_count = 0
        ride_ok    = 0
        positions: list = []
        cf_broke   = False

        try:
            while burn_count < state.burn_threshold:
                if state.all_resolved:
                    break
                if time.monotonic() - state.last_progress_mono > state.stall_timeout_s:
                    state.termination = "stall"
                    break

                dequeued = True
                try:
                    url = state.url_queue.get_nowait()
                    if url in state.done_urls:
                        continue   # stale queue entry — already won by a racer
                except asyncio.QueueEmpty:
                    if state.all_resolved:
                        break
                    open_list = sorted(state.target_urls - state.done_urls)
                    if not open_list:
                        break
                    url = open_list[slot_id % len(open_list)]
                    dequeued = False

                state.in_flight += 1
                state.in_flight_urls.add(url)
                ride_pos  = len(positions) + 1
                t_url_abs = datetime.now(timezone.utc)

                status, char_count, markdown_len, elapsed, html, err = await _fetch_one_url(
                    crawler, url, pstr, state.page_timeout_ms,
                )
                state.in_flight -= 1
                state.in_flight_urls.discard(url)

                positions.append((url, status, round(elapsed, 2)))
                job = JobRecord(
                    url=url, url_hash=_url_hash(url),
                    status=status, char_count=char_count, markdown_len=markdown_len,
                    elapsed_s=round(elapsed, 2), error=err, file=None,
                    t_start=t_url_abs, ride_position=ride_pos, proxy_str=pstr,
                )

                if status == "ok":
                    if url not in state.done_urls:
                        state.done_urls.add(url)
                        out      = _write_raw(_url_hash(url), html, state.output_dir)
                        job.file = str(out)
                        state.n_ok += 1
                        ride_ok   += 1
                        state.last_progress_mono = time.monotonic()
                        print(f"[slot {slot_id}] ok  r={ride_pos} {url[:70]}", file=sys.stderr)
                    else:
                        print(f"[slot {slot_id}] dup-race discarded {url[:70]}", file=sys.stderr)
                        continue   # skip job_records.append — dup fetch, no stats

                elif status == "regwall":
                    burn_count      += 1
                    state.n_regwall += 1
                    if dequeued and url not in state.done_urls:
                        state.url_queue.put_nowait(url)
                    print(
                        f"[slot {slot_id}] RW  burn={burn_count}/{state.burn_threshold}"
                        f" r={ride_pos}", file=sys.stderr,
                    )

                elif status == "connect_fail":
                    state.n_connect_fail += 1
                    if dequeued and url not in state.done_urls:
                        state.url_queue.put_nowait(url)
                    cf_broke = True
                    print(f"[slot {slot_id}] CF  rotating", file=sys.stderr)
                    break

                else:  # failed | empty
                    fail_count += 1
                    if dequeued and url not in state.done_urls:
                        state.url_queue.put_nowait(url)
                    print(
                        f"[slot {slot_id}] {status} fail={fail_count}/{FAIL_THRESHOLD}"
                        f" r={ride_pos} → requeue", file=sys.stderr,
                    )
                    if fail_count >= FAIL_THRESHOLD:
                        break

                state.job_records.append(job)

        finally:
            ride = RideRecord(
                proxy_str=pstr, proto=proto, host_port=hp,
                n_ok=ride_ok, n_regwall=burn_count,
                n_connect_fail=1 if cf_broke else 0,
                n_failed=fail_count,
                n_urls_attempted=len(positions),
                burned_threshold=burn_count >= state.burn_threshold,
                burned_connect=cf_broke,
                ride_s=time.monotonic() - t_bind,
                positions=positions,
            )
            state.ride_records.append(ride)
            state.cooldown_mgr.mark_burned(proto, hp)
            print(
                f"[slot {slot_id}] proxy done ok={ride_ok} rw={burn_count}"
                f" cf={int(cf_broke)} n={len(positions)} {pstr}",
                file=sys.stderr,
            )

    print(f"[slot {slot_id}] exit", file=sys.stderr)


# Atomically advance pool cursor; return (proto, hp) or None if pool is empty.
async def _next_proxy(state: RiderState) -> tuple[str, str] | None:
    async with state.proxy_lock:
        eligible = state.cooldown_mgr.eligible_candidates(state.proxy_pool)
        if not eligible:
            return None
        idx              = state.proxy_cursor % len(eligible)
        state.proxy_cursor += 1
        return eligible[idx]


# Fetch one URL via per-context proxy; return (status, char_count, markdown_len, elapsed, html, err).
async def _fetch_one_url(
    crawler:         AsyncWebCrawler,
    url:             str,
    proxy_str:       str,
    page_timeout_ms: int,
) -> tuple[str, int | None, int | None, float, str, str | None]:
    sid     = str(uuid.uuid4())
    run_cfg = CrawlerRunConfig(
        session_id=sid,
        proxy_config=ProxyConfig(server=proxy_str),
        cache_mode=CacheMode.BYPASS,
        page_timeout=page_timeout_ms,
        wait_until="domcontentloaded",
        delay_before_return_html=DELAY_BEFORE_HTML,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )

    t0           = time.perf_counter()
    status       = "failed"
    html         = ""
    err          = None
    markdown_len = None

    try:
        result  = await crawler.arun(url=url, config=run_cfg)
        elapsed = time.perf_counter() - t0

        if not result.success:
            emsg   = (result.error_message or "").lower()
            status = "connect_fail" if any(k in emsg for k in _PROXY_ERR) else "failed"
            err    = result.error_message
        elif not result.html:
            status = "empty"
        else:
            raw_md = (result.markdown.raw_markdown or "") if result.markdown else ""
            if _is_regwall(raw_md):
                status = "regwall"
            else:
                status       = "ok"
                html         = result.html
                markdown_len = len(raw_md)

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        status  = "connect_fail"
        err     = str(exc)

    finally:
        try:
            await crawler.crawler_strategy.browser_manager.kill_session(sid)
        except Exception as exc:
            print(f"[rider] kill_session warn: {exc}", file=sys.stderr)

    return status, len(html) if html else None, markdown_len, elapsed, html, err


# Return True if markdown contains any REGWALL_SIGNALS.
def _is_regwall(markdown: str) -> bool:
    return any(sig in markdown for sig in REGWALL_SIGNALS)


# Write raw HTML to output_dir/raw/{url_hash}.html; return path.
def _write_raw(url_hash: str, html: str, output_dir: Path) -> Path:
    path = output_dir / RAW_SUBDIR / f"{url_hash}.html"
    path.write_text(html, encoding="utf-8")
    return path


# SHA-256 URL hash (12 hex chars) — matches scrape.py convention.
def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


# Independent progress watchdog — runs as a separate asyncio task, immune to wedged slots.
# Uses asyncio.sleep() (timer-based) so it fires even when all slot tasks are permanently
# suspended on await crawler.arun(). Polls every poll_interval seconds; default is
# min(30, stall_timeout_s / 4) so a short smoke timeout still gets fast detection.
async def _watchdog(
    state:         RiderState,
    poll_interval: float | None = None,
) -> None:
    interval = poll_interval if poll_interval is not None else min(30.0, state.stall_timeout_s / 4)
    while True:
        await asyncio.sleep(interval)
        if state.all_resolved:
            return
        idle = time.monotonic() - state.last_progress_mono
        if idle > state.stall_timeout_s:
            _abort_stall(state, idle)  # does not return


# Write remaining_urls.txt + job.md then os._exit(1). Never returns.
# os._exit bypasses asyncio teardown and browser.close() so wedged Chrome processes
# cannot re-hang the shutdown; raw files already flushed to disk before we reach here.
def _abort_stall(state: RiderState, idle_s: float) -> None:
    print(
        f"[watchdog] STALL {idle_s:.0f}s ≥ {state.stall_timeout_s:.0f}s — "
        f"writing report + failure log → os._exit(1)",
        file=sys.stderr,
    )
    state.termination = "stall"

    # Drain remaining queue URLs
    queued: list[str] = []
    while True:
        try:
            queued.append(state.url_queue.get_nowait())
        except asyncio.QueueEmpty:
            break

    # In-flight URLs — the wedged ones: diagnostically valuable
    inflight = sorted(state.in_flight_urls)

    # Write failure log + report into scrape_jobs/{job_id}/ (same dir as normal completion)
    state.job_dir.mkdir(parents=True, exist_ok=True)
    fail_log = state.job_dir / "remaining_urls.txt"
    lines = [
        f"# Remaining URLs at stall abort — idle {idle_s:.0f}s (threshold {state.stall_timeout_s:.0f}s)",
        f"# Total un-scraped: {len(queued) + len(inflight)}",
        "",
        f"# never attempted (queue) — {len(queued)} URLs",
    ] + queued + [
        "",
        f"# in-flight / wedged at abort — {len(inflight)} URLs",
    ] + inflight
    fail_log.write_text("\n".join(lines), encoding="utf-8")
    print(f"[watchdog] failure log → {fail_log}", file=sys.stderr)

    # Write job.md via reporter; fallback to minimal stub on any error
    try:
        from src.news.engine.proxy_riding.reporter import write_riding_report  # late import — avoids circular at module level
        write_riding_report(state, state.job_dir, state.t_job_start)
        print(f"[watchdog] job.md → {state.job_dir / 'job.md'}", file=sys.stderr)
    except Exception as exc:
        print(f"[watchdog] write_riding_report WARN: {exc}", file=sys.stderr)
        try:
            (state.job_dir / "job.md").write_text(
                "\n".join([
                    "# CoinDesk riding job — STALL ABORT",
                    "",
                    "termination: stall",
                    f"idle_s: {idle_s:.0f}",
                    f"n_ok: {state.n_ok}",
                    f"n_regwall: {state.n_regwall}",
                    f"n_failed: {state.n_failed}",
                    f"n_connect_fail: {state.n_connect_fail}",
                    "",
                    f"Reporter error: {exc}",
                ]),
                encoding="utf-8",
            )
        except Exception as write_exc:
            print(f"[watchdog] fallback job.md WARN: {write_exc}", file=sys.stderr)

    sys.stderr.flush()
    os._exit(1)
