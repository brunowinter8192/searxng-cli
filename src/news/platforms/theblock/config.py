# INFRASTRUCTURE
from src.news.platform import ProxyScrapeConfig, ScrapeConfig
from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool

SITEMAP_INDEX   = "https://www.theblock.co/sitemap_tbco_index.xml"
DIRECT_TIMEOUT  = 15.0
DEFAULT_TIMEFRAME = "48h"

PROXY_SCRAPE_CONFIG = ProxyScrapeConfig(
    pool_provider=load_backfill_pool,
    content_type="html",
)

SCRAPE_CONFIG = ScrapeConfig()
