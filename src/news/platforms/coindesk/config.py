# INFRASTRUCTURE
from src.news.platform import ScrapeConfig

# Precise regwall signals — do NOT use loose markers (subscribe/register fire on article footers)
REGWALL_SIGNALS: list[str] = [
    "from_regwall",
    "Create a FREE account to continue reading",
    "You've reached your monthly limit",
]

SCRAPE_CONFIG = ScrapeConfig()

# Discovery constants
TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MAX_CLICK_ROUNDS = 8      # safety cap: 8 × ~16 URLs/batch ≈ 128 URLs max
POLL_INTERVAL = 0.5
POLL_MAX = 40             # 20s max wait per click
PRE_48H_THRESHOLD = 3    # stop when this many articles older than 48h are seen
CUTOFF_DAYS = 2           # collect back N days; terminate on articles older than cutoff
