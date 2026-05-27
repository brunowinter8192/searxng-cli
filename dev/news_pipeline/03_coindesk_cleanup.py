#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import json
import re
import statistics
from pathlib import Path

INPUT_DIR = Path(__file__).parent / "02b_output"
OUTPUT_DIR = Path(__file__).parent / "03_output"

# End-anchor patterns — checked in document order; earliest match wins
_RE_MORE_FOR_YOU     = re.compile(r'^More For You\s*$')
_RE_MORE_FOR_YOU_H2  = re.compile(r'^## More For You')
_RE_PRIVACY          = re.compile(r'^## We Care About Your Privacy')
# ≥2 concatenated [text](url) groups with no surrounding plain text.
# Requires {2,} to avoid firing on single-link lines (Google badge, nav labels).
_RE_TAG_FOOTER       = re.compile(r'^(\[[^\]]+\]\([^)]+\)){2,}$')

_END_ANCHORS = [
    ("MORE_FOR_YOU",    _RE_MORE_FOR_YOU),
    ("MORE_FOR_YOU_H2", _RE_MORE_FOR_YOU_H2),
    ("PRIVACY",         _RE_PRIVACY),
    ("TAG_FOOTER",      _RE_TAG_FOOTER),
]

# In-body strip patterns
_RE_GOOGLE_BADGE = re.compile(r'\[Make\s*\]\(https://www\.google\.com/preferences/source')
# Updated/Published prefix variant covered by optional group
_RE_DATE_BYLINE  = re.compile(r'^(?:Updated |Published )?[A-Z][a-z]+ \d{1,2}, \d{4},.*read$')
_RE_BYLINE       = re.compile(r'^By \[.*?\]\(.*?\)(?:[,|].*)?\s*$')
_RE_IMAGE        = re.compile(r'^!\[.*?\]\(.*?\)\s*$')
_RE_IMAGE_LINK   = re.compile(r'^\[!\[.*?\]\(.*?\)\]\(.*?\)\s*$')
_RE_EMPTY_LINK   = re.compile(r'\[\]\(.*?\)')


