# INFRASTRUCTURE

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from p2_cooldown import PersistentCooldownManager
from p3_target import build_sitemap_target, _LOC_RE
from p4_loop import run_loop, DEFAULT_MAX_WALL_S, REFRESH_INTERVAL_S
from p5_logger import AcquireLogger
from p6_buffer import BUFFER_SIZE, DEFAULT_CONCURRENCY

sys.path.insert(0, str(Path(__file__).parent.parent))
from curated_sources import load_curated_proxies, load_backfill_pool

ACQUIRE_BASE      = Path(__file__).parent
OUTPUT_DIR        = ACQUIRE_BASE / "acquire_pipe_output"
LOG_DIR           = ACQUIRE_BASE / "acquire_pipe_logs"
REPORT_DIR        = ACQUIRE_BASE / "acquire_pipe_reports"
ARTICLE_URLS_FILE = OUTPUT_DIR / "theblock_article_urls.txt"


# ORCHESTRATOR

def acquire_pipe_workflow(
    concurrency: int,
    buffer_size: int,
    max_wall_s: float,
    pool_name: str,
) -> None:
    """Sustained acquire-pipe: sitemap → 64 sub-sitemaps → ~27k article URLs.

    Uses persistent cooldown (proxy_status_log.json cooled_at), active buffer of
    buffer_size eligible proxies, 60-min pool refresh, wait-on-exhaustion, and a
    hard safety cap of max_wall_s seconds.
    """
    cm        = PersistentCooldownManager()
    pool_fn   = load_backfill_pool if pool_name == "backfill" else load_curated_proxies

    print(f"[acquire_pipe] Building sitemap target...")
    target_urls = build_sitemap_target()
    print(f"[acquire_pipe] Target: {len(target_urls)} sub-sitemaps")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    loc_urls: list[str] = []
    logger = AcquireLogger(total_urls=len(target_urls), log_dir=LOG_DIR)

    def content_handler(url: str, content: bytes) -> None:
        fname = OUTPUT_DIR / _url_to_filename(url)
        fname.write_bytes(b"<!-- source: " + url.encode() + b" -->\n" + content)
        for m in _LOC_RE.finditer(content):
            loc_urls.append(m.group(1).decode().strip())

    print(
        f"[acquire_pipe] Starting sustained loop "
        f"(concurrency={concurrency}, buffer={buffer_size}, "
        f"max_hours={max_wall_s/3600:.2f}, pool={pool_name})..."
    )
    done, gap = run_loop(
        pool_fn, target_urls, "xml", logger, cm,
        concurrency=concurrency,
        buffer_size=buffer_size,
        content_handler=content_handler,
        max_wall_s=max_wall_s,
    )
    print(f"[acquire_pipe] Loop done: {len(done)} completed, {len(gap)} remaining")

    article_urls = list(dict.fromkeys(loc_urls))
    ARTICLE_URLS_FILE.write_text("\n".join(article_urls) + "\n", encoding="utf-8")
    print(f"[acquire_pipe] Article URLs: {len(article_urls)} unique → {ARTICLE_URLS_FILE}")

    md_path = logger.finalize(REPORT_DIR)
    print(f"[acquire_pipe] Report: {md_path}")

    if gap:
        print(f"[acquire_pipe] {len(gap)} sub-sitemaps incomplete (safety cap or exhaustion)")


# FUNCTIONS

# Slugify sub-sitemap URL into safe filename with .xml extension
def _url_to_filename(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "_", url.split("://")[-1])
    slug = re.sub(r"_+", "_", slug).strip("_")[:100]
    return f"{slug}.xml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Acquire-pipe (sustained): sitemap dev-run → ~27k article URLs"
    )
    parser.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        help=f"Concurrent (proxy, URL) pairs per batch (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--buffer_size", type=int, default=BUFFER_SIZE,
        help=f"Active proxy buffer depth (default: {BUFFER_SIZE})",
    )
    parser.add_argument(
        "--max_hours", type=float, default=DEFAULT_MAX_WALL_S / 3600,
        help=f"Hard wall-time safety cap in hours (default: {DEFAULT_MAX_WALL_S/3600:.0f})",
    )
    parser.add_argument(
        "--pool", choices=["curated", "backfill"], default="curated",
        help="Proxy pool: curated (monosans+proxifly ~3.5k) or backfill (top-13 ~22k, default: curated)",
    )
    args = parser.parse_args()
    acquire_pipe_workflow(
        concurrency=args.concurrency,
        buffer_size=args.buffer_size,
        max_wall_s=args.max_hours * 3600,
        pool_name=args.pool,
    )
