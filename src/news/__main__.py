# INFRASTRUCTURE
import argparse
import asyncio

import src.news.platforms.coindesk   # side-effect: registers CoinDeskPlatform
import src.news.platforms.theblock   # side-effect: registers TheBlockPlatform

from src.news.registry import get
from src.news.pipeline import run_pipeline, run_discover_only, run_scrape_only


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
        help="Run discover + discover-update only — skip dedup/scrape/clean/publish (CoinDesk).",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        default=False,
        help="Read discover shards, MD-diff, scrape → clean → publish. No discover. (CoinDesk).",
    )
    parser.add_argument(
        "--year",
        default=None,
        help="Scrape URLs from discover shards for one year, e.g. 2018. Mutually exclusive with --from/--to.",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        default=None,
        help="Start date YYYY-MM-DD for discover date range (use with --to).",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        default=None,
        help="End date YYYY-MM-DD for discover date range (use with --from).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap URL count after date filter (quick probe, e.g. --limit 5).",
    )
    args = parser.parse_args()

    platform = get(args.source)
    skip_index = args.skip_index
    if hasattr(platform, "timeframe"):
        platform.timeframe = args.timeframe
        if args.timeframe != "delta" and not args.discover_only and not args.scrape_only:
            skip_index = True
            print(f"Non-delta timeframe ({args.timeframe!r}) — RAG index auto-skipped.")
            print(f"After review, run: rag-cli index --collection {platform.collection}")

    if args.scrape_only:
        if args.year and (args.from_date or args.to_date):
            parser.error("--year and --from/--to are mutually exclusive")
        asyncio.run(run_scrape_only(
            platform,
            year=args.year,
            from_date=args.from_date,
            to_date=args.to_date,
            limit=args.limit,
            skip_index=skip_index,
        ))
    elif args.discover_only:
        asyncio.run(run_discover_only(platform))
    else:
        asyncio.run(run_pipeline(platform, skip_index=skip_index))


if __name__ == "__main__":
    main()
