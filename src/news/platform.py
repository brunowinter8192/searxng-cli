# INFRASTRUCTURE
from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable


# FUNCTIONS

@dataclass
class ProxyScrapeConfig:
    pool_provider: Callable[[], tuple[list[tuple[str, str]], list[dict]]]  # called on startup + 60-min refresh; returns (pool, sources)
    content_type: str = "html"                           # "html" | "xml" — fetch validation gate
    concurrency: int = 128                               # concurrent (proxy, url) pairs per batch
    buffer_size: int = 1280                              # active buffer depth (10× concurrency)


@dataclass
class ScrapeConfig:
    download_delay: float = 1.0
    concurrency_per_domain: int = 8
    page_timeout_ms: int = 15000
    delay_before_return_html: float = 0.5


@runtime_checkable
class Platform(Protocol):
    name: str                   # --source value AND filename prefix f"{name}__"
    collection: str             # target RAG collection; CoinDesk -> "coindesk"
    precondition_url: str       # internet-check URL; CoinDesk -> "https://www.coindesk.com"
    regwall_signals: list[str]  # precise match strings; [] = guard disabled
    scrape_engine: str          # "browser" | "proxy_pool" — selects engine in pipeline.py
    scrape_config: ScrapeConfig
    proxy_scrape_config: "ProxyScrapeConfig | None"  # None for browser platforms

    async def discover(self) -> list[dict]: ...         # [{url,lastmod,publication_date,title,section}, ...]
    def cleanup(self, raw_markdown: str, entry: dict) -> str: ...  # strip chrome -> pure body
