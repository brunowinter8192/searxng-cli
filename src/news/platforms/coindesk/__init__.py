# INFRASTRUCTURE
from src.news.platform import ScrapeConfig
from src.news.registry import register
from src.news.platforms.coindesk.config import REGWALL_SIGNALS, SCRAPE_CONFIG
# From coindesk/discover.py: discover() -> list[dict]
from src.news.platforms.coindesk.discover import discover as _discover
# From coindesk/cleanup.py: cleanup(raw_markdown, entry) -> str
from src.news.platforms.coindesk.cleanup import cleanup as _cleanup


# FUNCTIONS

class CoinDeskPlatform:
    name: str = "coindesk"
    collection: str = "searxng_crypto"
    precondition_url: str = "https://www.coindesk.com"
    regwall_signals: list[str] = REGWALL_SIGNALS
    scrape_engine: str = "browser"
    scrape_config: ScrapeConfig = SCRAPE_CONFIG
    proxy_scrape_config = None

    async def discover(self) -> list[dict]:
        return await _discover()

    def cleanup(self, raw_markdown: str, entry: dict) -> str:
        return _cleanup(raw_markdown, entry)


register(CoinDeskPlatform())