# ORCHESTRATOR
def cleanup_workflow(input_dir: Path, output_dir: Path):
    md_files = sorted(input_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for path in md_files:
        entry = process_file(path, output_dir)
        manifest.append(entry)

    write_manifest(manifest, output_dir)
    print_summary(manifest, output_dir)


# FUNCTIONS

# Parse, clean, and write one article file; return manifest entry dict
def process_file(path: Path, output_dir: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    original_chars = len(raw)
    hash_name = path.stem

    fm_fields, body_lines = parse_frontmatter(raw)

    start_idx = find_start_anchor(body_lines)
    if start_idx is None:
        # No H1 — output raw body only (no frontmatter block), flag in manifest
        cleaned = "\n".join(body_lines).strip() + "\n"
        out_path = output_dir / path.name
        out_path.write_text(cleaned, encoding="utf-8")
        return _manifest_entry(hash_name, fm_fields, original_chars, cleaned, "NO_H1")

    end_idx, anchor_name = find_end_anchor(body_lines, start_idx)
    extracted = body_lines[start_idx:end_idx]
    cleaned_lines = clean_body(extracted)
    cleaned = "\n".join(cleaned_lines) + "\n"

    out_path = output_dir / path.name
    out_path.write_text(cleaned, encoding="utf-8")
    return _manifest_entry(hash_name, fm_fields, original_chars, cleaned, anchor_name)


# Build manifest entry dict merging frontmatter fields + run stats
def _manifest_entry(hash_name: str, fm: dict, original_chars: int, cleaned: str, anchor: str) -> dict:
    cleaned_chars = len(cleaned)
    reduction = round((1 - cleaned_chars / original_chars) * 100, 1) if original_chars else 0.0
    return {
        "hash": hash_name,
        "url": fm.get("url", ""),
        "lastmod": fm.get("lastmod", ""),
        "publication_date": fm.get("publication_date", ""),
        "title": fm.get("title", ""),
        "section": fm.get("section", ""),
        "scraped_at": fm.get("scraped_at", ""),
        "original_chars": original_chars,
        "cleaned_chars": cleaned_chars,
        "reduction_pct": reduction,
        "end_anchor_used": anchor,
    }


# Split raw file into frontmatter field dict and body lines
def parse_frontmatter(raw: str) -> tuple[dict, list[str]]:
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, [l.rstrip("\n") for l in lines]
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return {}, [l.rstrip("\n") for l in lines]
    fm_fields: dict[str, str] = {}
    for line in lines[1:close]:
        stripped = line.rstrip("\n")
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            fm_fields[key.strip()] = value.strip()
    body_lines = [l.rstrip("\n") for l in lines[close + 1:]]
    return fm_fields, body_lines


# Return index of first H1 line in body_lines, or None
def find_start_anchor(body_lines: list[str]) -> int | None:
    for i, line in enumerate(body_lines):
        if line.startswith("# "):
            return i
    return None


# Return (end_idx, anchor_name) for the earliest end anchor after start_idx.
# end_idx is exclusive — body slice is body_lines[start_idx:end_idx].
# If no anchor found: (len(body_lines), "NONE")
def find_end_anchor(body_lines: list[str], start_idx: int) -> tuple[int, str]:
    for i in range(start_idx + 1, len(body_lines)):
        line = body_lines[i]
        for name, pattern in _END_ANCHORS:
            if pattern.match(line):
                return i, name
    return len(body_lines), "NONE"


# Apply in-body cleanup rules to a list of lines; return cleaned list
def clean_body(lines: list[str]) -> list[str]:
    result = []
    blank_run = 0

    for line in lines:
        # Strip Google News badge line
        if _RE_GOOGLE_BADGE.search(line):
            continue
        # Strip date/read-time byline (bare and Updated/Published prefix variants)
        if _RE_DATE_BYLINE.match(line):
            continue
        # Strip author byline (By [...](...)...)
        if _RE_BYLINE.match(line):
            continue
        # Strip standalone image lines and image-wrapped-in-link lines
        if _RE_IMAGE.match(line) or _RE_IMAGE_LINK.match(line):
            continue
        # Strip empty links inline
        line = _RE_EMPTY_LINK.sub("", line)

        # Blank-line normalization (collapse 3+ consecutive blanks → 2)
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 2:
                result.append("")
        else:
            blank_run = 0
            result.append(line)

    # Strip leading/trailing blank lines from body
    while result and result[0] == "":
        result.pop(0)
    while result and result[-1] == "":
        result.pop()

    return result


# Write manifest JSON to output_dir
def write_manifest(manifest: list[dict], output_dir: Path):
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


# Print summary: total files, reduction stats, anchor distribution
def print_summary(manifest: list[dict], output_dir: Path):
    reductions = [e["reduction_pct"] for e in manifest]
    anchor_dist: dict[str, int] = {}
    for e in manifest:
        anchor_dist[e["end_anchor_used"]] = anchor_dist.get(e["end_anchor_used"], 0) + 1

    print(f"Files processed : {len(manifest)}")
    if reductions:
        print(f"Reduction %     : mean={statistics.mean(reductions):.1f}%  median={statistics.median(reductions):.1f}%  min={min(reductions):.1f}%  max={max(reductions):.1f}%")
    print("End-anchor dist :")
    for anchor, count in sorted(anchor_dist.items(), key=lambda x: -x[1]):
        print(f"  {anchor}: {count}")
    print(f"Output          : {output_dir}")
    print(f"Manifest        : {output_dir / 'manifest.json'}")


def main():
    parser = argparse.ArgumentParser(
        description="CoinDesk article cleanup — extract body, strip nav/footer noise, normalize."
    )
    parser.add_argument("--input", default=str(INPUT_DIR),
                        help=f"Input dir of scraped .md files (default: {INPUT_DIR})")
    parser.add_argument("--output", default=str(OUTPUT_DIR),
                        help=f"Output dir for cleaned .md files (default: {OUTPUT_DIR})")
    args = parser.parse_args()
    cleanup_workflow(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
