"""Tests for browser-launch failure classification in scrape_url.

Runs without a browser: try_scrape's AsyncWebCrawler is patched to raise a
synthetic exception, simulating a missing patchright/chromium executable.
"""
import logging

import pytest

from src.scraper import scrape_url


# ---------------------------------------------------------------------------
# is_browser_launch_error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("msg", [
    "BrowserType.launch: Executable doesn't exist at /root/.cache/ms-playwright/chromium-1208/chrome-linux/chrome",
    "Please run the following command to download new browsers:\n    playwright install",
    "Failed to launch chromium via BrowserType.launch",
])
def test_is_browser_launch_error_detects_signatures(msg):
    """Known launch-failure signatures are classified as browser_missing."""
    assert scrape_url.is_browser_launch_error(Exception(msg)) is True


@pytest.mark.parametrize("msg", [
    "Timeout 60000ms exceeded while waiting for load",
    "net::ERR_NAME_NOT_RESOLVED at https://nonexistent-domain-xyz.test",
    "Page.goto: net::ERR_CONNECTION_REFUSED",
    "",
])
def test_is_browser_launch_error_ignores_ordinary_errors(msg):
    """Ordinary per-URL network/timeout errors are NOT misclassified as browser problems."""
    assert scrape_url.is_browser_launch_error(Exception(msg)) is False


# ---------------------------------------------------------------------------
# try_scrape routes launch failures to garbage_type "browser_missing"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_maps_launch_failure_to_browser_missing(monkeypatch, caplog):
    """A browser-launch exception from AsyncWebCrawler yields garbage_type=browser_missing at ERROR level."""

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("BrowserType.launch: Executable doesn't exist at /fake/chrome")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(scrape_url, "AsyncWebCrawler", _RaisingCrawler)

    with caplog.at_level(logging.ERROR, logger="src.scraper.scrape_url"):
        content, meta = await scrape_url.try_scrape("https://example.com")

    assert content == ""
    assert meta["garbage_type"] == "browser_missing"
    assert any("Browser binary missing" in m or "launch" in m.lower() for m in caplog.messages)


@pytest.mark.asyncio
async def test_try_scrape_keeps_generic_outcome_for_ordinary_errors(monkeypatch):
    """A non-launch exception (e.g. timeout) keeps the existing generic empty-meta behavior."""

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("Timeout 60000ms exceeded while waiting for load")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(scrape_url, "AsyncWebCrawler", _RaisingCrawler)

    content, meta = await scrape_url.try_scrape("https://example.com")

    assert content == ""
    assert meta["garbage_type"] is None


# ---------------------------------------------------------------------------
# scrape_url_workflow surfaces the actionable message
# ---------------------------------------------------------------------------

def test_garbage_messages_has_actionable_browser_missing_fix():
    """The user-facing message for browser_missing names the concrete install command."""
    msg = scrape_url._GARBAGE_MESSAGES["browser_missing"]
    assert "patchright install chromium" in msg
