#!/usr/bin/env python3
# Instrumented async proxy liveness checker + concurrency sweep.
# Stage 1: freeze pool → check liveness via curl_cffi.AsyncSession → classify failures → sweep_log.md
#
# Modes:
#   --freeze               fetch 68 sources (lists imported from probe_pool_size.py), write frozen_pool/
#   --sample N [--seed S]  check N random proxies; seed=42 default → identical sample across runs
#   --full                 check entire frozen pool
#
# Usage:
#   ./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --freeze
#   ./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --sample 20000 --concurrency 512
#   ./venv/bin/python dev/news_pipeline/theblock/probe_liveness.py --sample 20000 --concurrency 1000 --connect-timeout 5 --read-timeout 5

# INFRASTRUCTURE

import argparse
import asyncio
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import (
    RequestException,
    Timeout,
    ProxyError,
    SSLError,
)
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.const import CurlECode

# Source lists + async fetcher imported from probe_pool_size — do not re-type the 68 URLs
sys.path.insert(0, str(Path(__file__).parent))
from probe_pool_size import HTTP_SOURCES, SOCKS4_SOURCES, SOCKS5_SOURCES, fetch_all_sources  # noqa: E402
from monosans_loader import load_monosans_proxies  # noqa: E402
from proxy_status_log import record_run  # noqa: E402

SCRIPT_DIR  = Path(__file__).parent
FROZEN_DIR  = SCRIPT_DIR / "frozen_pool"
LOG_DIR     = SCRIPT_DIR / "probe_liveness_logs"
SWEEP_LOG   = LOG_DIR / "sweep_log.md"

CHECK_URL   = "http://ipv4.icanhazip.com"
SAMPLE_SEED = 42
_IP_RE      = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

DEAD_BUCKETS = [
    "connect_timeout", "read_timeout", "hard_timeout", "connection_refused",
    "proxy_handshake_error", "resolve_error", "tls_error",
    "http_non200", "bad_body", "unknown",
]

# ORCHESTRATOR

async def probe_liveness_workflow() -> None:
    args = parse_args()

    if args.freeze:
        await freeze_pool()
        return

    if args.source == "monosans":
        entries = load_monosans_proxies()
        mode    = "monosans"
    else:
        frozen_dir = Path(args.input)
        entries    = load_frozen_pool(frozen_dir)
        if args.sample:
            entries = build_sample(entries, args.sample, args.seed)
            mode    = "sample"
        else:
            mode    = "full"

    ts      = datetime.now(timezone.utc)
    t0_wall = time.monotonic()

    results = await run_checks(
        entries,
        concurrency=args.concurrency,
        connect_s=args.connect_timeout,
        read_s=args.read_timeout,
    )

    elapsed = time.monotonic() - t0_wall
    print_console_summary(results, args.concurrency, elapsed)
    append_sweep_log(
        results, ts, mode, len(entries),
        args.concurrency, args.connect_timeout, args.read_timeout, elapsed,
    )
    if any(r["bucket"] == "unknown" for r in results):
        write_unknown_log(results, ts)
    record_run(results, mode)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Proxy liveness checker + concurrency sweep")
    p.add_argument("--freeze", action="store_true", help="Fetch 68 sources, write frozen_pool/")
    p.add_argument("--source", choices=["frozen", "monosans"], default="frozen",
                   help="Proxy source: frozen pool dir (default) or monosans live JSON")
    p.add_argument("--sample", type=int, metavar="N", help="Check N random proxies (seeded)")
    p.add_argument("--full", action="store_true", help="Check full frozen pool")
    p.add_argument("--seed", type=int, default=SAMPLE_SEED, help=f"RNG seed (default {SAMPLE_SEED})")
    p.add_argument("--concurrency", type=int, default=512, help="Semaphore size (default 512)")
    p.add_argument("--connect-timeout", type=float, default=5.0, metavar="S")
    p.add_argument("--read-timeout",    type=float, default=5.0, metavar="S")
    p.add_argument("--input", default=str(FROZEN_DIR), help="Frozen pool dir")
    return p.parse_args()


async def freeze_pool() -> None:
    """Fetch all 68 sources, deduplicate per bucket, write sorted frozen_pool/{http,socks4,socks5}.txt."""
    print("=== freeze: fetching 68 sources ===")
    t0 = time.monotonic()
    source_results = await fetch_all_sources()
    elapsed = time.monotonic() - t0

    bucket_proxies: dict[str, set[str]] = {"http": set(), "socks4": set(), "socks5": set()}
    for r in source_results:
        bucket_proxies[r["bucket"]].update(r["proxies"])

    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    for bucket, proxies in bucket_proxies.items():
        path = FROZEN_DIR / f"{bucket}.txt"
        path.write_text("\n".join(sorted(proxies)) + "\n", encoding="utf-8")
        print(f"  {bucket:8}: {len(proxies):>8,} unique → {path.name}")

    ok    = sum(1 for r in source_results if r["ok"])
    total = sum(len(p) for p in bucket_proxies.values())
    print(f"\nFrozen: {total:,} unique total | {ok}/{len(source_results)} sources OK | {elapsed:.1f}s")


