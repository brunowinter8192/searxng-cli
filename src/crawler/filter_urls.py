# INFRASTRUCTURE
import fnmatch
import logging
import os
import sys
import tempfile

logger = logging.getLogger(__name__)


# ORCHESTRATOR

# Filter URL list file in-place, dropping lines matching any pattern in exclude_patterns
def filter_urls_workflow(file_path: str, exclude_patterns: str, dry_run: bool = False) -> None:
    if not os.path.exists(file_path):
        print(f"filter_urls: file not found: {file_path}", file=sys.stderr)
        return

    all_urls = _read_lines(file_path)
    kept = [u for u in all_urls if not match_any(u, exclude_patterns)]
    dropped = [u for u in all_urls if match_any(u, exclude_patterns)]

    for url in dropped:
        print(f"dropped: {url}", file=sys.stderr)
    print(f"kept {len(kept)}, dropped {len(dropped)} from {file_path}", file=sys.stderr)

    if not dry_run:
        _atomic_write(file_path, kept)


# FUNCTIONS

# Test URL against any glob pattern from comma-separated pattern string
def match_any(url: str, patterns_str: str) -> bool:
    if not patterns_str:
        return False
    return any(
        fnmatch.fnmatchcase(url, p.strip())
        for p in patterns_str.split(",")
        if p.strip()
    )


# Read URL list from file (strip whitespace, skip empty lines)
def _read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# Atomic file rewrite: tmpfile in same dir + os.replace
def _atomic_write(path: str, lines: list[str]) -> None:
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise
