#!/usr/bin/env python3
# The Block proxy pipe — Stage 1 (neutral liveness) → Stage 2 (CF check) → Stage 3 (sitemap discovery + B-capture)
#
# Stage 1: Fetch fresh pool from 68 sources, sample 5k, neutral liveness @ concurrency=128.
# Stage 2: CF-pass check on neutral-alive with curl_cffi impersonate=chrome.
# Stage 3: Sequential-exhaustion discovery — drain ONE proxy until it 403/429s, record B, rotate.
#          This guarantees real B observations (vs round-robin which never exhausts any single proxy).
#
# Usage:
#   ./venv/bin/python dev/news_pipeline/theblock/pipe_theblock.py
#
# Output:
#   dev/news_pipeline/theblock/pipe_log.md  — funnel log (appended per run)
#   dev/news_pipeline/theblock/cache/       — per-sub sitemap checkpoint JSONs (resume-safe)

# INFRASTRUCTURE

import asyncio
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests as cffi_requests

sys.path.insert(0, str(Path(__file__).parent))
from probe_pool_size  import fetch_all_sources   # noqa: E402
from probe_liveness   import run_checks          # noqa: E402
from probe_discovery  import (                   # noqa: E402
    load_sub_cache, save_sub_cache, extract_locs, normalize_url, CACHE_DIR,
)
from source_tracker   import update_and_flush as tracker_flush  # noqa: E402

SCRIPT_DIR            = Path(__file__).parent
PIPE_LOG              = SCRIPT_DIR / "pipe_log.md"

BATCH_SIZE            = 5_000
CONCURRENCY_LIVENESS  = 128
CONCURRENCY_CF        = 20
CONNECT_TIMEOUT_S     = 5.0
READ_TIMEOUT_S        = 5.0
CF_TIMEOUT_S          = 15

