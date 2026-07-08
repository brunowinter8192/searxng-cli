#!/usr/bin/env python3
"""DDG + Mojeek DOM selector probe — checks coverage of current selectors and alternative containers."""

# INFRASTRUCTURE
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.browser import new_tab, close_browser
from src.search.engines.duckduckgo import (
    _build_url as _ddg_url,
    _wait_for_results as _ddg_wait,
    _extract_value,
)
from src.search.engines.mojeek import (
    _build_url as _mojeek_url,
    _wait_for_results as _mojeek_wait,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"
QUERY = "python asyncio"

# ── DDG JS ──────────────────────────────────────────────────────────────────

_DDG_JS_COUNTS = """
var c = {};

// Current production container selector
c.web_result = document.querySelectorAll('#links > div.web-result').length;

// All divs directly under #links (organic + ads + other blocks)
c.links_direct_div = document.querySelectorAll('#links > div').length;

// Non-web-result blocks inside #links
c.links_non_web_result = document.querySelectorAll('#links > div:not(.web-result)').length;

// Alternative container candidates
c.result__body   = document.querySelectorAll('div.result__body').length;
c.results_links  = document.querySelectorAll('div.results_links').length;
c.result__title  = document.querySelectorAll('div.result__title').length;

// Current title/href selector coverage within web-results
var _wr = document.querySelectorAll('#links > div.web-result');
var _with_h2a = 0, _with_snippet = 0;
for (var _i = 0; _i < _wr.length; _i++) {
    if (_wr[_i].querySelector('h2 a'))          _with_h2a++;
    if (_wr[_i].querySelector('a.result__snippet')) _with_snippet++;
}
c.web_result_with_h2a      = _with_h2a;
c.web_result_with_snippet  = _with_snippet;

// h2 totals anywhere in #links
c.h2_in_links = document.querySelectorAll('#links h2').length;

// result__snippet totals anywhere in #links (current snippet selector)
c.snippet_in_links = document.querySelectorAll('#links a.result__snippet').length;

// Ads / sponsored blocks
c.ads = document.querySelectorAll('.result--ad, .result--sponsored, [data-testid="ad"]').length;

// External links (non-duckduckgo.com)
var _allA = document.querySelectorAll('a[href^="http"]');
var _ext = 0;
for (var _j = 0; _j < _allA.length; _j++) {
    if (_allA[_j].href.indexOf('duckduckgo.com') === -1) _ext++;
}
c.external_links_total = _ext;

return JSON.stringify(c);
"""

# First-N web-result structure (title tag, has-snippet)
_DDG_JS_STRUCTURE = """
var _wr = document.querySelectorAll('#links > div.web-result');
var _out = [];
for (var _i = 0; _i < Math.min(_wr.length, 5); _i++) {
    var _el = _wr[_i];
    var _a  = _el.querySelector('h2 a');
    var _sn = _el.querySelector('a.result__snippet');
    _out.push({
        classes:      _el.className.split(' ').slice(0, 4).join(' '),
        has_h2a:      !!_a,
        title:        _a  ? _a.textContent.trim().slice(0, 55) : null,
        link:         _a  ? _a.href.slice(0, 80) : null,
        has_snippet:  !!_sn,
    });
}
return JSON.stringify(_out);
"""

# ── Mojeek JS ────────────────────────────────────────────────────────────────

_MOJEEK_JS_COUNTS = """
var c = {};

// Current production selectors
c.results_standard_li  = document.querySelectorAll('ul.results-standard > li').length;
c.ob_anchors           = document.querySelectorAll('ul.results-standard > li > a.ob').length;

// Per-li coverage of sub-selectors
var _lis = document.querySelectorAll('ul.results-standard > li');
var _with_ob = 0, _with_h2a = 0, _with_ps = 0;
for (var _i = 0; _i < _lis.length; _i++) {
    if (_lis[_i].querySelector('a.ob'))  _with_ob++;
    if (_lis[_i].querySelector('h2 a'))  _with_h2a++;
    if (_lis[_i].querySelector('p.s'))   _with_ps++;
}
c.li_with_ob  = _with_ob;
c.li_with_h2a = _with_h2a;
c.li_with_ps  = _with_ps;

// How many li lack a.ob (= missed by current wait and parse)
c.li_without_ob = c.results_standard_li - _with_ob;

// ul.results-standard count (expect 1)
c.results_standard_ul = document.querySelectorAll('ul.results-standard').length;

// Other ul blocks that might carry results
c.other_ul = document.querySelectorAll('ul:not(.results-standard)').length;

// Any result-like containers outside ul.results-standard
c.div_result = document.querySelectorAll('div.result').length;

// Pagination links
c.pagination = document.querySelectorAll('.pagination a, a[href*="page="]').length;

// External links (non-mojeek.com)
var _allA = document.querySelectorAll('a[href^="http"]');
var _ext = 0;
for (var _j = 0; _j < _allA.length; _j++) {
    if (_allA[_j].href.indexOf('mojeek.com') === -1) _ext++;
}
c.external_links_total = _ext;

return JSON.stringify(c);
"""

# First-N li structure
_MOJEEK_JS_STRUCTURE = """
var _lis = document.querySelectorAll('ul.results-standard > li');
var _out = [];
for (var _i = 0; _i < Math.min(_lis.length, 5); _i++) {
    var _li  = _lis[_i];
    var _ob  = _li.querySelector('a.ob');
    var _h2a = _li.querySelector('h2 a');
    var _ps  = _li.querySelector('p.s');
    _out.push({
        has_ob:   !!_ob,
        ob_href:  _ob  ? _ob.href.slice(0, 80) : null,
        has_h2a:  !!_h2a,
        title:    _h2a ? _h2a.textContent.trim().slice(0, 55) : null,
        has_ps:   !!_ps,
    });
}
return JSON.stringify(_out);
"""


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== DDG ===", file=sys.stderr)
    ddg_counts, ddg_struct = await probe_engine(
        url=_ddg_url(QUERY),
        wait_fn=_ddg_wait,
        js_counts=_DDG_JS_COUNTS,
        js_structure=_DDG_JS_STRUCTURE,
        name="DDG",
    )

    print("=== Mojeek ===", file=sys.stderr)
    mojeek_counts, mojeek_struct = await probe_engine(
        url=_mojeek_url(QUERY),
        wait_fn=_mojeek_wait,
        js_counts=_MOJEEK_JS_COUNTS,
        js_structure=_MOJEEK_JS_STRUCTURE,
        name="Mojeek",
    )

    report_path = write_report(ddg_counts, ddg_struct, mojeek_counts, mojeek_struct)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

# Open tab, navigate, wait for results, run both JS blocks, close tab
async def probe_engine(url: str, wait_fn, js_counts: str, js_structure: str, name: str) -> tuple[dict, list]:
    tab = await new_tab()
    try:
        print(f"  URL: {url}", file=sys.stderr)
        await tab.go_to(url, timeout=20)
        if not await wait_fn(tab):
            print(f"  WARNING: {name} results did not load", file=sys.stderr)
            return {}, []
        counts = await run_js(tab, js_counts)
        structure = await run_js_list(tab, js_structure)
        print(f"  counts collected", file=sys.stderr)
        return counts, structure
    finally:
        await tab.close()
        await close_browser()


# Execute JS, parse result as dict
async def run_js(tab, js: str) -> dict:
    raw = await tab.execute_script(js)
    val = _extract_value(raw)
    if not val:
        return {}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {}


# Execute JS, parse result as list
async def run_js_list(tab, js: str) -> list:
    raw = await tab.execute_script(js)
    val = _extract_value(raw)
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


# Diagnose DDG counts; return (verdict, detail)
def diagnose_ddg(c: dict) -> tuple[str, str]:
    wr = c.get("web_result", 0)
    h2a = c.get("web_result_with_h2a", 0)
    links_div = c.get("links_direct_div", 0)
    non_wr = c.get("links_non_web_result", 0)
    ext = c.get("external_links_total", 0)
    ads = c.get("ads", 0)

    if wr == h2a and non_wr == 0:
        verdict = "Selector coverage is complete — `#links > div.web-result` captures all organic blocks and `h2 a` matches every one."
        detail = f"All {wr} web-result containers have an `h2 a`. No non-web-result blocks in `#links`. The page-render ceiling ({wr}) is what DDG HTML endpoint returns per page — single page, no count parameter."
    elif h2a < wr:
        verdict = f"`h2 a` misses {wr - h2a} of {wr} web-result containers — those results have a different title structure."
        detail = f"web-result count = {wr}, with-h2a = {h2a}. Delta = {wr - h2a} results have non-h2 title markup."
    elif non_wr > 0:
        verdict = f"`#links > div.web-result` misses {non_wr} non-web-result divs in `#links` (ads={ads})."
        detail = f"Total divs in `#links` = {links_div}, web-result = {wr}, non-web-result = {non_wr}. External links = {ext}."
    else:
        verdict = "Ambiguous — see raw counts."
        detail = f"web_result={wr}, links_direct_div={links_div}, ext_links={ext}"
    return verdict, detail


# Diagnose Mojeek counts; return (verdict, detail)
def diagnose_mojeek(c: dict) -> tuple[str, str]:
    li_total = c.get("results_standard_li", 0)
    ob = c.get("ob_anchors", 0)
    li_ob = c.get("li_with_ob", 0)
    li_h2a = c.get("li_with_h2a", 0)
    li_ps = c.get("li_with_ps", 0)
    without_ob = c.get("li_without_ob", 0)
    ext = c.get("external_links_total", 0)

    if without_ob == 0 and li_h2a == li_total:
        verdict = "Coverage complete — every `li` has `a.ob` and `h2 a`. Current selectors are sound."
        detail = f"All {li_total} li have both `a.ob` and `h2 a`. The 10-result ceiling is Mojeek's default page size — no count parameter is available in the current URL."
    elif without_ob > 0:
        verdict = f"`a.ob` misses {without_ob} of {li_total} li — those items lack the `.ob` class and are invisible to current wait + parse."
        detail = f"li_total={li_total}, li_with_ob={li_ob}, li_without_ob={without_ob}, li_with_h2a={li_h2a}. Switching to `ul.results-standard > li` as the top-level iterator (without filtering on `a.ob`) would recover those results."
    else:
        verdict = "Ambiguous — see raw counts."
        detail = f"li_total={li_total}, ob={ob}, li_with_h2a={li_h2a}, ext_links={ext}"
    return verdict, detail


# Write combined markdown report; return path
def write_report(
    ddg_c: dict, ddg_s: list,
    mojeek_c: dict, mojeek_s: list,
) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"ddg_mojeek_selector_probe_{ts}.md"

    ddg_verdict, ddg_detail = diagnose_ddg(ddg_c)
    mojeek_verdict, mojeek_detail = diagnose_mojeek(mojeek_c)

    DDG_LABELS = [
        ("web_result",              "`#links > div.web-result` — current container"),
        ("links_direct_div",        "`#links > div` — all direct div children"),
        ("links_non_web_result",    "`#links > div:not(.web-result)` — non-organic blocks"),
        ("web_result_with_h2a",     "web-results with `h2 a` (current title selector)"),
        ("web_result_with_snippet", "web-results with `a.result__snippet` (current snippet)"),
        ("h2_in_links",             "`h2` anywhere in `#links`"),
        ("snippet_in_links",        "`a.result__snippet` anywhere in `#links`"),
        ("result__body",            "`div.result__body`"),
        ("results_links",           "`div.results_links`"),
        ("result__title",           "`div.result__title`"),
        ("ads",                     "Ad/sponsored blocks"),
        ("external_links_total",    "External `<a>` total (non-duckduckgo.com)"),
    ]
    MOJEEK_LABELS = [
        ("results_standard_li",  "`ul.results-standard > li` — total result items"),
        ("ob_anchors",           "`ul.results-standard > li > a.ob` — current wait/parse anchor"),
        ("li_with_ob",           "li containing `a.ob`"),
        ("li_without_ob",        "li WITHOUT `a.ob` (missed by current selectors)"),
        ("li_with_h2a",          "li containing `h2 a` (title)"),
        ("li_with_ps",           "li containing `p.s` (snippet)"),
        ("results_standard_ul",  "`ul.results-standard` count"),
        ("other_ul",             "Other `<ul>` elements on page"),
        ("div_result",           "`div.result` containers"),
        ("pagination",           "Pagination links"),
        ("external_links_total", "External `<a>` total (non-mojeek.com)"),
    ]

    lines = [
        f"# DDG + Mojeek DOM Selector Probe — {ts}",
        "",
        f"**Query:** `{QUERY}`",
        "",
        "---",
        "",
        "## DuckDuckGo",
        "",
        f"**URL:** `{_ddg_url(QUERY)}`",
        "",
        "### DOM Counts",
        "",
        "| Selector / Metric | Count |",
        "|-------------------|-------|",
    ]
    for key, label in DDG_LABELS:
        lines.append(f"| {label} | {ddg_c.get(key, 'N/A')} |")

    lines += [
        "",
        "### First-5 web-result Structure",
        "",
        "| # | has h2 a | Title | Link (80ch) | has snippet |",
        "|---|----------|-------|-------------|-------------|",
    ]
    for i, s in enumerate(ddg_s, 1):
        lines.append(
            f"| {i} | {s.get('has_h2a')} | {s.get('title') or ''} | "
            f"{s.get('link') or ''} | {s.get('has_snippet')} |"
        )

    lines += [
        "",
        "### Diagnosis",
        "",
        f"**Verdict:** {ddg_verdict}",
        "",
        ddg_detail,
        "",
        "---",
        "",
        "## Mojeek",
        "",
        f"**URL:** `{_mojeek_url(QUERY)}`",
        "",
        "### DOM Counts",
        "",
        "| Selector / Metric | Count |",
        "|-------------------|-------|",
    ]
    for key, label in MOJEEK_LABELS:
        lines.append(f"| {label} | {mojeek_c.get(key, 'N/A')} |")

    lines += [
        "",
        "### First-5 li Structure",
        "",
        "| # | has a.ob | ob_href (80ch) | has h2 a | Title | has p.s |",
        "|---|----------|---------------|----------|-------|---------|",
    ]
    for i, s in enumerate(mojeek_s, 1):
        lines.append(
            f"| {i} | {s.get('has_ob')} | {s.get('ob_href') or ''} | "
            f"{s.get('has_h2a')} | {s.get('title') or ''} | {s.get('has_ps')} |"
        )

    lines += [
        "",
        "### Diagnosis",
        "",
        f"**Verdict:** {mojeek_verdict}",
        "",
        mojeek_detail,
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    asyncio.run(run_probe())
