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
# From filter_modes.py: engine restriction, modifier map, URL filter, and default engine set
from src.search.filter_modes import apply_filter_mode, filter_urls_by_mode, _DEFAULT_ENGINES

logger = logging.getLogger(__name__)

SNIPPET_LENGTH = 5000
ENGINE_WATCHDOG_TIMEOUT: float = 3.6
RATE_WAIT_TIMEOUT: float = 5.0
ENGINE_WATCHDOG_OVERRIDE: dict[str, float] = {
    "open_library": 6.0,        # Server-dominated 1.4-5.8s latency; 3.6s cap caused ~35% timeouts
    "semantic_scholar": 5.0,    # CSR hydration 0.5-2.5s + go_to budget post-DOM-drift fix
    "crossref": 6.0,            # API response 1-5s range; 3.6s httpx cap races watchdog deadline
    "google_scholar": 6.0,      # HTTP latency 0.7-5s; 3.6s default would produce TIMEOUT_HTTPX
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
    logger.info("Searching: %s (language=%s, books=%s, pdf=%s, docs=%s)", query, language, books, pdf, docs)
    selected, select_excluded = _select_engines(engines)
    selected, query_modifier_map, mode, mode_excluded = apply_filter_mode(selected, books, pdf, docs, query_modifier_map)
    all_excluded = {**select_excluded, **mode_excluded}
    effective_timeout = engine_timeout if engine_timeout is not None else ENGINE_WATCHDOG_TIMEOUT

    raw_results, engine_stats, engine_fanout_ms, engine_ms, engine_details = await _run_engine_fanout(
        selected, query, language, effective_timeout, query_modifier_map, _with_timings
    )

    t0 = time.perf_counter()
    ranked, slot_counts = _merge_and_rank(raw_results, class_filter=class_filter)
    ranked = filter_urls_by_mode(ranked, mode)
    merge_rank_ms = round((time.perf_counter() - t0) * 1000)

    top20, preview_stats = await fetch_previews(ranked[:20])
    preview_ms = preview_stats["total_ms"]

    t0 = time.perf_counter()
    formatted_text, snippet_sources, snippet_texts = _format_results(query, top20)
    select_snippet_ms = round((time.perf_counter() - t0) * 1000)

    og_meta = {r.url: r.preview for r in top20 if r.preview}

    key = cache_key(query, language, engines, time_range, class_filter=class_filter, modifier_id=mode)
    t0 = time.perf_counter()
    cache_write(key, ranked, query, language, engines, time_range,
                snippet_sources=snippet_sources, slot_counts=slot_counts,
                snippet_texts=snippet_texts, og_meta=og_meta)
    cache_write_ms = round((time.perf_counter() - t0) * 1000)

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _build_query_log_entry(query, language, selected, total_ms, engine_stats, preview_stats, all_excluded)

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
    results: list = []
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
    selected, _ = _select_engines(engines)
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

# Filter engine registry; default path excludes google_scholar (Google co-fire constraint)
# Returns (selected, excluded) — excluded maps engine.name → reason for engines not included
def _select_engines(engines: str | None) -> tuple[dict, dict[str, str]]:
    if not engines:
        selected = {k: v for k, v in ENGINES.items() if k in _DEFAULT_ENGINES}
        return selected, {"google_scholar": "decoupled_from_google"}
    names = [e.strip().lower() for e in engines.split(",")]
    return {k: v for k, v in ENGINES.items() if k in names}, {}


# Execute engine fanout (timed or plain); return (raw_results, engine_stats, fanout_ms, engine_ms, engine_details)
async def _run_engine_fanout(
    selected: dict,
    query: str,
    language: str,
    effective_timeout: float,
    query_modifier_map: dict[str, Callable] | None,
    with_timings: bool,
) -> tuple[list, dict, int, dict, dict]:
    raw_results: list = []
    engine_ms: dict[str, int] = {}
    engine_stats: dict[str, dict] = {}
    t_fanout = time.perf_counter()
    if with_timings:
        names_and_engines = list(selected.items())
        tasks = [
            _engine_with_timing(eng, query, language, 10, ENGINE_WATCHDOG_OVERRIDE.get(eng.name, effective_timeout), query_modifier_map=query_modifier_map)
            for _, eng in names_and_engines
        ]
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
        raw_results, engine_stats = await _query_engines_concurrent(
            query, language, 10, selected, query_modifier_map=query_modifier_map
        )
        engine_details = {}
    engine_fanout_ms = round((time.perf_counter() - t_fanout) * 1000)
    return raw_results, engine_stats, engine_fanout_ms, engine_ms, engine_details


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


# Build and write query log entry after each search_web_workflow call
def _build_query_log_entry(
    query: str,
    language: str,
    selected: dict,
    total_ms: int,
    engine_stats: dict,
    preview_stats: dict,
    engines_excluded: dict[str, str],
) -> None:
    bottleneck = max(engine_stats, key=lambda k: engine_stats[k]["search_ms"]) if engine_stats else None
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log_query({
        "ts": ts,
        "query": query,
        "language": language,
        "engines_requested": [eng.name for eng in selected.values()],
        "engines_excluded": engines_excluded,
        "total_wall_ms": total_ms,
        "bottleneck_engine": bottleneck,
        "engines": engine_stats,
        "preview": preview_stats,
    })
