# INFRASTRUCTURE
import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
import pydoll.exceptions as _pydoll_exc
import websockets.exceptions as _ws_exc
from mcp.types import TextContent

from src.search.browser import close_browser
from src.search.cache import cache_key, cache_write
from src.search.engines.google import GoogleEngine
from src.search.preview import fetch_previews
from src.search.engines.scholar import ScholarEngine
from src.search.engines.crossref import CrossRefEngine
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.engines.mojeek import MojeekEngine
from src.search.engines.lobsters import LobstersEngine
from src.search.engines.openalex import OpenAlexEngine
from src.search.engines.stack_exchange import StackExchangeEngine
from src.search.engines.semantic_scholar import SemanticScholarEngine
from src.search.engines.open_library import OpenLibraryEngine
from src.search.rate_limiter import get_limiter
from src.search.result import SearchResult
# From snippet.py: score-based snippet selection
from src.search.snippet import _select_snippet
# From merge.py: URL-merge and slot allocation
from src.search.merge import _merge_and_rank
# From status.py: sub-status string constants
from src.search import status as S
# From query_logger.py: append-only JSONL query log
from src.search.query_logger import log_query
# From book_whitelist.py: domain whitelist + path rules for --books mode
from src.search.book_whitelist import is_book_url
# From pdf_filter.py: PDF host whitelist + path rules for --pdf mode
from src.search.pdf_filter import is_pdf_url
# From docs_filter.py: noise blacklist for --docs mode
from src.search.docs_filter import is_docs_url

logger = logging.getLogger(__name__)

SNIPPET_LENGTH = 5000
ENGINE_WATCHDOG_TIMEOUT: float = 3.6
RATE_WAIT_TIMEOUT: float = 5.0
ENGINE_WATCHDOG_OVERRIDE: dict[str, float] = {
    "open_library": 6.0,        # Server-dominated 1.4-5.8s latency; 3.6s cap caused ~35% timeouts
    "semantic_scholar": 5.0,    # CSR hydration 0.5-2.5s + go_to budget post-DOM-drift fix
    "crossref": 6.0,            # API response 1-5s range; 3.6s httpx cap races watchdog deadline
}

# Empirical per-engine ceilings (max_results_probe_20260507_024429.md)
ENGINE_MAX_RESULTS: dict[str, int] = {
    "google": 100,          # server cap via num= URL param; DOM renders ~9-11
    "google_scholar": 20,   # Scholar renders max ~20 per page
    "duckduckgo": 10,       # no count param; post-fetch DOM slice only
    "mojeek": 10,           # no count param; post-fetch DOM slice only
    "lobsters": 20,         # no count param; pool is query-dependent
    "openalex": 200,        # per_page= API param; documented max 200
    "crossref": 200,        # rows= API param; documented max 1000, practical 200
    "stack_exchange": 100,  # pagesize= API param; hard cap 100
    "semantic_scholar": 10, # 10/page hardcoded by SS UI; no override param
    "open_library": 100,   # limit= API param; supports 1000+ but latency server-dominated (1.4-5.8s at 100)
}

ENGINES = {
    "google": GoogleEngine(),
    "google scholar": ScholarEngine(),
    "crossref": CrossRefEngine(),
    "duckduckgo": DuckDuckGoEngine(),
    "mojeek": MojeekEngine(),
    "lobsters": LobstersEngine(),
    "openalex": OpenAlexEngine(),
    "stack_exchange": StackExchangeEngine(),
    "semantic_scholar": SemanticScholarEngine(),
    "open_library": OpenLibraryEngine(),
}

# --books mode: restrict to general-web engines + Open Library catalog, append '+book' modifier to web engines
_BOOKS_ENGINES = frozenset({"google", "duckduckgo", "mojeek", "open_library"})
_BOOKS_MODIFIER: Callable[[str], str] = lambda q: f"{q} book"

# --pdf mode: restrict to PDF-rich engines and append ' pdf' modifier; post-filter via is_pdf_url
# Engine selection rationale (free_word_injection_probe_20260507_033631.md):
#   google/ddg/mojeek → surface direct .pdf file URLs; scholar → arxiv.org/abs/ (TIER1 transform)
#   crossref/openalex dropped: return doi.org-only results, 0 yield after is_pdf_url filter
_PDF_ENGINES = frozenset({"google", "duckduckgo", "mojeek", "google scholar"})
_PDF_MODIFIER: Callable[[str], str] = lambda q: f"{q} pdf"

