# INFRASTRUCTURE

import re

import httpx

from src.news.engine.proxy_pool.monosans_loader import load_monosans_proxies, MONOSANS_URL
from src.news.engine.proxy_pool.pool_retry import fetch_with_retry
from src.news.engine.proxy_pool.proxy_key import proxy_key

PROXIFLY_URL = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json"
FETCH_TIMEOUT = 15.0

# (proto, url) pairs — multi-entry per proto allowed (jetkai http+https both → "http")
THESPEEDX_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
]
JETKAI_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt"),
    ("http",   "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt"),
    ("socks4", "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt"),
]
ROOSTERKID_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS.txt"),
    ("socks4", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4.txt"),
    ("socks5", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5.txt"),
]
THEMIRALAY_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/themiralay/Proxy-List-World/master/data.txt"),
]
R00TEE_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Https.txt"),
    ("socks4", "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks5.txt"),
]
IPLOCATE_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt"),
    ("http",   "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/https.txt"),
    ("socks4", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt"),
]
SUNNY9577_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt"),
    ("socks4", "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks4_proxies.txt"),
    ("socks5", "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks5_proxies.txt"),
]
ALIILAPRO_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt"),
]
DPANGESTUW_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/http_proxies.txt"),
    ("socks4", "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks4_proxies.txt"),
    ("socks5", "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks5_proxies.txt"),
]
ZAEEM20_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt"),
    ("http",   "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt"),
    ("socks4", "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt"),
]
ZLOI_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt"),
    ("http",   "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt"),
    ("socks4", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt"),
]
HOOKZOF_SOURCES: list[tuple[str, str]] = [
    ("socks5", "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"),
]

_IP_PORT_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}:\d+")


# ORCHESTRATOR

# Fetch all active sources per-URL with retry + isolation; return (deduped pool, source results)
def load_backfill_pool() -> tuple[list[tuple[str, str]], list[dict]]:
    """Fetch all active sources; merge, dedup; return (pool, sources).

    Sources (17): monosans, roosterkid, TheSpeedX, themiralay, r00tee, iplocate,
    sunny9577, ALIILAPRO, dpangestuw, Zaeem20, zloi-user, hookzof,
    proxifly (JSON), jetkai (http/https/socks4/socks5),
    prxchk (http/socks5), ShiftyTR (http/socks5), vakhov (http/socks5).
    databay-labs removed (repo deleted from GitHub — 404 on all URLs).
    Target: ~30k+ unique.

    Each URL is fetched independently with exponential-backoff retry (pool_retry).
    A source that still fails after all retries is recorded as ok=False in sources
    and skipped — never raises. sources: [{url, ok, count}] one entry per URL.
    """
    entries: list[tuple[str, str]] = []
    sources: list[dict]            = []

    _try_source(MONOSANS_URL, load_monosans_proxies, entries, sources)

    for proto, url in ROOSTERKID_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in THESPEEDX_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_bare_txt(p, u), entries, sources)
    for proto, url in THEMIRALAY_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in R00TEE_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in IPLOCATE_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in SUNNY9577_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in ALIILAPRO_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in DPANGESTUW_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in ZAEEM20_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in ZLOI_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in HOOKZOF_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)

    _try_source(PROXIFLY_URL, _fetch_proxifly, entries, sources)
    for proto, url in JETKAI_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_bare_txt(p, u), entries, sources)

    return _merge_dedup(entries), sources


# FUNCTIONS

def load_curated_proxies() -> list[tuple[str, str]]:
    """Fetch monosans + proxifly, merge, dedup; return [(protocol, host:port)]."""
    monosans = load_monosans_proxies()
    proxifly = _fetch_proxifly()
    return _merge_dedup(monosans + proxifly)


def load_thespeedx_proxies() -> list[tuple[str, str]]:
    """Fetch TheSpeedX http/socks4/socks5 bare txt files; dedup; return [(protocol, host:port)]."""
    entries: list[tuple[str, str]] = []
    for proto, url in THESPEEDX_SOURCES:
        entries.extend(_fetch_bare_txt(proto, url))
    return _merge_dedup(entries)


