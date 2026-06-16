"""Tests for proxy_pool engine: janitor window stats (D3), retry resilience (D1),
and source-list reporting (D2). Tests are self-contained: synthetic JSONL events,
no network, no filesystem state beyond tmp_path.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

import src.news.engine.proxy_pool.pool_retry as pool_retry
from src.news.engine.proxy_pool.janitor import (
    _compute_stats,
    _compute_window_stats,
    _group_pool_sources,
    _parse_ts,
    _write_md,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attempt(proxy: str, url: str, ts: str, result: str = "ok") -> dict:
    return {"proxy_key": proxy, "url": url, "ts": ts, "result": result}


def _refresh(size: int, ts: str) -> dict:
    return {"event": "pool_refresh", "size": size, "ts": ts}


def _write_and_read_md(tmp_path: Path, events: list[dict], target: int = 10, done: int = 5) -> str:
    """Compute stats from events and write job.md; return its text."""
    stats = _compute_stats(events)
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    _write_md(job_dir, "test-job", target, done, stats)
    return (job_dir / "job.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# D3 — _compute_window_stats: urls_handled = distinct, fetch_attempts = total
# ---------------------------------------------------------------------------

def test_urls_handled_is_distinct_urls():
    """urls_handled counts distinct target URLs, not attempt events."""
    # 5 attempt events but only 3 distinct URLs
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    events = [
        _attempt("http://p1:1", "https://target.com/a", "2026-01-01T00:00:01Z"),
        _attempt("http://p2:2", "https://target.com/a", "2026-01-01T00:00:02Z"),  # same URL, 2nd proxy
        _attempt("http://p1:1", "https://target.com/b", "2026-01-01T00:00:03Z"),
        _attempt("http://p2:2", "https://target.com/c", "2026-01-01T00:00:04Z"),
        _attempt("http://p3:3", "https://target.com/b", "2026-01-01T00:00:05Z"),  # same URL, 3rd proxy
    ]
    windows = _compute_window_stats(events, t0)
    assert len(windows) == 1
    assert windows[0]["urls_handled"] == 3   # a, b, c — distinct


def test_fetch_attempts_is_total_event_count():
    """fetch_attempts counts all attempt events (proxy × url pairs), not distinct URLs."""
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    events = [
        _attempt("http://p1:1", "https://target.com/a", "2026-01-01T00:00:01Z"),
        _attempt("http://p2:2", "https://target.com/a", "2026-01-01T00:00:02Z"),
        _attempt("http://p1:1", "https://target.com/b", "2026-01-01T00:00:03Z"),
        _attempt("http://p2:2", "https://target.com/c", "2026-01-01T00:00:04Z"),
        _attempt("http://p3:3", "https://target.com/b", "2026-01-01T00:00:05Z"),
    ]
    windows = _compute_window_stats(events, t0)
    assert windows[0]["fetch_attempts"] == 5  # total attempt events


def test_urls_handled_ne_fetch_attempts_when_multi_proxy():
    """The two counters diverge when a URL is attempted by multiple proxies."""
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    # 1 distinct URL, 3 attempt events (3 proxies race the same URL)
    events = [
        _attempt("http://p1:1", "https://target.com/x", "2026-01-01T00:00:01Z", "fail"),
        _attempt("http://p2:2", "https://target.com/x", "2026-01-01T00:00:02Z", "fail"),
        _attempt("http://p3:3", "https://target.com/x", "2026-01-01T00:00:03Z", "ok"),
    ]
    windows = _compute_window_stats(events, t0)
    w = windows[0]
    assert w["urls_handled"]   == 1  # one distinct URL
    assert w["fetch_attempts"] == 3  # three proxy attempts


def test_window_stats_across_two_windows():
    """urls_handled and fetch_attempts are computed per-window independently."""
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    events = [
        # window 0: 2 distinct URLs, 3 attempts
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:10:00Z"),
        _attempt("http://p2:2", "https://t.com/a", "2026-01-01T00:20:00Z"),
        _attempt("http://p1:1", "https://t.com/b", "2026-01-01T00:30:00Z"),
        # window 1: 1 distinct URL, 2 attempts
        _attempt("http://p1:1", "https://t.com/c", "2026-01-01T01:05:00Z"),
        _attempt("http://p2:2", "https://t.com/c", "2026-01-01T01:10:00Z"),
    ]
    windows = _compute_window_stats(events, t0)
    assert len(windows) == 2
    w0, w1 = windows[0], windows[1]
    assert w0["urls_handled"]   == 2
    assert w0["fetch_attempts"] == 3
    assert w1["urls_handled"]   == 1
    assert w1["fetch_attempts"] == 2


# ---------------------------------------------------------------------------
# D3 — job.md rendering: both columns present with correct values
# ---------------------------------------------------------------------------

def test_job_md_has_fetch_versuche_column(tmp_path):
    """job.md table header contains 'Fetch-Versuche' and 'URLs handled' as separate columns."""
    events = [
        _refresh(500, "2026-01-01T00:00:00Z"),
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:01:00Z"),
        _attempt("http://p2:2", "https://t.com/a", "2026-01-01T00:02:00Z"),
        _attempt("http://p1:1", "https://t.com/b", "2026-01-01T00:03:00Z"),
    ]
    md = _write_and_read_md(tmp_path, events)
    assert "Fetch-Versuche" in md
    assert "URLs handled"   in md


def test_job_md_urls_handled_and_fetch_attempts_values(tmp_path):
    """job.md row values: urls_handled = 2 (distinct), fetch_attempts = 3 (total)."""
    events = [
        _refresh(500, "2026-01-01T00:00:00Z"),
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:01:00Z"),
        _attempt("http://p2:2", "https://t.com/a", "2026-01-01T00:02:00Z"),  # same URL
        _attempt("http://p1:1", "https://t.com/b", "2026-01-01T00:03:00Z"),
    ]
    md = _write_and_read_md(tmp_path, events)
    # Window 0 row: | 0 | probiert | erfolgreich | 2 | 3 | 500 |
    assert "| 0 |" in md
    lines = [l for l in md.splitlines() if l.startswith("| 0 |")]
    assert lines, "Window 0 row not found in job.md"
    row = lines[0]
    cols = [c.strip() for c in row.split("|")]
    # cols[0]='', cols[1]='0', cols[2]=probiert, cols[3]=erfolgreich,
    # cols[4]=urls_handled, cols[5]=fetch_attempts, cols[6]=pool_size
    assert cols[4] == "2", f"urls_handled wrong: {cols[4]}"
    assert cols[5] == "3", f"fetch_attempts wrong: {cols[5]}"


# ---------------------------------------------------------------------------
# D1 — pool_retry.fetch_with_retry
# ---------------------------------------------------------------------------

def test_fetch_with_retry_recovers_after_transient_failure():
    """fetch_with_retry returns the result when fn() eventually succeeds before attempt 5."""
    call_count = [0]

    def flaky():
        call_count[0] += 1
        if call_count[0] < 3:
            raise httpx.ConnectError("transient")
        return "recovered"

    with patch.object(pool_retry, "_sleep") as mock_sleep:
        result = pool_retry.fetch_with_retry(flaky)

    assert result == "recovered"
    assert call_count[0] == 3
    # sleep called between attempt 1→2 (1s) and attempt 2→3 (2s)
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list == [call(1), call(2)]


def test_fetch_with_retry_reraises_after_all_attempts():
    """fetch_with_retry re-raises the last exception after 5 failed attempts."""
    call_count = [0]

    def always_fail():
        call_count[0] += 1
        raise httpx.ConnectError("persistent")

    with patch.object(pool_retry, "_sleep") as mock_sleep:
        with pytest.raises(httpx.ConnectError, match="persistent"):
            pool_retry.fetch_with_retry(always_fail)

    assert call_count[0] == 5
    assert mock_sleep.call_count == 4  # slept between each of the 5 attempts


def test_fetch_with_retry_no_sleep_on_first_attempt():
    """fetch_with_retry does not sleep before the very first attempt."""
    def succeed_immediately():
        return 42

    with patch.object(pool_retry, "_sleep") as mock_sleep:
        result = pool_retry.fetch_with_retry(succeed_immediately)

    assert result == 42
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# D1 — load_backfill_pool: per-source isolation (continue on failure, no raise)
# ---------------------------------------------------------------------------

def test_load_backfill_pool_continues_when_monosans_fails():
    """If monosans exhausts all retries, pool contains entries from other sources; no exception raised."""
    from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool

    def mock_get(url, timeout):
        if "monosans" in url:
            raise httpx.ConnectError("test blip")
        resp = MagicMock()
        resp.text = "1.2.3.4:1080\n5.6.7.8:3128\n"
        resp.raise_for_status = lambda: None
        return resp

    with patch("httpx.get", side_effect=mock_get), patch.object(pool_retry, "_sleep"):
        pool, sources = load_backfill_pool()

    monosans_src = next(s for s in sources if "monosans" in s["url"])
    assert monosans_src["ok"] is False
    assert monosans_src["count"] == 0

    # Other sources contributed entries → pool is non-empty
    assert len(pool) > 0
    ok_sources = [s for s in sources if s["ok"]]
    assert len(ok_sources) > 0


def test_load_backfill_pool_returns_tuple():
    """load_backfill_pool returns (list, list) — pool and per-source results."""
    from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool

    resp = MagicMock()
    resp.text = "1.2.3.4:1080\n"
    resp.json.return_value = [{"protocol": "http", "host": "1.2.3.4", "port": 1080}]
    resp.raise_for_status = lambda: None

    with patch("httpx.get", return_value=resp), patch.object(pool_retry, "_sleep"):
        result = load_backfill_pool()

    pool, sources = result
    assert isinstance(pool, list)
    assert isinstance(sources, list)
    assert all(isinstance(s, dict) for s in sources)
    assert all({"url", "ok", "count"} <= s.keys() for s in sources)


def test_load_backfill_pool_source_count_on_success():
    """A successful source records count == number of parsed proxy entries."""
    from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool, THESPEEDX_SOURCES

    resp = MagicMock()
    # 3 valid lines per request → each bare_txt source gets count=3
    resp.text = "1.1.1.1:80\n2.2.2.2:80\n3.3.3.3:80\n"
    resp.json.return_value = [
        {"protocol": "http", "host": "4.4.4.4", "port": 80},
    ]
    resp.raise_for_status = lambda: None

    with patch("httpx.get", return_value=resp), patch.object(pool_retry, "_sleep"):
        _, sources = load_backfill_pool()

    # Check one of the TheSpeedX bare-txt sources
    thespeedx_http_url = THESPEEDX_SOURCES[0][1]
    src = next(s for s in sources if s["url"] == thespeedx_http_url)
    assert src["ok"] is True
    assert src["count"] == 3


# ---------------------------------------------------------------------------
# D2 — logger.record_pool_source
# ---------------------------------------------------------------------------

def test_record_pool_source_writes_jsonl_event(tmp_path):
    """record_pool_source appends a pool_source event with correct fields to JSONL."""
    from src.news.engine.proxy_pool.logger import AcquireLogger

    log_dir = tmp_path / "logs"
    logger  = AcquireLogger(total_urls=0, log_dir=log_dir)
    logger.record_pool_source("https://raw.githubusercontent.com/monosans/proxies.json", True, 4521)
    logger.record_pool_source("https://raw.githubusercontent.com/r00tee/Https.txt", False, 0)
    logger.close()

    lines  = list(log_dir.iterdir())[0].read_text().splitlines()
    events = [json.loads(l) for l in lines]

    assert events[0]["event"] == "pool_source"
    assert events[0]["url"]   == "https://raw.githubusercontent.com/monosans/proxies.json"
    assert events[0]["ok"]    is True
    assert events[0]["count"] == 4521
    assert "ts" in events[0]

    assert events[1]["ok"]    is False
    assert events[1]["count"] == 0


# ---------------------------------------------------------------------------
# D2 — _group_pool_sources
# ---------------------------------------------------------------------------

def _pool_source(url: str, ok: bool, count: int, ts: str = "2026-01-01T00:00:00Z") -> dict:
    return {"event": "pool_source", "url": url, "ok": ok, "count": count, "ts": ts}


def _pool_refresh(size: int, ts: str = "2026-01-01T00:00:00Z") -> dict:
    return {"event": "pool_refresh", "size": size, "ts": ts}


def test_group_pool_sources_single_refresh():
    """Single pool_refresh → one batch containing all following pool_source events."""
    events = [
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src1.com", True,  50, "2026-01-01T00:00:01Z"),
        _pool_source("https://src2.com", False,  0, "2026-01-01T00:00:02Z"),
    ]
    batches = _group_pool_sources(events)
    assert len(batches) == 1
    assert len(batches[0]) == 2
    assert batches[0][0]["url"] == "https://src1.com"
    assert batches[0][1]["ok"] is False


def test_group_pool_sources_two_refreshes():
    """Two pool_refresh events → two batches; attempt events between are ignored."""
    events = [
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src1.com", True, 50, "2026-01-01T00:00:01Z"),
        _attempt("http://p1:1", "https://target.com", "2026-01-01T00:05:00Z"),  # interleaved attempt
        _pool_refresh(90, "2026-01-01T01:00:00Z"),
        _pool_source("https://src1.com", True, 48, "2026-01-01T01:00:01Z"),
        _pool_source("https://src2.com", False,  0, "2026-01-01T01:00:02Z"),
    ]
    batches = _group_pool_sources(events)
    assert len(batches) == 2
    assert len(batches[0]) == 1   # startup: src1 only
    assert len(batches[1]) == 2   # refresh: src1 + src2


def test_group_pool_sources_empty_events():
    """No pool_refresh/pool_source events → empty list."""
    events = [_attempt("http://p1:1", "https://t.com", "2026-01-01T00:00:01Z")]
    batches = _group_pool_sources(events)
    assert batches == []


# ---------------------------------------------------------------------------
# D2 — job.md source section rendering
# ---------------------------------------------------------------------------

def test_job_md_source_section_present(tmp_path):
    """job.md renders ## Pool source breakdown when pool_source events exist."""
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://raw.githubusercontent.com/monosans/proxies.json", True,  50, "2026-01-01T00:00:01Z"),
        _pool_source("https://raw.githubusercontent.com/r00tee/Https.txt",      False,  0, "2026-01-01T00:00:02Z"),
    ]
    md = _write_and_read_md(tmp_path, events)
    assert "## Pool source breakdown" in md
    assert "### Refresh 0 (startup)"  in md
    assert "monosans"  in md
    assert "r00tee"    in md
    assert "| ok |"    in md
    assert "| fail |"  in md


