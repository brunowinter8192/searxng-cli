# INFRASTRUCTURE
import json
import re
import sys

from crawl4ai.html2text import HTML2Text

_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

_LINK_URL_RE       = re.compile(r'\[([^\]]+)\]\(https?://[^)]+\)')
_DISCLAIMER_RE     = re.compile(r'^Disclaimer: The Block is an independent media outlet.*$', re.MULTILINE)
# Extended to also match old brand name "The Block Crypto, Inc." (2 files in corpus)
_COPYRIGHT_RE      = re.compile(
    r'^©\s*\d{4}\s+(?:The Block Crypto,\s*Inc\.|The Block)\.?\s*All Rights Reserved.*$',
    re.MULTILINE,
)
# Broadened: drop trailing-_ requirement (many CTAs close with "here." not "_")
_NEWSLETTER_CTA_RE = re.compile(r'^_.*subscribe to the .*newsletter.*$', re.MULTILINE)
_BLANK_RUN_RE      = re.compile(r'\n{3,}')

# Stage 1 additions — corpus-verified boilerplate shapes
# TinyMCE bookmark spans that html2text passes through as literal HTML (19 files in corpus)
_MCE_SPAN_RE        = re.compile(r'<span[^>]*data-mce-type[^>]*>.*?</span>', re.DOTALL)
# Commissioned-content disclaimer footer (534 files); optional italic wrapper
_COMMISSIONED_RE    = re.compile(r'^_?This post is commissioned\b.*$', re.MULTILINE)
# Podcast subscribe-CTA line; handles _/*/__ markdown prefix variants (371 files)
_PODCAST_SUB_CTA_RE = re.compile(r'^[*_]*Listen below[,.]?\s+and subscribe to\b.*$', re.MULTILINE)
# Newsletter promo 2-line block: header + subscribe line (99 files)
_NEWSLETTER_PROMO_RE = re.compile(
    r'^\*\*The Block Newsletters[^\n]*\n[^\n]*theblock\.co/newsletters[^\n]*',
    re.MULTILINE,
)
# Campus trial CTA line (44 files); matches with or without trailing period
_CAMPUS_CTA_RE      = re.compile(
    r'^Sign up for a trial today:[^\n]*theblock\.co/campus[^\n]*$',
    re.MULTILINE,
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

    return _post_clean(_html_to_markdown(article_body))


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


# Strip The-Block-specific boilerplate from post-html2text Markdown.
# Order: inline-URL strip first (exposes plain CTA text), MCE spans, then line-level removals, then normalise.
def _post_clean(md: str) -> str:
    md = _LINK_URL_RE.sub(r'\1', md)
    md = _MCE_SPAN_RE.sub('', md)
    md = _DISCLAIMER_RE.sub('', md)
    md = _COPYRIGHT_RE.sub('', md)
    md = _NEWSLETTER_CTA_RE.sub('', md)
    md = _COMMISSIONED_RE.sub('', md)
    md = _PODCAST_SUB_CTA_RE.sub('', md)
    md = _NEWSLETTER_PROMO_RE.sub('', md)
    md = _CAMPUS_CTA_RE.sub('', md)
    lines = [line.rstrip() for line in md.splitlines()]
    md = '\n'.join(lines)
    md = _BLANK_RUN_RE.sub('\n\n', md)
    return md.strip()


# Convert HTML fragment to clean Markdown; no line wrapping, images suppressed.
def _html_to_markdown(html: str) -> str:
    h = HTML2Text()
    h.body_width   = 0
    h.ignore_images = True
    return h.handle(html).strip()
