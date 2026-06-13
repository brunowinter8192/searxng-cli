# INFRASTRUCTURE
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from mcp.types import TextContent

# From pdf_chain.py: URL chain resolution (blacklist, TIER1 transforms, multi-step citation_pdf_url)
from src.scraper.pdf_chain import (
    TIER1_DOMAINS,
    _base_domain,
    apply_tier1_transform,
    extract_citation_pdf_url,
    is_blacklisted,
    is_github_blob,
)
# From download_logger.py: per-URL JSONL download log
from src.scraper.download_logger import log_download

logger = logging.getLogger(__name__)


# ORCHESTRATOR
def download_pdf_workflow(url: str, output_dir: str = str(Path.home() / "Downloads")) -> list[TextContent]:
    t_total = time.perf_counter()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    logger.info("Downloading PDF: %s", url)

    chain_attempted: list[str] = []
    timings_ms: dict = {
        "blacklist_check": None, "github_blob_check": None, "tier1_transform": None,
        "direct_pdf_check": None, "citation_pdf_url_hop1": None,
        "download": None, "total_wall": None,
    }
    _rec: dict = {
        "ts": ts, "url": url, "domain": _base_domain(url), "output_dir": output_dir,
        "output_path": None, "outcome": None, "chain_resolution": None,
        "chain_attempted": chain_attempted, "final_pdf_url": None,
        "http_status": None, "content_type": None, "bytes_downloaded": None,
        "timings_ms": timings_ms, "error_message": None,
    }

    def _emit(outcome: str, **kwargs) -> None:
        timings_ms["total_wall"] = round((time.perf_counter() - t_total) * 1000)
        _rec["outcome"] = outcome
        _rec.update(kwargs)
        log_download(_rec)

    fetch_url, chain_resolution, abort, step_timings, step_chain = _resolve_pdf_url(url)
    timings_ms.update(step_timings)
    chain_attempted.extend(step_chain)
    if abort is not None:
        _emit(chain_resolution)
        return abort

    _rec["final_pdf_url"] = fetch_url
    _rec["chain_resolution"] = chain_resolution

    response, err_outcome, err_kwargs, err_content, step_timings, step_chain = _stream_download(fetch_url)
    timings_ms.update(step_timings)
    chain_attempted.extend(step_chain)
    if err_outcome is not None:
        _emit(err_outcome, **err_kwargs)
        return err_content

    content_type, body_start, is_valid = _verify_pdf_content(response)
    if not is_valid:
        _emit("http_error", http_status=response.status_code, content_type=content_type, error_message="non_pdf_response")
        return [TextContent(type="text", text=f"Error: URL did not return a PDF (Content-Type: {content_type})")]

    output_path, file_size, io_err = _save_pdf_to_disk(response, fetch_url, output_dir, body_start)
    if io_err is not None:
        _emit("io_error", output_path=output_path, http_status=response.status_code,
              content_type=content_type, error_message=type(io_err).__name__)
        return [TextContent(type="text", text=f"Error writing file {output_path}: {io_err}")]

    size_str = format_size(file_size)
    logger.info("PDF saved: %s (%s)", output_path, size_str)
    _emit("ok", output_path=output_path, http_status=response.status_code,
          content_type=content_type, bytes_downloaded=file_size)
    return [TextContent(type="text", text=f"Downloaded: {output_path} ({size_str})")]


# FUNCTIONS

