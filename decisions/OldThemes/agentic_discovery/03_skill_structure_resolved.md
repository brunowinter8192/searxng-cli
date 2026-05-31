# Agentic Discovery — Skill Structure Resolution

**Session:** 2026-06-01  
**Status:** RESOLVED — closes the open decision from `02_pipe_flow_and_roadmap.md`  
**Source decisions:** `01_gh_live_experiment.md`, `02_pipe_flow_and_roadmap.md`, `decisions/explore01_discovery.md`

---

## What Was Decided

### 1. Discovery = guideline in `capture-and-index` Phase 0 (no pinned script)

The capture pipeline's URL discovery is encoded as a PROCEDURE in the worker skill (`capture-and-index/SKILL.md`, Phase 0), not as a reference script that workers invoke. Workers write situational `/tmp` scripts based on the procedure — the deliverable is maximum URL coverage, not adherence to a specific implementation.

**Rationale:** The experiment arc showed that discovery strategy is site-dependent (Next.js `__NEXT_DATA__` vs sitemap vs Playwright BFS). Pinning a single script would require workers to adapt it per-site anyway. A guideline with a clear cascade (Path A → B → C) and explicit gotchas is more durable and flexible than a template. A capable model given a clear procedure and a concrete deliverable outperforms one following a rigid script.

### 2. Discovery cascade (in order)

1. **Path A — `__NEXT_DATA__`** (Next.js SSR sites): parse nav tree from initial HTML, union all versions including oldest. 100% recall in ~1–5s, no browser. Primary path when `<script id="__NEXT_DATA__">` found.
2. **Path B — Sitemap** (non-Next.js, verified coverage): use when sitemap exists and covers the target section.
3. **Path C — Playwright BFS** (fallback): `crawler.arun()` + `result.links.internal`, sequential (WAF-safe). 81.3% recall ceiling on section-scoped-nav sites — accepted, structural, not fixable by tuning.

### 3. `src/` gets only the pipe-scraper

`src/crawler/explore_site.py` + `discover_urls_playwright()` remain as-is — used for ad-hoc `searxng-cli explore_site` only. No discovery code changes in this task.

The only planned `src/` addition for this architecture is the **pipe-scraper** (Phase 1 of the capture skill): a raw/maximal scraping module that takes a URL list and writes `.md` files without any content filtering. This is a **separate later task** — its `src/` invocation is TBD and acts as a placeholder in the skill.

### 4. CLI contract: `search` + `scrape` only

No `crawl` CLI tool. The BFS crawlers (`crawl_site` BFS path, `explore_site`) are retired as the PRIMARY discovery mechanism (BFS measured insufficient at 67–81% recall). `explore_site` stays for ad-hoc use but is marked legacy/ad-hoc in `web-research/SKILL.md`.

### 5. Rename: `cleanup-and-index` → `capture-and-index`

The old name no longer fits — the worker now owns Discovery + Scrape + Drop + Cleanup + Index. `capture-and-index` describes the full pipeline scope.

Directory renamed: `skills/cleanup-and-index/` → `skills/capture-and-index/`.

Active references updated: `web-research/SKILL.md` spawn template, `decisions/explore01_discovery.md` IST text.

Historical OldThemes narratives that describe past state (e.g. `skill_consolidation_split/01_re_split_2026-05-24.md`) are preserved intact — do not rewrite history.

### 6. Reference collection: user-named, may be another project's

Old convention: "always `<current_project>_reference`, never per-source." Relaxed to: target collection is named by the user at task start. Default suggestion is `<current_project>_reference`, but the user may name another project's reference collection. Opus never picks the name autonomously.

---

## Open Questions Resolved (from `02_pipe_flow_and_roadmap.md`)

| Q# | Question | Resolution |
|---|---|---|
| 1 | Rename `cleanup-and-index`? | → `capture-and-index` |
| 2 | Baukasten vs monolithic skill? | → Monolithic worker skill. Discovery guideline as Phase 0 procedure. |
| 3 | Pinned scripts vs worker writes itself? | → Worker writes /tmp scripts situationally. No pinned reference script. |
| 4 | `web-research` scope? | → Opus: identify domain + confirm collection + spawn worker + verify. Worker: Discovery + Scrape + Drop + Cleanup + Index. |

---

## Remaining Work

| Step | What | Blocker |
|---|---|---|
| 1 | src/ pipe-scraper implementation | Separate later task — replaces Phase 1 placeholder in capture-and-index skill |
| 2 | End-to-end capture run of 305 docs.github.com/de/rest URLs | After pipe-scraper lands |
| 3 | Second website as generalizability proof | After (2) — test `__NEXT_DATA__` approach on an unknown Next.js doc site |

See `decisions/explore01_discovery.md` SOLL for the current production state and remaining migration.