# --docs mode: restrict to general-web engines, append 'documentation' modifier, post-filter via is_docs_url
# Pure blacklist: blocks known noise (forums, blogs, code-hosting, tutorial sites), passes everything else
_DOCS_ENGINES = frozenset({"google", "duckduckgo", "mojeek"})
_DOCS_MODIFIER: Callable[[str], str] = lambda q: f"{q} documentation"


# ORCHESTRATOR

# Search all enabled engines concurrently, merge+rank, preview, format, cache, log, return TextContent
async def search_web_workflow(
    query: str,
    language: str = "en",
    time_range: str | None = None,
    engines: str | None = None,
    _with_timings: bool = False,
    class_filter: frozenset[str] | None = None,
    engine_timeout: float | None = None,
    query_modifier_map: dict[str, Callable[[str], str]] | None = None,
    books: bool = False,
    pdf: bool = False,
    docs: bool = False,
) -> list[TextContent] | tuple[list[TextContent], dict]:
    t_total = time.perf_counter()
    # 3-way mutex: pdf > docs > books (cli enforces mutex; guard here for direct callers)
    if sum([books, pdf, docs]) > 1:
        if pdf:
            logger.warning("Multiple mode flags set — pdf takes precedence; ignoring books/docs")
            books = False
            docs = False
        elif docs:
            logger.warning("Multiple mode flags set — docs takes precedence; ignoring books")
            books = False
    logger.info("Searching: %s (language=%s, books=%s, pdf=%s, docs=%s)", query, language, books, pdf, docs)
    selected = _select_engines(engines)
    if books:
        selected = {k: v for k, v in selected.items() if k in _BOOKS_ENGINES}
        # modifier applies only to web engines — Open Library is already a book catalog
        query_modifier_map = {name: _BOOKS_MODIFIER for name in _BOOKS_ENGINES if name != "open_library"}
    if pdf:
        selected = {k: v for k, v in selected.items() if k in _PDF_ENGINES}
        query_modifier_map = {name: _PDF_MODIFIER for name in _PDF_ENGINES}
    if docs:
        selected = {k: v for k, v in selected.items() if k in _DOCS_ENGINES}
        query_modifier_map = {name: _DOCS_MODIFIER for name in _DOCS_ENGINES}
    effective_timeout = engine_timeout if engine_timeout is not None else ENGINE_WATCHDOG_TIMEOUT

    # Engine fanout phase
    raw_results: list = []
    engine_ms: dict[str, int] = {}
    engine_stats: dict[str, dict] = {}
    t_fanout = time.perf_counter()
    if _with_timings:
        names_and_engines = list(selected.items())
        tasks = [_engine_with_timing(eng, query, language, 10, ENGINE_WATCHDOG_OVERRIDE.get(eng.name, effective_timeout), query_modifier_map=query_modifier_map) for _, eng in names_and_engines]
        timed = await asyncio.gather(*tasks)
        engine_details: dict[str, dict] = {}
        for (name, eng), (eng_results, rate_wait_ms, search_ms, status, drop_reason) in zip(names_and_engines, timed):
            raw_results.extend(eng_results)
            key = name.replace(' ', '_')
            engine_ms[f"engine_{key}_ms"] = search_ms
            engine_details[key] = {"status": status, "ms": search_ms}
            engine_stats[eng.name] = {
                "rate_wait_ms": rate_wait_ms,
                "search_ms": search_ms,
                "status": status,
                "result_count": len(eng_results),
                "drop_reason": drop_reason,
            }
    else:
        raw_results, engine_stats = await _query_engines_concurrent(query, language, 10, selected, query_modifier_map=query_modifier_map)
    engine_fanout_ms = round((time.perf_counter() - t_fanout) * 1000)

    # Merge-rank phase
    t0 = time.perf_counter()
    ranked, slot_counts = _merge_and_rank(raw_results, class_filter=class_filter)
    if books:
        ranked = [r for r in ranked if is_book_url(r.url)]
    if pdf:
        ranked = [r for r in ranked if is_pdf_url(r.url)]
    if docs:
        ranked = [r for r in ranked if is_docs_url(r.url)]
    merge_rank_ms = round((time.perf_counter() - t0) * 1000)

    # Preview phase (before cache_write so snippet_source is og-aware)
    top20, preview_stats = await fetch_previews(ranked[:20])
    preview_ms = preview_stats["total_ms"]

    # Format + snippet selection phase (collects snippet_source + display text per URL)
    t0 = time.perf_counter()
    formatted_text, snippet_sources, snippet_texts = _format_results(query, top20)
    select_snippet_ms = round((time.perf_counter() - t0) * 1000)

    # Build og/meta index from preview-enriched top20 objects (ranked[:20] still has preview=None)
    og_meta = {r.url: r.preview for r in top20 if r.preview}

    # Cache write phase
    key = cache_key(query, language, engines, time_range, class_filter=class_filter,
                    modifier_id="books" if books else ("pdf" if pdf else ("docs" if docs else None)))
    t0 = time.perf_counter()
    cache_write(key, ranked, query, language, engines, time_range,
                snippet_sources=snippet_sources, slot_counts=slot_counts,
                snippet_texts=snippet_texts, og_meta=og_meta)
    cache_write_ms = round((time.perf_counter() - t0) * 1000)

    total_ms = round((time.perf_counter() - t_total) * 1000)

    # Query log
    bottleneck = max(engine_stats, key=lambda k: engine_stats[k]["search_ms"]) if engine_stats else None
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log_query({
        "ts": ts,
        "query": query,
        "language": language,
        "engines_requested": [eng.name for eng in selected.values()],
        "total_wall_ms": total_ms,
        "bottleneck_engine": bottleneck,
        "engines": engine_stats,
        "preview": preview_stats,
    })

    result = [TextContent(type="text", text=formatted_text)]

    if not _with_timings:
        return result
    timings = {
        "engine_fanout_ms": engine_fanout_ms,
        **engine_ms,
        "engine_details": engine_details,
        "merge_rank_ms": merge_rank_ms,
        "preview_ms": preview_ms,
        "select_snippet_ms": select_snippet_ms,
        "cache_write_ms": cache_write_ms,
        "total_ms": total_ms,
    }
    return result, timings


