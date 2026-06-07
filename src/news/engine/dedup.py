# INFRASTRUCTURE
import hashlib
import re
from pathlib import Path

DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


# FUNCTIONS

# Compute URL hash matching the publish filename convention
def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


# Extract YYYY-MM-DD from publication_date field (ISO-8601 string) or URL path
def pub_date_str(entry: dict) -> str:
    pub = entry.get("publication_date", "")
    if pub and len(pub) >= 10:
        return pub[:10]
    m = DATE_RE.search(entry.get("url", ""))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


# Return (new_entries, n_skipped): drop entries whose target MD already exists in collection_dir.
# Filename key: f"{source}__{pubdate}__{hash}.md"
def filter_new_entries(
    entries: list[dict],
    collection_dir: Path,
    source: str,
) -> tuple[list[dict], int]:
    new_entries = []
    n_skipped = 0
    for entry in entries:
        h = url_hash(entry["url"])
        pubdate = pub_date_str(entry)
        target = collection_dir / f"{source}__{pubdate}__{h}.md"
        if target.exists():
            n_skipped += 1
        else:
            new_entries.append(entry)
    return new_entries, n_skipped