# Resolve download URL through blacklist → github_blob → tier1_transform → direct/.pdf chain
def _resolve_pdf_url(url: str) -> tuple:
    timings: dict = {}
    chain: list[str] = []

    t0 = time.perf_counter()
    blacklisted = is_blacklisted(url)
    timings["blacklist_check"] = round((time.perf_counter() - t0) * 1000)
    chain.append("blacklist_check")
    if blacklisted:
        domain = _base_domain(url)
        logger.info("PDF download blocked (blacklist): %s", domain)
        return (
            None, "blacklisted",
            [TextContent(type="text", text=f"Cannot download PDF from {url}: {domain} is on the blocked-domain list (no accessible PDF path).")],
            timings, chain,
        )

    t0 = time.perf_counter()
    github_blob = is_github_blob(url)
    timings["github_blob_check"] = round((time.perf_counter() - t0) * 1000)
    chain.append("github_blob_check")
    if github_blob:
        logger.info("PDF download blocked (GitHub blob viewer): %s", url)
        return (
            None, "github_blob",
            [TextContent(type="text", text=f"Cannot download PDF from {url}: GitHub blob URLs serve HTML viewers. Use the raw URL (github.com/.../raw/...) instead.")],
            timings, chain,
        )

    # Step 3: TIER1 transform (arxiv /abs/ → /pdf/, aclanthology + .pdf, openreview /forum → /pdf)
    # When a transform is applied, the resulting URL is a known PDF target — skip citation_pdf_url lookup.
    # (arxiv /pdf/<id> has no .pdf suffix but is a direct PDF; checking .endswith('.pdf') would
    # incorrectly trigger the multi-step branch and fail when extract_citation_pdf_url sees application/pdf.)
    t0 = time.perf_counter()
    transformed = apply_tier1_transform(url)
    timings["tier1_transform"] = round((time.perf_counter() - t0) * 1000)
    chain.append("tier1_transform")
    if transformed:
        logger.debug("TIER1 transform: %s → %s", url, transformed)
        return transformed, "tier1", None, timings, chain

    fetch_url = url
    domain = _base_domain(fetch_url)
    is_tier1 = domain in TIER1_DOMAINS or any(domain.endswith("." + t) for t in TIER1_DOMAINS)
    t0 = time.perf_counter()
    is_direct = urlparse(fetch_url).path.lower().endswith(".pdf")
    timings["direct_pdf_check"] = round((time.perf_counter() - t0) * 1000)
    chain.append("direct_pdf_check")
    if is_direct or is_tier1:
        return fetch_url, "direct", None, timings, chain

    t0 = time.perf_counter()
    citation_url = extract_citation_pdf_url(fetch_url)
    timings["citation_pdf_url_hop1"] = round((time.perf_counter() - t0) * 1000)
    chain.append("citation_pdf_url_hop1")
    if citation_url:
        logger.debug("Multi-step citation_pdf_url: %s → %s", fetch_url, citation_url)
        return citation_url, "multi_step", None, timings, chain

    logger.info("No PDF path found for: %s", url)
    return (
        None, "no_pdf_path",
        [TextContent(type="text", text=f"Cannot download PDF from {url}: no direct PDF path or citation_pdf_url meta tag found.")],
        timings, chain,
    )


# Stream-download fetch_url; return response on success or error details on failure
def _stream_download(fetch_url: str) -> tuple:
    timings: dict = {}
    chain: list[str] = ["download"]
    t0 = time.perf_counter()
    try:
        response = requests.get(fetch_url, stream=True, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as e:
        timings["download"] = round((time.perf_counter() - t0) * 1000)
        return (
            None, "http_error",
            {"http_status": e.response.status_code, "error_message": f"HTTPError {e.response.status_code}"},
            [TextContent(type="text", text=f"Error downloading {fetch_url}: HTTP {e.response.status_code}")],
            timings, chain,
        )
    except requests.RequestException as e:
        timings["download"] = round((time.perf_counter() - t0) * 1000)
        return (
            None, "network_error",
            {"error_message": type(e).__name__},
            [TextContent(type="text", text=f"Error downloading {fetch_url}: {e}")],
            timings, chain,
        )
    timings["download"] = round((time.perf_counter() - t0) * 1000)
    return response, None, {}, None, timings, chain


# Verify response is a PDF via Content-Type header or %PDF magic bytes
def _verify_pdf_content(response: requests.Response) -> tuple:
    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" in content_type:
        return content_type, b"", True
    body_start = next(response.iter_content(chunk_size=4), b"")
    if body_start[:4] == b"%PDF":
        return content_type, body_start, True
    return content_type, b"", False


# Derive output path, write PDF to disk, return path and file size
def _save_pdf_to_disk(response: requests.Response, fetch_url: str, output_dir: str, body_start: bytes) -> tuple:
    filename = extract_filename(response, fetch_url)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    try:
        write_pdf(response, output_path, body_start)
    except OSError as e:
        return output_path, 0, e
    file_size = os.path.getsize(output_path)
    return output_path, file_size, None


# Extract filename from Content-Disposition header, URL path, or generate one
def extract_filename(response: requests.Response, url: str) -> str:
    content_disposition = response.headers.get("Content-Disposition", "")
    if content_disposition:
        match = re.search(r'filename[^;=\n]*=[\"\']?([^;\"\'\n]+)', content_disposition)
        if match:
            name = match.group(1).strip()
            if name:
                return name

    path = url.split("?")[0].rstrip("/")
    basename = path.split("/")[-1]
    if basename and basename.lower().endswith(".pdf"):
        return basename

    return f"download_{int(time.time())}.pdf"


# Write streamed response content to file; body_start is pre-read bytes (may be empty)
def write_pdf(response: requests.Response, output_path: str, body_start: bytes = b"") -> None:
    with open(output_path, "wb") as f:
        if body_start:
            f.write(body_start)
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


# Format byte count as human-readable KB or MB string
def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"