def test_job_md_source_section_dedup_note(tmp_path):
    """job.md source section contains the cross-repo dedup explanation."""
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src.com/a", True, 50, "2026-01-01T00:00:01Z"),
    ]
    md = _write_and_read_md(tmp_path, events)
    assert "cross-repo dedup" in md or "deduped" in md


def test_job_md_source_section_two_refreshes(tmp_path):
    """Two pool_refresh batches produce Refresh 0 (startup) and Refresh 1 subsections."""
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src.com/a", True, 50, "2026-01-01T00:00:01Z"),
        _pool_refresh(90,  "2026-01-01T01:00:00Z"),
        _pool_source("https://src.com/a", True, 48, "2026-01-01T01:00:01Z"),
    ]
    md = _write_and_read_md(tmp_path, events)
    assert "### Refresh 0 (startup)" in md
    assert "### Refresh 1"           in md


def test_job_md_source_section_absent_without_pool_source_events(tmp_path):
    """job.md has no source section when no pool_source events exist (legacy JSONL)."""
    events = [
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:01:00Z"),
    ]
    md = _write_and_read_md(tmp_path, events)
    assert "## Pool source breakdown" not in md


def test_job_md_source_count_values(tmp_path):
    """Count column in source table shows the raw proxy count per source."""
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src.com/big",  True, 7832, "2026-01-01T00:00:01Z"),
        _pool_source("https://src.com/dead", False,   0, "2026-01-01T00:00:02Z"),
    ]
    md = _write_and_read_md(tmp_path, events)
    assert "7832" in md
    assert "| fail | 0 |" in md
