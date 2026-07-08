# dev/search_pipeline/_lib/

## Role
Shared parser + text utilities for `dev/search_pipeline/` analysis scripts — single source of truth for `KNOWN_ENGINES`, smoke-report parsing, and snippet-text cleanup/scoring. `__init__.py` empty, imported as `from _lib.parse import ...` / `from _lib.text import ...`.

## Modules

### parse.py (119 LOC)

**Purpose:** Parses the singular `pipeline_smoke_<ts>.md` report format into per-URL records (query, class, title, url, engines, source/display, og/meta, per-engine snippets).
**Reads:** MD report `Path` passed by caller (no direct filesystem lookup).
**Writes:** returns `list[dict]` — no I/O.
**Called by:** `22_openlibrary_smoke.py`, `23_books_ab_smoke.py`, `branch_probe.py`, `engine_distribution_analysis.py`, `pool_diff_v2_v3.py`, `no_google_burst_smoke.py`, `scholar_http_probe.py`, `snippet_selection_simulator.py`, `snippet_quality_analysis.py`.
**Calls out:** none (stdlib `ast`, `re`, `collections`, `pathlib` only).

### text.py (93 LOC)

**Purpose:** EN+DE combined stopword list (no NLTK dep), bloat-pattern detection (`detect_bloat`), bloat stripping (`strip_bloat`, incl. Google doubled-title-prefix heuristic), lexical-density scoring (`lexical_density`) for snippet quality comparisons.
**Reads:** raw snippet text passed by caller.
**Writes:** returns cleaned strings / sets / floats — no I/O.
**Called by:** scripts importing `_lib.text` (snippet-quality and selection-simulation probes); see `parse.py` caller list for the overlapping set.
**Calls out:** none (stdlib `re` only).

### test_text.py (32 LOC)

**Purpose:** Standalone assertion script for `strip_bloat` — 6 regression-guard assertions covering the "Read more" period-concatenated patch and the "Translate this page" prefix patch.
**Reads:** none.
**Writes:** stdout (`All 6 assertions passed.`) or `AssertionError` on failure.
**Called by:** CLI only. `./venv/bin/python dev/search_pipeline/_lib/test_text.py`.
**Calls out:** `_lib.text.strip_bloat`.