# Run N queries sequentially in shared Chrome, close browser in finally
async def search_batch_workflow(
    queries: list[str],
    language: str = "en",
    time_range: str | None = None,
    engines: str | None = None,
    class_filter: frozenset[str] | None = None,
    query_modifier_map: dict[str, Callable[[str], str]] | None = None,
    books: bool = False,
    pdf: bool = False,
    docs: bool = False,
) -> list[list[TextContent]]:
    results = []
    try:
        for q in queries:
            results.append(await search_web_workflow(
                q, language, time_range, engines,
                class_filter=class_filter,
                query_modifier_map=query_modifier_map,
                books=books,
                pdf=pdf,
                docs=docs,
            ))
    finally:
        await close_browser()
    return results


# Synchronous wrapper for dev scripts — runs event loop internally
def fetch_search_results(
    query: str,
    category: str,
    language: str,
    time_range: str | None,
    engines: str | None,
    pageno: int
) -> list:
    selected = _select_engines(engines)
    results, _ = asyncio.run(_query_engines_concurrent(query, language, 10, selected))
    return [
        {
            "url": r.url,
            "title": r.title,
            "content": r.snippet,
            "engines": [r.engine],
        }
        for r in results
    ]


# FUNCTIONS

# Filter engine registry by comma-separated names param or return all
def _select_engines(engines: str | None) -> dict:
    if not engines:
        return ENGINES
    names = [e.strip().lower() for e in engines.split(",")]
    return {k: v for k, v in ENGINES.items() if k in names}


# Query selected engines concurrently; return (combined_results, engine_stats_dict)
async def _query_engines_concurrent(
    query: str,
    language: str,
    max_results: int,
    selected: dict,
    timeout: float = ENGINE_WATCHDOG_TIMEOUT,
    query_modifier_map: dict[str, Callable[[str], str]] | None = None,
) -> tuple[list, dict[str, dict]]:
    tasks = [
        _engine_with_timing(engine, query, language, max_results, ENGINE_WATCHDOG_OVERRIDE.get(engine.name, timeout), query_modifier_map=query_modifier_map)
        for engine in selected.values()
    ]
    timed = await asyncio.gather(*tasks)
    combined: list = []
    engine_stats: dict[str, dict] = {}
    for engine, (eng_results, rate_wait_ms, search_ms, status, drop_reason) in zip(selected.values(), timed):
        combined.extend(eng_results)
        engine_stats[engine.name] = {
            "rate_wait_ms": rate_wait_ms,
            "search_ms": search_ms,
            "status": status,
            "result_count": len(eng_results),
            "drop_reason": drop_reason,
        }
    return combined, engine_stats


