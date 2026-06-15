# INFRASTRUCTURE
import json
import re
import sys

from crawl4ai.html2text import HTML2Text

_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


# FUNCTIONS

# Parse JSON-LD NewsArticle from raw HTML → articleBody→Markdown; mutate entry['publication_date'].
# Fallback: empty string + stderr log on missing JSON-LD or missing articleBody (no crash).
def cleanup(raw_html: str, entry: dict) -> str:
    data = _find_news_article(raw_html)
    if data is None:
        print(f"[theblock] cleanup: no JSON-LD NewsArticle found — {entry.get('url','?')}", file=sys.stderr)
        return ""

    article_body = data.get("articleBody", "")
    if not article_body:
        print(f"[theblock] cleanup: empty articleBody — {entry.get('url','?')}", file=sys.stderr)
        return ""

    pub_date = data.get("datePublished", "")
    if pub_date:
        entry["publication_date"] = pub_date

    return _html_to_markdown(article_body)


# Return first JSON-LD block whose @type is or includes "NewsArticle"; None if not found.
# Handles all common JSON-LD shapes without crashing:
#   plain dict           → checked directly
#   dict with @graph     → container dict + each @graph item checked
#   top-level list       → each list item checked
#   non-dict (int/str/…) → skipped silently
def _find_news_article(html: str) -> dict | None:
    for raw in _LD_RE.findall(html):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        for candidate in _iter_candidates(data):
            if _is_news_article(candidate):
                return candidate
    return None


# Yield all dict candidates from one parsed JSON-LD value (flat 2-level scan).
def _iter_candidates(data) -> object:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                if isinstance(item, dict):
                    yield item


# True if data['@type'] is "NewsArticle" or a list containing it.
def _is_news_article(data: dict) -> bool:
    t = data.get("@type", "")
    if isinstance(t, list):
        return "NewsArticle" in t
    return t == "NewsArticle"


# Convert HTML fragment to clean Markdown; no line wrapping, images suppressed.
def _html_to_markdown(html: str) -> str:
    h = HTML2Text()
    h.body_width   = 0
    h.ignore_images = True
    return h.handle(html).strip()
