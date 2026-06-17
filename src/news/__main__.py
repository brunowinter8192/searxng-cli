# INFRASTRUCTURE
import argparse
import asyncio

import src.news.platforms.coindesk   # side-effect: registers CoinDeskPlatform
import src.news.platforms.theblock   # side-effect: registers TheBlockPlatform

from src.news.registry import get
from src.news.pipeline import run_pipeline, run_discover_only


# ORCHESTRATOR
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.news",
        description="News ingestion pipeline — discover, scrape, clean, publish to RAG.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Platform name to run (e.g. coindesk)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        default=False,
        help="Copy articles to collection dir but skip rag-cli index (for testing)",
    )
    parser.add_argument(
        "--timeframe",
        default="delta",
        help=(
            "Discovery timeframe. "
            "CoinDesk: 'full' (backfill to 2018-01-01) or integer N (last N days; default 30). "
            "TheBlock: 'delta' (top-2 subs), 'full' (all subs), 'sub:N', 'sub:A-B'."
        ),
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        default=False,
        help="Run discover + inventory-update only — skip dedup/scrape/clean/publish (CoinDesk).",
    )
    args = parser.parse_args()

    platform = get(args.source)
    skip_index = args.skip_index
    if hasattr(platform, "timeframe"):
        platform.timeframe = args.timeframe
        if args.timeframe != "delta" and not args.discover_only:
            skip_index = True
            print(f"Non-delta timeframe ({args.timeframe!r}) — RAG index auto-skipped.")
            print(f"After review, run: rag-cli index --collection {platform.collection}")

    if args.discover_only:
        asyncio.run(run_discover_only(platform))
    else:
        asyncio.run(run_pipeline(platform, skip_index=skip_index))


if __name__ == "__main__":
    main()