def load_jetkai_proxies() -> list[tuple[str, str]]:
    """Fetch jetkai http/https/socks4/socks5 bare txt files (https→http); dedup; return [(protocol, host:port)]."""
    entries: list[tuple[str, str]] = []
    for proto, url in JETKAI_SOURCES:
        entries.extend(_fetch_bare_txt(proto, url))
    return _merge_dedup(entries)


def load_roosterkid_proxies() -> list[tuple[str, str]]:
    """Fetch roosterkid HTTPS/SOCKS4/SOCKS5 decorated txt files; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in ROOSTERKID_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_themiralay_proxies() -> list[tuple[str, str]]:
    """Fetch themiralay/Proxy-List-World http bare txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in THEMIRALAY_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_r00tee_proxies() -> list[tuple[str, str]]:
    """Fetch r00tee/Proxy-List http/socks4/socks5 bare txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in R00TEE_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_iplocate_proxies() -> list[tuple[str, str]]:
    """Fetch iplocate/free-proxy-list http/socks4/socks5 bare txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in IPLOCATE_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_sunny9577_proxies() -> list[tuple[str, str]]:
    """Fetch sunny9577/proxy-scraper http/socks4/socks5 generated txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in SUNNY9577_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_aliilapro_proxies() -> list[tuple[str, str]]:
    """Fetch ALIILAPRO/Proxy http/socks4/socks5 bare txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in ALIILAPRO_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_dpangestuw_proxies() -> list[tuple[str, str]]:
    """Fetch dpangestuw/Free-Proxy http/socks4/socks5 scheme-prefixed txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in DPANGESTUW_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_zaeem20_proxies() -> list[tuple[str, str]]:
    """Fetch Zaeem20/FREE_PROXIES_LIST http/socks4/socks5 bare txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in ZAEEM20_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_zloi_proxies() -> list[tuple[str, str]]:
    """Fetch zloi-user/hideip.me http/socks4/socks5 decorated txt; regex-parse; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in ZLOI_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_hookzof_proxies() -> list[tuple[str, str]]:
    """Fetch hookzof/socks5_list socks5 bare txt; regex-parse IP:PORT; dedup."""
    entries: list[tuple[str, str]] = []
    for proto, url in HOOKZOF_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def _fetch_proxifly() -> list[tuple[str, str]]:
    """Fetch proxifly all/data.json; return [(protocol, host:port)]. Retried on transient failure."""
    def _do():
        resp = httpx.get(PROXIFLY_URL, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(e["protocol"], f"{e['ip']}:{e['port']}") for e in resp.json()]
    return fetch_with_retry(_do)


def _fetch_bare_txt(proto: str, url: str) -> list[tuple[str, str]]:
    """Fetch one bare host:port txt file (one entry per line); return [(proto, host:port)]. Retried."""
    def _do():
        resp = httpx.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, line.strip()) for line in resp.text.splitlines() if line.strip()]
    return fetch_with_retry(_do)


def _fetch_roosterkid(proto: str, url: str) -> list[tuple[str, str]]:
    """Fetch roosterkid decorated txt; regex-extract IP:PORT; skip header/metadata lines. Retried."""
    def _do():
        resp = httpx.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, m.group()) for line in resp.text.splitlines()
                for m in (_IP_PORT_RE.search(line),) if m]
    return fetch_with_retry(_do)


# Fetch one source URL via fn(); append to entries on success; record {url, ok, count} in sources
def _try_source(url: str, fn, entries: list, sources: list) -> None:
    """Call fn() (internally retried); on final failure record ok=False and continue — never raises."""
    try:
        result = fn()
        entries.extend(result)
        sources.append({"url": url, "ok": True, "count": len(result)})
    except Exception:
        sources.append({"url": url, "ok": False, "count": 0})


def _merge_dedup(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Deduplicate entries by canonical proxy_key; first occurrence wins."""
    seen:   set[str]              = set()
    result: list[tuple[str, str]] = []
    for proto, host_port in entries:
        key = proxy_key(proto, host_port)
        if key not in seen:
            seen.add(key)
            result.append((proto, host_port))
    return result
