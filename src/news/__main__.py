# INFRASTRUCTURE
import argparse
import asyncio

import src.news.platforms.coindesk  # side-effect: registers CoinDeskPlatform

from src.news.registry import get
from src.news.pipeline import run_pipeline


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
    args = parser.parse_args()

    platform = get(args.source)
    asyncio.run(run_pipeline(platform, skip_index=args.skip_index))


if __name__ == "__main__":
    main()