# Wrap single engine search; return (results, rate_wait_ms, search_ms, status, drop_reason)
async def _engine_with_timing(
    engine,
    query: str,
    language: str,
    max_results: int,
    timeout: float | None = None,
    query_modifier_map: dict[str, Callable[[str], str]] | None = None,
) -> tuple[list, int, int, str, str | None]:
    t_before_acquire = time.perf_counter()
    try:
        await asyncio.wait_for(get_limiter(engine.name).acquire(), timeout=RATE_WAIT_TIMEOUT)
    except asyncio.TimeoutError:
        rate_wait_ms = round((time.perf_counter() - t_before_acquire) * 1000)
        return [], rate_wait_ms, 0, S.RATE_SKIP, f"rate_wait > {RATE_WAIT_TIMEOUT}s"
    rate_wait_ms = round((time.perf_counter() - t_before_acquire) * 1000)
    effective_query = query
    if query_modifier_map and engine.name in query_modifier_map:
        effective_query = query_modifier_map[engine.name](query)
    logger.debug("Engine %s effective_query: %s", engine.name, effective_query)
    effective_max = ENGINE_MAX_RESULTS.get(engine.name, max_results)
    t0 = time.perf_counter()
    try:
        if timeout is not None:
            results, empty_reason = await asyncio.wait_for(engine.search_with_reason(effective_query, language, effective_max), timeout=timeout)
        else:
            results, empty_reason = await engine.search_with_reason(effective_query, language, effective_max)
        search_ms = round((time.perf_counter() - t0) * 1000)
        if results:
            return results, rate_wait_ms, search_ms, S.OK, None
        return [], rate_wait_ms, search_ms, empty_reason or S.EMPTY, None
    except asyncio.TimeoutError:
        search_ms = round((time.perf_counter() - t0) * 1000)
        if timeout is not None and search_ms < timeout * 1.2 * 1000:
            sub = S.TIMEOUT_WATCHDOG
        else:
            sub = S.TIMEOUT_NONCOOP
        return [], rate_wait_ms, search_ms, sub, f"asyncio.TimeoutError after {timeout}s watchdog"
    except httpx.TimeoutException as e:
        logger.warning("Engine httpx timeout: %s", e)
        search_ms = round((time.perf_counter() - t0) * 1000)
        return [], rate_wait_ms, search_ms, S.TIMEOUT_HTTPX, str(e)
    except (_pydoll_exc.PydollException, _ws_exc.WebSocketException, ConnectionError) as e:
        logger.warning("Engine browser error: %s", e)
        search_ms = round((time.perf_counter() - t0) * 1000)
        return [], rate_wait_ms, search_ms, S.ERROR_BROWSER, str(e)
    except httpx.HTTPError as e:
        logger.warning("Engine HTTP error: %s", e)
        search_ms = round((time.perf_counter() - t0) * 1000)
        return [], rate_wait_ms, search_ms, S.ERROR_HTTP, str(e)
    except (json.JSONDecodeError, KeyError, ValueError, AttributeError) as e:
        logger.warning("Engine parse error: %s", e)
        search_ms = round((time.perf_counter() - t0) * 1000)
        return [], rate_wait_ms, search_ms, S.ERROR_PARSE, str(e)
    except Exception as e:
        logger.warning("Engine error: %s", e)
        search_ms = round((time.perf_counter() - t0) * 1000)
        return [], rate_wait_ms, search_ms, S.ERROR_OTHER, str(e)


# Format merged SearchResult list as plain text numbered list; returns (text, {url: source}, {url: display_text})
def _format_results(query: str, results: list[SearchResult]) -> tuple[str, dict[str, str], dict[str, str]]:
    if not results:
        return f'No results found for "{query}"', {}, {}
    lines = [f'Found {len(results)} results for "{query}"\n']
    sources: dict[str, str] = {}
    texts:   dict[str, str] = {}
    for idx, r in enumerate(results, 1):
        lines.append(f"{idx}. {r.title}")
        lines.append(f"   URL: {r.url}")
        snippet, source = _select_snippet(r)
        sources[r.url] = source
        texts[r.url]   = snippet
        if snippet:
            lines.append(f"   Snippet: {snippet[:SNIPPET_LENGTH]}")
        lines.append("")
    return "\n".join(lines), sources, texts
