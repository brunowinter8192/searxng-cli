# INFRASTRUCTURE

import argparse
import re
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
from p3_target import build_sitemap_target, _LOC_RE
from p4_loop import run_loop
from p5_logger import AcquireLogger

sys.path.insert(0, str(Path(__file__).parent.parent))
from curated_sources import load_curated_proxies, load_backfill_pool

ACQUIRE_BASE      = Path(__file__).parent
OUTPUT_DIR        = ACQUIRE_BASE / "acquire_pipe_output"
LOG_DIR           = ACQUIRE_BASE / "acquire_pipe_logs"
REPORT_DIR        = ACQUIRE_BASE / "acquire_pipe_reports"
ARTICLE_URLS_FILE = OUTPUT_DIR / "theblock_article_urls.txt"
DEFAULT_CONCURRENCY = 128


# ORCHESTRATOR

def acquire_pipe_workflow(concurrency: int, pool_name: str = "curated") -> None:
    """Stage 5: sitemap dev-run. pool → 64 sub-sitemaps → ~27k article URLs."""
    print(f"[acquire_pipe] Loading proxy pool ({pool_name})...")
    pool = load_backfill_pool() if pool_name == "backfill" else load_curated_proxies()
    print(f"[acquire_pipe] Pool ({pool_name}): {len(pool)} candidates")

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

    print(f"[acquire_pipe] Starting rotation loop (concurrency={concurrency})...")
    done, gap = run_loop(pool, target_urls, "xml", logger, concurrency, content_handler)
    print(f"[acquire_pipe] Loop done: {len(done)} completed, {len(gap)} gap")

    article_urls = list(dict.fromkeys(loc_urls))
    ARTICLE_URLS_FILE.write_text("\n".join(article_urls) + "\n", encoding="utf-8")
    print(f"[acquire_pipe] Article URLs: {len(article_urls)} unique → {ARTICLE_URLS_FILE}")

    md_path = logger.finalize(REPORT_DIR)
    print(f"[acquire_pipe] Report: {md_path}")

    if gap:
        print(f"[acquire_pipe] WARNING: {len(gap)} sub-sitemaps in gap (pool exhausted before completion)")


# FUNCTIONS

# Slugify sub-sitemap URL into safe filename with .xml extension
def _url_to_filename(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "_", url.split("://")[-1])
    slug = re.sub(r"_+", "_", slug).strip("_")[:100]
    return f"{slug}.xml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Acquire-pipe Stage 5: sitemap dev-run — 64 sub-sitemaps → ~27k article URLs"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Concurrent (proxy, URL) pairs per round (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--pool",
        choices=["curated", "backfill"],
        default="curated",
        help="Proxy pool to use: curated (monosans+proxifly ~3.5k) or backfill (top-13 repos ~22k, default: curated)",
    )
    args = parser.parse_args()
    acquire_pipe_workflow(args.concurrency, args.pool)
