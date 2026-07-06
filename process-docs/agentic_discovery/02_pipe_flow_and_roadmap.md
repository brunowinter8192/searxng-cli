# Agentic Discovery — Pipe-Flow Decisions & Roadmap

**Session:** 2026-05-31
**Status:** Decisions from this session — skill structure still open (next session)

---

## New Pipe Flow (decided)

### Before (Opus-side, pre-crawl, pattern-based)

```
Opus: explore_site → filter_urls (--exclude-patterns, fnmatch) → crawl_site → index
         ↑ Opus decides pre-crawl which URLs get crawled at all
```

Filter logic: `filter_urls_workflow` + `match_any()` in `src/crawler/filter_urls.py`.
Patterns are defined before the crawl — Opus must know the noise patterns BEFORE the crawl runs.

### New (worker-side, post-crawl, content-based)

```
Worker: Discovery (agentic, __NEXT_DATA__-first) → Crawl → content-based drop assessment → Index
                                                              ↑ Worker decides after crawl
```

**Decision logic:** The worker crawls all found URLs, reads the content, and decides
per URL whether the content is indexable. Drop criteria are content-based (empty page, redirect-only,
pure nav page, duplicate content) — not pattern-based.

**Worker end-report form:**
```
URLs found:    N
URLs crawled:  M
URLs dropped:  K  (with rationale per URL or per category)
URLs indexed:  M-K
```

**Why post-crawl is better:**
- Pattern filters before the crawl require domain prior knowledge (which URL patterns are noise?)
- Content-based drop after the crawl is domain-agnostic — the worker sees the real content
- Fits the generic discovery approach: whoever finds the URLs without prior knowledge should also filter them without prior knowledge

**Concrete consequence:** `filter_urls` / `--exclude-patterns` remains a CLI tool for manual post-processing,
but is no longer a mandatory step in the worker flow. The worker's drop proposal replaces the pre-crawl filter
as the primary quality stage.

---

## Note: Not All Found URLs Are Equally Valuable

From the `__NEXT_DATA__` experiment:
- 299 of the 305 goldstandard URLs came from FPT + GHEC sidebars (current, maintained pages)
- 6 came from GHES 3.16 (oldest available version): `projects-classic/*` + `repos/tags`
  — these pages are deprecated, no longer linked in newer versions, and technically
  outdated (`projects-classic` = GitHub Classic Projects, deprecated for years)

The worker drop proposal solves exactly this: post-crawl, the worker can recognize that
deprecated content is thin, looks outdated, or points to newer alternatives —
and recommend a drop, without Opus having known a pattern beforehand.

---

## Open Decision (next session): Skill / Toolkit Structure

**RESOLVED** — see `03_skill_structure_resolved.md`

Two existing pipeline skills (historical context, decision resolved below):
- **web-research** (Opus-side): discovery + optional filtering, hands off crawled URLs
- **cleanup-and-index** (worker-side): indexing, post-processing

Open questions (all resolved):
1. **Rename:** → `capture-and-index` (covers the complete worker flow: Discovery + Scrape + Drop + Cleanup + Index)
2. **Toolkit vs. monolithic:** → Monolithic worker skill. Discovery guideline in the skill as a procedure (Phase 0), no separate toolkit.
3. **Scripts vs. worker writes itself:** → Worker writes /tmp scripts situationally. No pinned reference script.
4. **`web-research` scope:** → Opus provides seed URL + collection. Worker does Discovery + Scrape + Drop + Cleanup + Index completely. Opus role: identify domain → confirm collection → spawn worker → verify.

---

## Roadmap Sequence (decided)

| Step | What | Dependency |
|---------|-----|-------------|
| 1 | Decide skill/toolkit structure | next session, open questions above |
| 2 | Scraping phase: shared CLI/pipeline logic + prod config | after (1) — structure determines where config lives |
| 3 | Index the 305 docs.github.com/de/rest URLs | after (2) — scraping must be production-ready |
| 4 | Second website as testbed | after (3) — test generic discovery on an unknown domain |

Step 4 is the actual generalizability proof: does the `__NEXT_DATA__` approach work
on another Next.js doc site, or does it need site-specific adaptations?
