# INFRASTRUCTURE

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))              # curated_sources, proxy_status_log
sys.path.insert(0, str(Path(__file__).parent / "acquire_pipe"))  # p1_fetch, p2_cooldown

from curated_sources import load_backfill_pool
from p1_fetch import fetch_url, XML_MARKERS
from p2_cooldown import PersistentCooldownManager

INDEX_URL         = "https://www.theblock.co/sitemap_tbco_index.xml"
OUTPUT_DIR        = Path(__file__).parent / "probe_48h_output"
DIRECT_TIMEOUT    = 15.0
MAX_ARTICLE_TRIES = 30
INTER_SUB_DELAY   = 1.0   # seconds between sub-sitemap fetches

_INDEX_LOC_RE = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_URL_BLOCK_RE = re.compile(rb"<url>(.*?)</url>", re.DOTALL)
_LOC_RE       = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_MOD_RE       = re.compile(rb"<lastmod>([^<]+)</lastmod>")


# ORCHESTRATOR

def probe_48h_article_fetch_workflow(hours: float, max_article_tries: int) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    print(f"[probe] Loading backfill pool...")
    pool = load_backfill_pool()
    print(f"[probe] Pool: {len(pool)} proxies")

    print(f"[probe] Fetching sitemap index...")
    post_subs = _fetch_index(pool)
    print(f"[probe] Post sub-sitemaps: {len(post_subs)}")

    cm      = PersistentCooldownManager()
    all_entries:    list[tuple[str, datetime]] = []
    sub_hit_counts: dict[str, int]             = {}
    fetched = 0

    for i, sub_url in enumerate(post_subs):
        name    = sub_url.split("/")[-1]
        entries = _fetch_sub_sitemap(sub_url, pool, cm)
        fetched += 1
        recent  = [(u, m) for u, m in entries if m >= cutoff]
        sub_hit_counts[name] = len(recent)
        all_entries.extend(recent)
        print(f"[probe] {name}: {len(entries)} entries, {len(recent)} in {hours:.0f}h window")
        if i < len(post_subs) - 1:
            time.sleep(INTER_SUB_DELAY)

    print(f"[probe] Sub-sitemaps fetched: {fetched}/{len(post_subs)}")
    print(f"[probe] {hours:.0f}h entries total: {len(all_entries)}")

    if not all_entries:
        print(f"[probe] No articles found in last {hours:.0f}h — widen --hours and retry")
        return

    recent_path = OUTPUT_DIR / "recent_articles.txt"
    lines = [f"{mod.strftime('%Y-%m-%dT%H:%M:%SZ')}\t{url}" for url, mod in all_entries]
    recent_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[probe] recent_articles.txt → {recent_path} ({len(all_entries)} entries)")

    print("[probe] Sub-sitemap hit breakdown (non-zero only):")
    for name, count in sub_hit_counts.items():
        if count > 0:
            print(f"  {name}: {count}")

    targets = all_entries[:2]
    for idx, (url, mod) in enumerate(targets):
        ok, content, attempts = _fetch_article(url, pool, cm, max_article_tries)
        if ok:
            out_path = OUTPUT_DIR / f"article_{idx}.html"
            out_path.write_bytes(content)
            print(f"[probe] Article {idx + 1}: {url}")
            print(f"  → OK in {attempts} attempt(s), {len(content):,} bytes → {out_path.name}")
        else:
            print(f"[probe] Article {idx + 1}: {url}")
            print(f"  → FAILED after {attempts} attempts")


# FUNCTIONS

# Fetch sitemap index (direct then proxy); return post_type_post sub-sitemap URLs only
def _fetch_index(pool: list) -> list[str]:
    content = _fetch_index_direct()
    if content is None:
        content = _fetch_index_via_proxy(pool)
    locs = _INDEX_LOC_RE.findall(content)
    return [u.decode().strip() for u in locs if b"post_type_post" in u]


# Attempt direct httpx GET of sitemap index; return bytes on XML success, None otherwise
def _fetch_index_direct() -> bytes | None:
    try:
        r = httpx.get(INDEX_URL, timeout=DIRECT_TIMEOUT, follow_redirects=True)
        head = r.content[:500]
        if r.status_code == 200 and any(m in head for m in XML_MARKERS):
            print(f"[sitemap] Direct OK ({len(r.content):,} bytes)")
            return r.content
        print(f"[sitemap] Direct: status={r.status_code}, no XML marker — proxy fallback")
        return None
    except Exception as e:
        print(f"[sitemap] Direct error: {e} — proxy fallback")
        return None


# Fetch index via proxy rotation; raise on exhaustion
def _fetch_index_via_proxy(pool: list) -> bytes:
    cm         = PersistentCooldownManager()
    candidates = cm.eligible_candidates(pool)
    print(f"[sitemap] Proxy fallback: {len(candidates)} candidates")
    for proto, hp in candidates:
        ok, content = fetch_url(proto, hp, INDEX_URL, "xml")
        if ok:
            print(f"[sitemap] Proxy OK via {proto}://{hp} ({len(content):,} bytes)")
            return content
        cm.mark_burned(proto, hp)
    raise RuntimeError("sitemap index exhausted all proxy candidates")


# Fetch one post sub-sitemap via proxy rotation; return (url, lastmod) pairs
def _fetch_sub_sitemap(
    sub_url: str, pool: list, cm: PersistentCooldownManager
) -> list[tuple[str, datetime]]:
    candidates = cm.eligible_candidates(pool)
    for proto, hp in candidates:
        ok, content = fetch_url(proto, hp, sub_url, "xml")
        if ok:
            return _parse_url_blocks(content)
        cm.mark_burned(proto, hp)
    print(f"[probe] WARNING: {sub_url.split('/')[-1]} — all candidates exhausted, skipping")
    return []


# Parse <url> blocks from sub-sitemap XML; return (loc, lastmod) pairs with UTC datetimes
def _parse_url_blocks(content: bytes) -> list[tuple[str, datetime]]:
    results: list[tuple[str, datetime]] = []
    for block in _URL_BLOCK_RE.finditer(content):
        body  = block.group(1)
        loc_m = _LOC_RE.search(body)
        mod_m = _MOD_RE.search(body)
        if not loc_m or not mod_m:
            continue
        url     = loc_m.group(1).decode().strip()
        mod_raw = mod_m.group(1).decode().strip().replace("Z", "+00:00")
        try:
            mod = datetime.fromisoformat(mod_raw)
            if mod.tzinfo is None:
                mod = mod.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        results.append((url, mod))
    return results


# Fetch one article page via proxy rotation; return (ok, content, attempts_used)
def _fetch_article(
    url: str, pool: list, cm: PersistentCooldownManager, max_tries: int
) -> tuple[bool, bytes, int]:
    candidates = cm.eligible_candidates(pool)
    for i, (proto, hp) in enumerate(candidates[:max_tries]):
        ok, content = fetch_url(proto, hp, url, "html")
        if ok:
            return True, content, i + 1
        cm.mark_burned(proto, hp)
    return False, b"", min(max_tries, len(candidates))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="48h article delta probe: theblock.co post sitemaps → raw HTML fetch"
    )
    parser.add_argument(
        "--hours", type=float, default=48.0,
        help="Lookback window in hours (default: 48)",
    )
    parser.add_argument(
        "--max_article_tries", type=int, default=MAX_ARTICLE_TRIES,
        help=f"Max proxy attempts per article page fetch (default: {MAX_ARTICLE_TRIES})",
    )
    args = parser.parse_args()
    probe_48h_article_fetch_workflow(hours=args.hours, max_article_tries=args.max_article_tries)
