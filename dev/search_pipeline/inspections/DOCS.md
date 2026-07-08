# dev/search_pipeline/inspections/

## Role

DOM-inspection tooling for engine selector drift recovery. Use when a browser-based engine returns persistent EMPTY or TIMEOUT for queries that should match — meaning the production selectors no longer match the rendered DOM (engine updated their markup). Not for one-shot debug scripts — holds reusable methodology and committed inspection reports as historical evidence.

Recovery flow: engine returns EMPTY/TIMEOUT for N consecutive queries → run `inspect_engine_dom.py <engine_name> "<sample_query>"` → read report (H1 broken selectors + H2 new data-test-id candidates + Diagnosis) → update `_JS_WAIT`/`_JS_PARSE` in `src/search/engines/<engine>.py` → smoke-test via `dev/search_pipeline/<engine>_smoke.py`.

## Modules

### inspect_engine_dom.py (330 LOC)

**Purpose:** navigate to engine search page via production browser (pydoll stealth, JS rendered), run 7 DOM heuristics (selector presence, data-test-id inventory, repeating class clusters, class-substring scan, data-* attribute scan, HTML snippet, external link count), write timestamped MD report.
**Reads:** `ENGINE_REGISTRY` (module-level config per engine); live DOM via pydoll browser session.
**Writes:** `md/<engine>_<ts>.md` report.
**Called by:** CLI only.
**Calls out:** `src.search.browser` (new_tab, close_browser).

---

## Gotchas

New engines must be added to `ENGINE_REGISTRY` in `inspect_engine_dom.py` before use — only `semantic_scholar` is configured; `google`, `google_scholar`, `duckduckgo`, `mojeek`, `lobsters` are TODO stubs. `md/semantic_scholar_20260508_*.md` are committed evidence reports (2026-05-08, diagnosed `div.cl-paper-row` selector drift → new selectors identified) — not throwaway output.
