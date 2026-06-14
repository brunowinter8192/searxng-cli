# INFRASTRUCTURE

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import box_lock
import p7_janitor as janitor
from p3_target import build_sitemap_target, _LOC_RE
from p4_race import run_race
from p5_logger import AcquireLogger
from p6_buffer import DEFAULT_CONCURRENCY

sys.path.insert(0, str(Path(__file__).parent.parent))
from curated_sources import load_curated_proxies, load_backfill_pool

ACQUIRE_BASE      = Path(__file__).parent
OUTPUT_DIR        = ACQUIRE_BASE / "acquire_pipe_output"
LOG_DIR           = ACQUIRE_BASE / "acquire_pipe_logs"
ARTICLE_URLS_FILE = OUTPUT_DIR / "theblock_article_urls.txt"


# ORCHESTRATOR

def acquire_pipe_workflow(
    concurrency: int,
    pool_name: str,
) -> None:
    """Race acquire-pipe: sitemap → 64 sub-sitemaps → ~27k article URLs.

    One job at a time (box_lock global flock). Each job is a clean slate
    (start_job wipes transient logs). end_job derives the persistent
    job.md + cumulative_hits.png and kills the transient JSONL.
    On LockBusyError → print + sys.exit(1).
    """
    pool_fn = load_backfill_pool if pool_name == "backfill" else load_curated_proxies

    initial_pool = pool_fn()
    print(f"[acquire_pipe] Loaded {pool_name} pool: {len(initial_pool)} proxies")
    print(f"[acquire_pipe] Building sitemap target...")
    target_urls = build_sitemap_target(pool=initial_pool)
    print(f"[acquire_pipe] Target: {len(target_urls)} sub-sitemaps")

    job_id      = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_desc = f"theblock-{pool_name}-{len(target_urls)}"

    try:
        with box_lock.acquire(job_id, target_desc):
            janitor.start_job(job_id)

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            loc_urls: list[str] = []
            logger = AcquireLogger(total_urls=len(target_urls), log_dir=LOG_DIR)
            logger.record_pool_refresh(len(initial_pool))

            def content_handler(url: str, content: bytes) -> None:
                fname = OUTPUT_DIR / _url_to_filename(url)
                fname.write_bytes(b"<!-- source: " + url.encode() + b" -->\n" + content)
                for m in _LOC_RE.finditer(content):
                    loc_urls.append(m.group(1).decode().strip())

            print(f"[acquire_pipe] Starting race loop (concurrency={concurrency}, pool={pool_name})...")
            done, gap = run_race(
                initial_pool, target_urls, "xml", logger,
                content_handler=content_handler,
                concurrency=concurrency,
            )
            print(f"[acquire_pipe] Loop done: {len(done)} completed, {len(gap)} remaining")

            article_urls = list(dict.fromkeys(loc_urls))
            ARTICLE_URLS_FILE.write_text("\n".join(article_urls) + "\n", encoding="utf-8")
            print(f"[acquire_pipe] Article URLs: {len(article_urls)} unique → {ARTICLE_URLS_FILE}")

            logger.close()
            janitor.end_job(job_id, logger._jsonl_path, len(target_urls), len(done))
            print(f"[acquire_pipe] Job report: acquire_pipe_jobs/{job_id}/")

            if gap:
                print(f"[acquire_pipe] {len(gap)} sub-sitemaps incomplete (safety cap or exhaustion)")

    except box_lock.LockBusyError as e:
        print(e)
        sys.exit(1)


# FUNCTIONS

# Slugify sub-sitemap URL into safe filename with .xml extension
def _url_to_filename(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "_", url.split("://")[-1])
    slug = re.sub(r"_+", "_", slug).strip("_")[:100]
    return f"{slug}.xml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Acquire-pipe (race): sitemap dev-run → ~27k article URLs"
    )
    parser.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        help=f"Concurrent worker threads (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--pool", choices=["curated", "backfill"], default="backfill",
        help="Proxy pool: curated (monosans+proxifly ~3.5k) or backfill (top-13 ~22k, default: backfill)",
    )
    args = parser.parse_args()
    acquire_pipe_workflow(
        concurrency=args.concurrency,
        pool_name=args.pool,
    )
