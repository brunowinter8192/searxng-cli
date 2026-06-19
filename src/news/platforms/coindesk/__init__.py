# INFRASTRUCTURE
from src.news.platform import ScrapeConfig
from src.news.registry import register
from src.news.engine.proxy_riding.scrape import RidingScrapeConfig
from src.news.platforms.coindesk.config import REGWALL_SIGNALS, SCRAPE_CONFIG, INVENTORY_DIR
# From coindesk/discover.py: discover(timeframe) -> list[dict]
from src.news.platforms.coindesk.discover import discover as _discover
# From coindesk/discover.py: load_inventory_filtered(dir, year, from_date, to_date, limit) -> list[dict]
from src.news.platforms.coindesk.discover import load_inventory_filtered as _load_filtered
# From coindesk/cleanup.py: cleanup(raw_markdown, entry) -> str
from src.news.platforms.coindesk.cleanup import cleanup as _cleanup


# FUNCTIONS

class CoinDeskPlatform:
    name: str = "coindesk"
    collection: str = "coindesk"
    precondition_url: str = "https://www.coindesk.com"
    regwall_signals: list[str] = REGWALL_SIGNALS
    scrape_engine: str = "proxy_riding"
    scrape_config: ScrapeConfig = SCRAPE_CONFIG
    proxy_scrape_config = None
    riding_scrape_config = RidingScrapeConfig()
    timeframe: str = "30"   # set by __main__ via --timeframe; "full" or int-string N-days

    async def discover(self) -> list[dict]:
        return await _discover(self.timeframe)

    # Return inventory entries filtered by year or date range; [{url, publication_date}].
    def load_scrape_entries(
        self,
        year: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return _load_filtered(INVENTORY_DIR, year=year, from_date=from_date, to_date=to_date, limit=limit)

    def cleanup(self, raw_markdown: str, entry: dict) -> str:
        return _cleanup(raw_markdown, entry)


register(CoinDeskPlatform())
