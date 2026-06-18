# INFRASTRUCTURE

import asyncio
import hashlib
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

sys.path.insert(0, str(Path(__file__).parent))

from p0_pool import PersistentCooldownManager

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
    output_dir:      Path
    burn_threshold:  int
    page_timeout_ms: int
    total_urls:      int

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

    @property
    def all_resolved(self) -> bool:
        return self.url_queue.empty() and self.in_flight == 0


# ORCHESTRATOR

# Launch n_slots concurrent rider tasks on one shared browser; return shared state when done.
async def run_riding_pool(
    url_queue:       asyncio.Queue,
    proxy_pool:      list,
    cooldown_mgr:    PersistentCooldownManager,
    output_dir:      Path,
    burn_threshold:  int,
    n_slots:         int,
    page_timeout_ms: int = PAGE_TIMEOUT_MS,
) -> RiderState:
    (output_dir / RAW_SUBDIR).mkdir(parents=True, exist_ok=True)
    state = RiderState(
        url_queue=url_queue,
        proxy_pool=proxy_pool,
        cooldown_mgr=cooldown_mgr,
        output_dir=output_dir,
        burn_threshold=burn_threshold,
        page_timeout_ms=page_timeout_ms,
        total_urls=url_queue.qsize(),
    )
    crawler = AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False))
    await crawler.start()
    try:
        tasks = [asyncio.create_task(_run_slot(i, crawler, state)) for i in range(n_slots)]
        await asyncio.gather(*tasks)
    finally:
        try:
            await crawler.close()
        except Exception as exc:
            print(f"[rider] crawler.close warn: {exc}", file=sys.stderr)
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

                try:
                    url = await asyncio.wait_for(state.url_queue.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    if state.all_resolved:
                        break
                    continue

                state.in_flight += 1
                ride_pos  = len(positions) + 1
                t_url_abs = datetime.now(timezone.utc)

                status, char_count, markdown_len, elapsed, html, err = await _fetch_one_url(
                    crawler, url, pstr, state.page_timeout_ms,
                )
                state.in_flight -= 1

                positions.append((url, status, round(elapsed, 2)))
                job = JobRecord(
                    url=url, url_hash=_url_hash(url),
                    status=status, char_count=char_count, markdown_len=markdown_len,
                    elapsed_s=round(elapsed, 2), error=err, file=None,
                    t_start=t_url_abs, ride_position=ride_pos, proxy_str=pstr,
                )

                if status == "ok":
                    out      = _write_raw(_url_hash(url), html, state.output_dir)
                    job.file = str(out)
                    state.n_ok += 1
                    ride_ok   += 1
                    state.last_progress_mono = time.monotonic()
                    print(f"[slot {slot_id}] ok  r={ride_pos} {url[:70]}", file=sys.stderr)

                elif status == "regwall":
                    burn_count      += 1
                    state.n_regwall += 1
                    state.url_queue.put_nowait(url)
                    print(
                        f"[slot {slot_id}] RW  burn={burn_count}/{state.burn_threshold}"
                        f" r={ride_pos}", file=sys.stderr,
                    )

                elif status == "connect_fail":
                    state.n_connect_fail += 1
                    state.url_queue.put_nowait(url)
                    cf_broke = True
                    print(f"[slot {slot_id}] CF  rotating", file=sys.stderr)
                    break

                else:  # failed | empty
                    state.url_queue.put_nowait(url)
                    print(f"[slot {slot_id}] {status} r={ride_pos} → requeue", file=sys.stderr)

                state.job_records.append(job)

        finally:
            ride = RideRecord(
                proxy_str=pstr, proto=proto, host_port=hp,
                n_ok=ride_ok, n_regwall=burn_count,
                n_connect_fail=1 if cf_broke else 0,
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


# Mini smoke: 5 URLs, 4 slots, raw pool (no feeder), 5-min cap.
if __name__ == "__main__":
    import json
    from p0_pool import load_backfill_pool
    from p3_url_sampler import sample_urls

    N_URLS    = 5
    N_SLOTS   = 4
    TIMEOUT_S = 300

    async def smoke() -> None:
        print("[smoke] loading proxy pool ...", file=sys.stderr)
        pool, _ = await asyncio.get_running_loop().run_in_executor(None, load_backfill_pool)
        print(f"[smoke] pool: {len(pool)} raw proxies", file=sys.stderr)

        cm        = PersistentCooldownManager()
        urls      = sample_urls(500)[:N_URLS]
        url_queue = asyncio.Queue()
        [url_queue.put_nowait(u) for u in urls]
        print(f"[smoke] {N_URLS} URLs / {N_SLOTS} slots:", file=sys.stderr)
        [print(f"  {u}", file=sys.stderr) for u in urls]

        out_dir = Path(__file__).parent / "smoke_output"
        t0      = time.monotonic()

        try:
            state = await asyncio.wait_for(
                run_riding_pool(url_queue, pool, cm, out_dir,
                                burn_threshold=2, n_slots=N_SLOTS, page_timeout_ms=8000),
                timeout=TIMEOUT_S,
            )
            state_timeout = False
        except asyncio.TimeoutError:
            print("[smoke] TIMEOUT — partial results follow", file=sys.stderr)
            state_timeout = True
            state = None

        elapsed   = time.monotonic() - t0
        raw_dir   = out_dir / "raw"
        raw_files = sorted(raw_dir.glob("*.html")) if raw_dir.exists() else []

        report = {
            "elapsed_s":      round(elapsed, 1),
            "timeout":        state_timeout,
            "n_ok":           state.n_ok           if state else "?",
            "n_regwall":      state.n_regwall       if state else "?",
            "n_failed":       state.n_failed        if state else "?",
            "n_connect_fail": state.n_connect_fail  if state else "?",
            "termination":    state.termination     if state else "timeout",
            "proxies_used":   len(state.ride_records) if state else "?",
            "raw_files":      len(raw_files),
        }
        print(json.dumps(report, indent=2))
        for f in raw_files[:3]:
            print(f"  raw/{f.name}: {f.stat().st_size:,} bytes")

    asyncio.run(smoke())