def load_frozen_pool(frozen_dir: Path) -> list[tuple[str, str]]:
    """Return [(protocol, host:port)] in deterministic order: http→socks4→socks5, sorted within each."""
    entries: list[tuple[str, str]] = []
    for proto in ("http", "socks4", "socks5"):
        path = frozen_dir / f"{proto}.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append((proto, line))
    return entries


def build_sample(entries: list[tuple[str, str]], n: int, seed: int) -> list[tuple[str, str]]:
    """Deterministic sample: same seed + same frozen files → identical proxies every run."""
    return random.Random(seed).sample(entries, min(n, len(entries)))


async def run_checks(
    entries: list[tuple[str, str]],
    concurrency: int,
    connect_s: float,
    read_s: float,
) -> list[dict]:
    """Check all entries concurrently under Semaphore(concurrency); progress every 2000."""
    sem     = asyncio.Semaphore(concurrency)
    results: list[dict | None] = [None] * len(entries)
    done    = [0]
    total   = len(entries)

    print(f"Checking {total:,} proxies  concurrency={concurrency}  "
          f"connect={connect_s}s  read={read_s}s ...")

    async with AsyncSession() as session:
        async def _one(i: int, proto: str, host_port: str) -> None:
            results[i] = await check_proxy(session, sem, proto, host_port, connect_s, read_s)
            done[0] += 1
            n = done[0]
            if n % 2000 == 0 or n == total:
                alive_so_far = sum(1 for r in results[:n] if r and r["alive"])
                print(f"  {n:>6}/{total}  alive={alive_so_far}", flush=True)

        await asyncio.gather(*[_one(i, proto, hp) for i, (proto, hp) in enumerate(entries)])

    return results  # type: ignore[return-value]


async def check_proxy(
    session: AsyncSession,
    sem: asyncio.Semaphore,
    proto: str,
    host_port: str,
    connect_s: float,
    read_s: float,
) -> dict:
    """GET CHECK_URL through one proxy; classify outcome into alive/dead bucket."""
    # socks5h = remote DNS resolution through proxy (avoids local DNS load, more representative)
    proxy_proto = "socks5h" if proto == "socks5" else proto
    proxy_url   = f"{proxy_proto}://{host_port}"

    async with sem:
        t0      = time.monotonic()          # measure from semaphore-acquire, not queue-entry
        elapsed = 0.0
        try:
            resp    = await asyncio.wait_for(
                session.get(
                    CHECK_URL,
                    proxy=proxy_url,
                    timeout=(connect_s, read_s),
                    allow_redirects=False,
                ),
                timeout=connect_s + read_s + 2.0,   # hard Python deadline: curl timeout + 2s slack
            )
            elapsed = time.monotonic() - t0
            body    = resp.text.strip() if resp.text else ""

            if resp.status_code == 200 and _IP_RE.match(body):
                return _res(proto, host_port, True,  "alive",       "",                   elapsed)
            if resp.status_code == 200:
                return _res(proto, host_port, False, "bad_body",    body[:80],            elapsed)
            return     _res(proto, host_port, False, "http_non200", f"status={resp.status_code}", elapsed)

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            return _res(proto, host_port, False, "hard_timeout",
                        f"asyncio.wait_for exceeded at {elapsed:.2f}s", elapsed)
        except RequestException as e:
            elapsed = time.monotonic() - t0
            bucket, detail = classify_error(e, elapsed, connect_s, read_s)
            return _res(proto, host_port, False, bucket, detail, elapsed)
        except Exception as e:
            elapsed = time.monotonic() - t0
            return _res(proto, host_port, False, "unknown",
                        f"{type(e).__name__}: {str(e)[:120]}", elapsed)


def _res(proto: str, host_port: str, alive: bool, bucket: str, detail: str, elapsed: float) -> dict:
    return {"proto": proto, "host_port": host_port,
            "alive": alive, "bucket": bucket, "detail": detail, "elapsed": elapsed}


