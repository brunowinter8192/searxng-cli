# INFRASTRUCTURE

from curl_cffi import requests as cffi

THEBLOCK_INDEX = "https://www.theblock.co/sitemap_tbco_index.xml"
XML_MARKERS    = (b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>")
HTML_MARKERS   = (b"<html", b"<!DOCTYPE", b"<!doctype")
FETCH_TIMEOUT  = 15


# ORCHESTRATOR

def fetch_url(proto: str, host_port: str, url: str, content_type: str) -> tuple[bool, bytes]:
    """Fetch url through proto://host_port; validate by content_type.

    content_type: "xml" (sitemap gate) | "html" (article gate)
    Returns (ok, content) — content is raw bytes on success, b"" on failure.
    """
    purl = f"{proto}://{host_port}"
    try:
        s = cffi.Session(impersonate="chrome")
        r = s.get(url, proxies={"http": purl, "https": purl}, timeout=FETCH_TIMEOUT)
        return _validate(r, content_type)
    except Exception:
        return False, b""


# FUNCTIONS

# Validate response against content_type gate; return (ok, content)
def _validate(r, content_type: str) -> tuple[bool, bytes]:
    if r.status_code != 200:
        return False, b""
    head = r.content[:500]
    if content_type == "xml":
        ok = any(m in head for m in XML_MARKERS)
    elif content_type == "html":
        ok = any(m in head.lower() for m in HTML_MARKERS)
    else:
        ok = False
    return ok, r.content if ok else b""