TARGET_CF_CHECK       = "https://www.theblock.co/sitemap_tbco_post_type_post_0.xml"
SITEMAP_INDEX_URL     = "https://www.theblock.co/sitemap_tbco_index.xml"
XML_MARKERS           = [b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>"]

# ORCHESTRATOR

async def pipe_theblock_workflow() -> None:
    ts = datetime.now(timezone.utc)
    t0 = time.monotonic()
    print(f"=== The Block proxy pipe  {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} ===\n")

    print("[Stage 1] Fetching fresh pool + neutral liveness check ...")
    t1 = time.monotonic()
    all_entries, source_results, hp_to_sources = await fetch_fresh_pool()
    sample = random.sample(all_entries, min(BATCH_SIZE, len(all_entries)))
    print(f"  Pool: {len(all_entries):,} entries → sample: {len(sample):,}")
    liveness_results = await run_checks(
        sample,
        concurrency=CONCURRENCY_LIVENESS,
        connect_s=CONNECT_TIMEOUT_S,
        read_s=READ_TIMEOUT_S,
    )
    neutral_alive = build_proxy_urls(liveness_results)
    elapsed_s1 = time.monotonic() - t1
    print(f"  Neutral-alive: {len(neutral_alive):,}/{len(sample):,}  "
          f"({100*len(neutral_alive)/len(sample):.1f}%)  {elapsed_s1:.0f}s\n")

    print("[Stage 2] CF-pass check (curl_cffi chrome) ...")
    t2 = time.monotonic()
    cf_passing = stage2_cf_check(neutral_alive)
    elapsed_s2 = time.monotonic() - t2
    neu_n = len(neutral_alive)
    print(f"  CF-passing: {len(cf_passing):,}/{neu_n:,}  "
          f"({100*len(cf_passing)/neu_n:.1f}% of neutral)  {elapsed_s2:.0f}s\n")

    if not cf_passing:
        print("  No CF-passing proxies — aborting Stage 3.")
        append_pipe_log(ts, len(sample), len(neutral_alive), 0, 0, 0, [], [],
                        elapsed_s1, elapsed_s2, 0.0)
        tracker_flush(ts, source_results, sample, liveness_results, neutral_alive, [],
                      hp_to_sources)
        return

    print("[Stage 3] Discovery fetch (sequential exhaustion for B-capture) ...")
    t3 = time.monotonic()
    subs_fetched, total_subs, b_exhausted, b_active = stage3_discovery(cf_passing)
    elapsed_s3 = time.monotonic() - t3
    cached = count_cached()
    print(f"  Subs fetched this run: {subs_fetched}")
    print(f"  Cache progress: {cached}/{total_subs}  elapsed: {elapsed_s3:.0f}s\n")

    print(f"Total elapsed: {time.monotonic()-t0:.0f}s")
    append_pipe_log(ts, len(sample), len(neutral_alive), len(cf_passing),
                    subs_fetched, total_subs, b_exhausted, b_active,
                    elapsed_s1, elapsed_s2, elapsed_s3)
    tracker_flush(ts, source_results, sample, liveness_results, neutral_alive, cf_passing,
                  hp_to_sources)

# FUNCTIONS

async def fetch_fresh_pool() -> tuple[list[tuple[str, str]], list[dict], dict[str, set[str]]]:
    """Fetch all 68 sources fresh; return (entries, source_results, hp_to_sources)."""
    source_results = await fetch_all_sources()
    bucket: dict[str, set[str]] = {"http": set(), "socks4": set(), "socks5": set()}
    hp_to_sources: dict[str, set[str]] = {}
    for r in source_results:
        bucket[r["bucket"]].update(r["proxies"])
        for hp in r["proxies"]:
            hp_to_sources.setdefault(hp, set()).add(r["url"])
    entries: list[tuple[str, str]] = []
    for proto, proxies in bucket.items():
        for hp in proxies:
            entries.append((proto, hp))
    return entries, source_results, hp_to_sources


def build_proxy_urls(liveness_results: list[dict]) -> list[str]:
    """Extract alive results → proxy URL strings (socks5 → socks5h for remote DNS)."""
    urls = []
    for r in liveness_results:
        if r["alive"]:
            proto = "socks5h" if r["proto"] == "socks5" else r["proto"]
            urls.append(f"{proto}://{r['host_port']}")
    return urls


def cf_get(proxy_url: str, url: str) -> tuple[bytes, int]:
    """GET url via proxy with curl_cffi chrome impersonation. Returns (body, status_code)."""
    try:
        s = cffi_requests.Session(impersonate="chrome")
        r = s.get(url, proxies={"http": proxy_url, "https": proxy_url}, timeout=CF_TIMEOUT_S)
        s.close()
        return r.content, r.status_code
    except Exception:
        return b"", 0


def is_xml(body: bytes) -> bool:
    head = body[:500]
    return any(m in head for m in XML_MARKERS)


def stage2_cf_check(proxy_urls: list[str]) -> list[str]:
    """CF-pass check on neutral-alive proxies. Returns list of passing proxy URL strings."""
    passing: list[str] = []
    lock = threading.Lock()
    done = [0]
    total = len(proxy_urls)

    def check_one(purl: str) -> str | None:
        body, status = cf_get(purl, TARGET_CF_CHECK)
        with lock:
            done[0] += 1
            if done[0] % 50 == 0 or done[0] == total:
                sys.stdout.write(f"\r  {done[0]}/{total} checked  ")
                sys.stdout.flush()
        return purl if (status == 200 and is_xml(body)) else None

    with ThreadPoolExecutor(max_workers=CONCURRENCY_CF) as ex:
        futures = {ex.submit(check_one, p): p for p in proxy_urls}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                passing.append(result)
    print()
    return passing


def stage3_discovery(cf_proxies: list[str]) -> tuple[int, int, list[int], list[int]]:
    """Fetch missing sub-sitemaps with sequential proxy exhaustion for B-capture.

    Strategy: stay on current proxy for consecutive subs until it returns 403/429 →
    record B (fetches completed by that proxy) → rotate to next. This guarantees
    each proxy reaches (or approaches) its CF block limit before we move on.

    Returns: (subs_fetched, total_subs, b_exhausted, b_active_lower_bounds)
    """
    sub_urls = get_sitemap_index(cf_proxies)
    if not sub_urls:
        print("  Could not fetch sitemap index — no working CF-passing proxy.")
        return 0, 0, [], []

    total_subs = len(sub_urls)
    pending    = [u for u in sub_urls if load_sub_cache(u) is None]
    print(f"  Index: {total_subs} subs total | {len(pending)} pending | "
          f"{total_subs - len(pending)} cached\n")

    if not pending:
        print("  All subs already cached.")
        return 0, total_subs, [], []

    proxy_queue:  list[str]       = list(cf_proxies)
    proxy_budget: dict[str, int]  = {p: 0 for p in proxy_queue}
    b_exhausted:  list[int]       = []
    subs_fetched = 0
    proxy_idx    = 0   # index into proxy_queue; stay put on success, advance on exhaust/transient

    for sub_url in pending:
        sub_name = sub_url.split("/")[-1]
        fetched  = False
        transient_tries = 0

        while proxy_queue and not fetched:
            if proxy_idx >= len(proxy_queue):
                proxy_idx = 0
            purl = proxy_queue[proxy_idx]

            body, status = cf_get(purl, sub_url)

            if status == 200 and is_xml(body):
                locs = [normalize_url(u)
                        for u in extract_locs(body.decode("utf-8", errors="replace"))]
                save_sub_cache(sub_url, locs)
                proxy_budget[purl] += 1
                subs_fetched += 1
                print(f"  [{subs_fetched:>2}] {sub_name:<55} "
                      f"B_so_far={proxy_budget[purl]}  proxy={purl[:35]}…")
                fetched = True
                # DO NOT advance proxy_idx — sequential exhaustion

            elif status in (403, 429):
                b = proxy_budget[purl]
                b_exhausted.append(b)
                print(f"  [--] {purl[:35]}… exhausted  HTTP {status}  B={b}  "
                      f"→ rotating ({len(proxy_queue)-1} proxies left)")
                proxy_queue.pop(proxy_idx)
                if proxy_idx >= len(proxy_queue):
                    proxy_idx = 0
                # Retry same sub with next proxy (proxy_idx already points at successor)

            else:
                # Transient (connect error, timeout, etc.) — skip this proxy for this sub
                transient_tries += 1
                proxy_idx += 1
                if transient_tries >= len(proxy_queue):
                    print(f"  [!!] {sub_name} — all proxies failed transiently, skipping")
                    fetched = True   # accept skip; sub stays uncached for next run

        if not proxy_queue:
            print(f"  All CF proxies exhausted after {subs_fetched} subs.")
            break

    b_active = [proxy_budget[p] for p in proxy_queue]
    return subs_fetched, total_subs, b_exhausted, b_active


def get_sitemap_index(cf_proxies: list[str]) -> list[str]:
    """Fetch sitemap_tbco_index.xml, trying proxies until one returns valid XML."""
    for purl in cf_proxies[:10]:
        body, status = cf_get(purl, SITEMAP_INDEX_URL)
        if status == 200 and is_xml(body):
            locs = extract_locs(body.decode("utf-8", errors="replace"))
            if locs:
                print(f"  Index fetched via {purl[:40]}…  ({len(locs)} sub-URLs)")
                return locs
    return []


def count_cached() -> int:
    return sum(1 for _ in CACHE_DIR.glob("sub_*.json"))


def append_pipe_log(
    ts: datetime,
    raw_n: int,
    neutral_n: int,
    cf_n: int,
    subs_fetched: int,
    total_subs: int,
    b_exhausted: list[int],
    b_active: list[int],
    elapsed_s1: float,
    elapsed_s2: float,
    elapsed_s3: float,
) -> None:
    """Append one structured funnel entry to pipe_log.md."""
    alive_pct  = 100 * neutral_n / raw_n   if raw_n      else 0.0
    cf_pct_neu = 100 * cf_n / neutral_n    if neutral_n  else 0.0
    cf_pct_raw = 100 * cf_n / raw_n        if raw_n      else 0.0
    cached     = count_cached()

    b_ctr = Counter(b_exhausted)

    lines = [
        "---",
        f"## {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} | batch={raw_n:,} | "
        f"conc_liveness={CONCURRENCY_LIVENESS} | conc_cf={CONCURRENCY_CF}",
        "",
        "| Stage | Count | Rate | Wall-clock |",
        "|---|---|---|---|",
        f"| Raw batch (fresh 68-source sample) | {raw_n:,} | — | — |",
        f"| Stage 1 neutral-alive | {neutral_n:,} | {alive_pct:.1f}% of raw | {elapsed_s1:.0f}s |",
        f"| Stage 2 CF-passing | {cf_n:,} | "
        f"{cf_pct_neu:.1f}% of neutral / {cf_pct_raw:.1f}% of raw | {elapsed_s2:.0f}s |",
        f"| Stage 3 subs fetched this run | {subs_fetched} | — | {elapsed_s3:.0f}s |",
        f"| Stage 3 cache progress | {cached}/{total_subs} | — | — |",
        "",
        "### Per-IP Budget B",
        "",
    ]

    if b_exhausted:
        b_min  = min(b_exhausted)
        b_max  = max(b_exhausted)
        b_mean = sum(b_exhausted) / len(b_exhausted)
        lines += [
            f"Exhausted proxies: n={len(b_exhausted)}  "
            f"min={b_min}  max={b_max}  mean={b_mean:.1f}",
            "",
            "| B (fetches before 403/429) | Count |",
            "|---|---|",
        ]
        for b_val in sorted(b_ctr):
            lines.append(f"| {b_val} | {b_ctr[b_val]} |")
    else:
        lines.append("No proxies exhausted this run (all still active, or Stage 3 not reached).")

    if b_active:
        lines += [
            "",
            f"Active proxies still alive at end: n={len(b_active)}  "
            f"lower-bound B: min={min(b_active)}  max={max(b_active)}",
        ]
    lines.append("")

    with PIPE_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Funnel log → {PIPE_LOG}")


if __name__ == "__main__":
    asyncio.run(pipe_theblock_workflow())
