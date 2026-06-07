# INFRASTRUCTURE
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# FUNCTIONS

@dataclass
class ScrapeConfig:
    download_delay: float = 1.0
    concurrency_per_domain: int = 8
    page_timeout_ms: int = 15000
    delay_before_return_html: float = 0.5


@runtime_checkable
class Platform(Protocol):
    name: str                   # --source value AND filename prefix f"{name}__"
    collection: str             # target RAG collection; CoinDesk -> "searxng_crypto"
    precondition_url: str       # internet-check URL; CoinDesk -> "https://www.coindesk.com"
    regwall_signals: list[str]  # precise match strings; [] = guard disabled
    scrape_config: ScrapeConfig

    async def discover(self) -> list[dict]: ...         # [{url,lastmod,publication_date,title,section}, ...]
    def cleanup(self, raw_markdown: str, entry: dict) -> str: ...  # strip chrome -> pure body
