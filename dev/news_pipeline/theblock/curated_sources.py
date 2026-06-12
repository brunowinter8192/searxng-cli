#!/usr/bin/env python3
# Unified curated proxy source: monosans + proxifly, merged and deduped.
# Standalone eval sources: TheSpeedX, databay-labs, jetkai, roosterkid.

# INFRASTRUCTURE

import re
import httpx

from monosans_loader import load_monosans_proxies
from proxy_status_log import proxy_key

PROXIFLY_URL      = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json"
FETCH_TIMEOUT     = 15.0

# (proto, url) pairs — multi-entry per proto allowed (jetkai http+https both → "http")
THESPEEDX_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
]
DATABAY_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks5.txt"),
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

_IP_PORT_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}:\d+")

# ORCHESTRATOR

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


def load_databay_proxies() -> list[tuple[str, str]]:
    """Fetch databay-labs http/socks4/socks5 bare txt files; dedup; return [(protocol, host:port)]."""
    entries: list[tuple[str, str]] = []
    for proto, url in DATABAY_SOURCES:
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

# FUNCTIONS

def _fetch_proxifly() -> list[tuple[str, str]]:
    """Fetch proxifly all/data.json; return [(protocol, host:port)]."""
    resp = httpx.get(PROXIFLY_URL, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return [(e["protocol"], f"{e['ip']}:{e['port']}") for e in resp.json()]


def _fetch_bare_txt(proto: str, url: str) -> list[tuple[str, str]]:
    """Fetch one bare host:port txt file (one entry per line); return [(proto, host:port)]."""
    resp = httpx.get(url, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    entries: list[tuple[str, str]] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if line:
            entries.append((proto, line))
    return entries


def _fetch_roosterkid(proto: str, url: str) -> list[tuple[str, str]]:
    """Fetch roosterkid decorated txt; regex-extract IP:PORT; skip header/metadata lines."""
    resp = httpx.get(url, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    entries: list[tuple[str, str]] = []
    for line in resp.text.splitlines():
        m = _IP_PORT_RE.search(line)
        if m:
            entries.append((proto, m.group()))
    return entries


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