def classify_error(
    exc: RequestException, elapsed_s: float, connect_s: float, read_s: float
) -> tuple[str, str]:
    """Map RequestException → (reason_bucket, detail_string).

    Timeout split: elapsed time is primary discriminator (robust across libcurl versions);
    message text is secondary fallback; if NEITHER matches, bucket=unknown (version-drift signal).
    ProxyError checked before CurlConnectionError because curl_cffi's code2error() re-maps
    RECV_ERROR+"CONNECT" to ProxyError — catching that case as proxy_handshake_error, not connection_refused.
    """
    code    = getattr(exc, "code", 0)
    msg     = str(exc)
    total_s = connect_s + read_s

    if isinstance(exc, Timeout):
        slack = 0.5
        if elapsed_s <= connect_s + slack:
            return "connect_timeout", f"elapsed={elapsed_s:.2f}s"
        if elapsed_s >= total_s - slack:
            return "read_timeout", f"elapsed={elapsed_s:.2f}s"
        # Fallback: libcurl message text (version-dependent)
        if "Connection timed out" in msg:
            return "connect_timeout", f"msg-text elapsed={elapsed_s:.2f}s"
        if "Operation timed out" in msg:
            return "read_timeout", f"msg-text elapsed={elapsed_s:.2f}s"
        # Neither elapsed-time nor text matched — log as unknown for version-drift detection
        return "unknown", (
            f"Timeout unclassified elapsed={elapsed_s:.2f}s "
            f"connect_limit={connect_s}s total_limit={total_s}s msg={msg!r}"
        )

    if int(code) in (CurlECode.COULDNT_RESOLVE_PROXY, CurlECode.COULDNT_RESOLVE_HOST):
        return "resolve_error", f"code={int(code)} {msg[:80]}"

    if isinstance(exc, ProxyError) or int(code) in (CurlECode.GOT_NOTHING, CurlECode.WEIRD_SERVER_REPLY):
        return "proxy_handshake_error", f"code={int(code)} {msg[:80]}"

    if isinstance(exc, CurlConnectionError):
        return "connection_refused", f"code={int(code)} {msg[:80]}"

    if isinstance(exc, SSLError):
        return "tls_error", f"code={int(code)} {msg[:80]}"

    return "unknown", f"code={int(code)} type={type(exc).__name__} {msg[:120]}"


def print_console_summary(results: list[dict], concurrency: int, elapsed: float) -> None:
    alive = sum(1 for r in results if r["alive"])
    n     = len(results)
    dead  = n - alive
    tp    = n / elapsed if elapsed > 0 else 0

    histogram: dict[str, int] = defaultdict(int)
    for r in results:
        if not r["alive"]:
            histogram[r["bucket"]] += 1

    print(f"\n--- concurrency={concurrency}  elapsed={elapsed:.1f}s  throughput={tp:.0f}/s ---")
    print(f"  Alive: {alive:,}/{n:,}  ({100*alive/n:.1f}%)")
    if dead:
        print("  Dead reason histogram:")
        for bucket in DEAD_BUCKETS:
            count = histogram.get(bucket, 0)
            if count:
                print(f"    {bucket:<25} {count:>6,}  ({100*count/dead:.1f}% of dead)")


def append_sweep_log(
    results: list[dict],
    ts: datetime,
    mode: str,
    n: int,
    concurrency: int,
    connect_s: float,
    read_s: float,
    elapsed: float,
) -> None:
    """Append one structured markdown entry to sweep_log.md (committed — comparable-over-time record)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    alive     = sum(1 for r in results if r["alive"])
    dead      = n - alive
    tp        = n / elapsed if elapsed > 0 else 0
    alive_pct = 100 * alive / n if n else 0

    histogram: dict[str, int] = defaultdict(int)
    for r in results:
        if not r["alive"]:
            histogram[r["bucket"]] += 1

    lines = [
        "---",
        f"## {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} | {mode} | n={n:,} | "
        f"concurrency={concurrency} | timeout={connect_s}s/{read_s}s",
        "",
        "| Wall-clock | Throughput | Alive | Alive% | Dead |",
        "|---|---|---|---|---|",
        f"| {elapsed:.1f}s | {tp:.0f}/s | {alive:,} | {alive_pct:.1f}% | {dead:,} |",
        "",
        "### Dead Reason Histogram",
        "",
        "| Reason | Count | % of dead |",
        "|---|---|---|",
    ]
    for bucket in DEAD_BUCKETS:
        count = histogram.get(bucket, 0)
        pct   = 100 * count / dead if dead else 0.0
        lines.append(f"| {bucket} | {count:,} | {pct:.1f}% |")
    lines.append("")

    with SWEEP_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nAppended sweep entry → {SWEEP_LOG}")


def write_unknown_log(results: list[dict], ts: datetime) -> None:
    """Write full detail of unknown-bucket results to a per-run gitignored log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path     = LOG_DIR / f"unknown_errors_{ts.strftime('%Y%m%dT%H%M%SZ')}.log"
    unknowns = [r for r in results if r["bucket"] == "unknown"]
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# Unknown errors — {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} — {len(unknowns)} entries\n\n")
        for r in unknowns:
            f.write(
                f"proto={r['proto']}  {r['host_port']}  "
                f"elapsed={r['elapsed']:.2f}s  {r['detail']}\n"
            )
    print(f"  Unknown log ({len(unknowns)} entries) → {path}")


if __name__ == "__main__":
    asyncio.run(probe_liveness_workflow())
