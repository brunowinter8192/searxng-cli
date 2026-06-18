# INFRASTRUCTURE

import argparse
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p0_pool import PersistentCooldownManager
from p1_alive_feeder import AliveFeeder, FEEDER_QUEUE_MAXSIZE
from p2_browser_rider import run_riding_pool
from p3_url_sampler import sample_urls
from p4_reporter import write_riding_report


# ORCHESTRATOR

async def _run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    urls = sample_urls(args.n_urls)
    if not urls:
        print(
            f"[main] FATAL: sample_urls({args.n_urls}) returned 0 URLs.\n"
            f"  INVENTORY_DIR resolution failed — check p3_url_sampler._repo_root().\n"
            f"  Expected: data/news/coindesk/inventory/ under repo root.",
            file=sys.stderr,
        )
        sys.exit(1)

    url_queue = asyncio.Queue()
    for u in urls:
        url_queue.put_nowait(u)
    print(f"[main] {len(urls)} URLs queued, concurrency={args.concurrency}, "
          f"burn-threshold={args.burn_threshold}", file=sys.stderr)

    cm          = PersistentCooldownManager()
    proxy_queue = asyncio.Queue(maxsize=FEEDER_QUEUE_MAXSIZE)
    feeder      = AliveFeeder(proxy_queue=proxy_queue, cm=cm)
    feeder_task = asyncio.create_task(feeder.run())

    t_job_start = datetime.now(timezone.utc)
    t0          = time.monotonic()

    try:
        state = await run_riding_pool(
            url_queue=url_queue,
            proxy_queue=proxy_queue,
            cooldown_mgr=cm,
            output_dir=output_dir,
            burn_threshold=args.burn_threshold,
            n_slots=args.concurrency,
        )
    finally:
        feeder.stop()
        feeder_task.cancel()
        try:
            await feeder_task
        except asyncio.CancelledError:
            pass

    elapsed = time.monotonic() - t0
    print(
        f"[main] done in {elapsed:.0f}s — "
        f"ok={state.n_ok} rw={state.n_regwall} fail={state.n_failed} "
        f"cf={state.n_connect_fail} termination={state.termination}",
        file=sys.stderr,
    )

    write_riding_report(state, output_dir, t_job_start)
    print(f"[main] report → {output_dir / 'job.md'}")


# FUNCTIONS

# Parse CLI arguments.
def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="CoinDesk browser-proxy riding scraper")
    ap.add_argument("--concurrency",    type=int, default=20,      help="Browser slots (default 20)")
    ap.add_argument("--burn-threshold", type=int, default=2,       help="Regwall hits before proxy rotate (default 2)")
    ap.add_argument("--n-urls",         type=int, default=500,     help="URLs to scrape (default 500)")
    ap.add_argument("--output-dir",     default="output",          help="Output directory for raw HTML + report")
    return ap.parse_args()


if __name__ == "__main__":
    asyncio.run(_run(_parse_args()))
