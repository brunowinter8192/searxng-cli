# INFRASTRUCTURE
import asyncio
import json
import logging
from urllib.parse import quote_plus

from src.search.browser import new_tab
from src.search.engines.base import BaseEngine
from src.search.rate_limiter import RateLimiter, get_limiter, _limiters
from src.search.result import SearchResult
from src.search import status as S

logger = logging.getLogger(__name__)

SEARCH_URL = "https://scholar.google.com/scholar?q={}&hl={}&num={}"
CONSENT_DOMAIN = "consent.google.com"
CAPTCHA_PATH = "/sorry/"
MAX_WAIT_CYCLES = 1
WAIT_INTERVAL = 1.0

_JS_WAIT = "return document.querySelectorAll('div.gs_r.gs_or.gs_scl').length"

_JS_PARSE = """var _n = document.querySelectorAll('div.gs_r.gs_or.gs_scl');
var _o = [];
for (var _i = 0; _i < _n.length; _i++) {
    var _el = _n[_i];
    var _a = _el.querySelector('h3.gs_rt a');
    var _s = _el.querySelector('div.gs_rs');
    if (!_a) continue;
    _o.push({url: _a.href, title: _a.textContent.trim(), snippet: _s ? _s.textContent.trim() : ''});
}
return JSON.stringify(_o)"""

_JS_CONSENT = """
var btn = document.querySelector('button[jsname="b3VHJd"]') ||
           document.querySelector('.lssxud') ||
           document.querySelector('form[action*="consent"] button[type="submit"]') ||
           document.querySelector('button[aria-label*="Accept"]');
if (btn) { btn.click(); return true; }
return false;
"""

# Uniform 4 req/min across all engines (Google-Baseline, normalized 2026-05-04)
_limiters["google_scholar"] = RateLimiter(max_requests=4, window_seconds=60)


# ORCHESTRATOR

# Google Scholar search via pydoll stealth browser
class ScholarEngine(BaseEngine):
    name = "google_scholar"

    # Full search logic with empty-reason diagnosis; exceptions propagate to _engine_with_timing
    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None]:
        logger.info("Scholar search: %s", query)
        limiter = get_limiter(self.name)
        tab = await new_tab()
        search_url = _build_url(query, language, max_results)
        try:
            await tab.go_to(search_url, timeout=3.0)
            current = await tab.current_url
            if CONSENT_DOMAIN in current:
                await _handle_consent(tab)
                await tab.go_to(search_url, timeout=3.0)
                current = await tab.current_url
            if CAPTCHA_PATH in current:
                logger.warning("Scholar CAPTCHA detected for: %s", query)
                limiter.backoff()
                return [], S.EMPTY_BLOCK
            if not await _wait_for_results(tab):
                reason = await _diagnose_empty(tab)
                logger.warning("Scholar empty (%s) for: %s", reason, query)
                return [], reason
            results = await _parse_results(tab, max_results)
            limiter.reset_backoff()
            return results, (None if results else S.EMPTY_NO_RESULTS)
        finally:
            await tab.close()

    # Legacy thin wrapper — delegates to search_with_reason; swallows exceptions for dev-script compat
    async def search(self, query: str, language: str = "en", max_results: int = 10) -> list[SearchResult]:
        try:
            results, _ = await self.search_with_reason(query, language, max_results)
            return results
        except Exception as e:
            logger.error("Scholar search failed: %s", e)
            get_limiter(self.name).backoff()
            return []


# FUNCTIONS

# Extract primitive value from CDP execute_script result dict
def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


# Build Scholar search URL with encoded query
def _build_url(query: str, language: str, max_results: int) -> str:
    return SEARCH_URL.format(quote_plus(query), language, max_results)


# Click consent accept button on consent.google.com
async def _handle_consent(tab) -> None:
    logger.info("Scholar consent page detected — clicking accept")
    await tab.execute_script(_JS_CONSENT)


# Poll for result containers up to MAX_WAIT_CYCLES seconds, return True when found
async def _wait_for_results(tab) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = _extract_value(raw)
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


# Query DOM for Scholar result containers and return SearchResult list
async def _parse_results(tab, max_results: int) -> list[SearchResult]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    try:
        items = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    results = []
    for i, item in enumerate(items[:max_results]):
        url = item.get("url", "")
        if not url:
            continue
        results.append(SearchResult(
            url=url,
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            engine="google_scholar",
            position=i + 1,
        ))
    return results


# Diagnose why Scholar returned empty after _wait_for_results failed; tab is still open
# Priority: BLOCK → CONSENT → CONCURRENT_RACE → NO_CONTAINER
async def _diagnose_empty(tab) -> str:
    title = _extract_value(await tab.execute_script("return document.title.toLowerCase()")) or ""
    url = _extract_value(await tab.execute_script("return window.location.href")) or ""
    if any(x in title for x in ("captcha", "unusual traffic", "are you a bot", "robot")) or "/sorry/" in url:
        return S.EMPTY_BLOCK
    if CONSENT_DOMAIN in url:
        return S.EMPTY_CONSENT
    state = _extract_value(await tab.execute_script("return document.readyState")) or ""
    if state != "complete":
        return S.EMPTY_CONCURRENT_RACE
    return S.EMPTY_NO_CONTAINER
