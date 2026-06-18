---
name: searxng-cli-web-research
description: SearXNG web research — CLI tool reference (search_web, search_engine_drilldown, scrape_url, download_pdf) + permanent-capture worker setup
---

<!-- WIP COPY for iteration in trading/dev/skill_wip — edit here, sync back to the plugin skill when finalized. Source: ~/.claude/plugins/cache/brunowinter-plugins/searxng-cli/1.0.0/skills/searxng-cli-web-research/SKILL.md -->

# SearXNG Web Research — Skill

Ad-hoc web research via `searxng-cli`: search across 9 engines, drill into one engine for its URLs, scrape a page to filtered markdown, download a PDF. To permanently capture a whole domain (or a set of PDFs) into RAG, use the Permanent Capture Workflow at the bottom — that spawns a worker; this CLI is for in-chat lookups.

**This is the ONLY capture skill Opus activates.** Everything Opus needs to prompt and supervise a capture — web-md AND pdf — lives here. The worker activates `searxng-cli-capture-and-index` to execute the pipeline; Opus never reads that skill. (Both sides holding a skill is by design: the worker runs the steps, Opus knows the gates well enough to man them.)

## CLI Invocation

All tools run via the `searxng-cli` wrapper (in PATH). Run them in the foreground — no `&`, no redirect.

```bash
# Search — engine breakdown (counts per engine, no URLs)
searxng-cli search_web "machine learning retrieval"
searxng-cli search_web --docs "react hooks"

# URLs for one engine (from the search_web cache)
searxng-cli search_engine_drilldown "machine learning retrieval" --engine google

# Scrape a page to filtered markdown
searxng-cli scrape_url "https://example.com/article"

# Download a PDF
searxng-cli download_pdf "https://arxiv.org/pdf/2310.01526" --output-dir /tmp/papers/
```

On error (missing dependency, engine timeout): prints to stderr, exits non-zero.

## Tools

| Tool | Purpose |
|------|---------|
| search_web | Search across 9 engines. Returns an engine-breakdown table (counts per engine, no URLs) |
| search_engine_drilldown | URL list for one engine, from the cached search_web results |
| scrape_url | Page → filtered markdown (15k, PruningContentFilter). For in-chat reading |
| download_pdf | Download a PDF file to disk |

## Parameters

### search_web

| Parameter | Type | Description |
|-----------|------|-------------|
| query | str (required) | Search query, 2–5 keywords |
| --books | flag | Book lookup (+book modifier + book-domain whitelist). Mutually exclusive with --pdf / --docs |
| --pdf | flag | PDF lookup (+pdf modifier + PDF-host whitelist). Mutually exclusive with --books / --docs |
| --docs | flag | Docs lookup (+documentation modifier + noise blacklist). Mutually exclusive with --books / --pdf |

**Output:** engine breakdown — count per engine:

```
Engine breakdown for "rust async runtime":
  google               9
  duckduckgo           8
  ...
Use `searxng-cli search_engine_drilldown "rust async runtime" --engine <name>` to see URLs.
```

Engines: google, duckduckgo, mojeek, lobsters, semantic_scholar, openalex, crossref, stack_exchange, open_library.

### search_engine_drilldown

| Parameter | Type | Description |
|-----------|------|-------------|
| query | str (required) | Must match the prior search_web call |
| --engine | str (required) | One engine name (see list above) |
| --books / --pdf / --docs | flag | Must match the prior search_web call's mode |

**Output:** numbered URL list for that engine, in its native rank order:

```
Results from lobsters for "rust async runtime"

1. Async Rust in 2024
   URL: https://lobste.rs/s/xkq4j/async_rust_2024
   Snippet: …
```

### scrape_url

| Parameter | Type | Description |
|-----------|------|-------------|
| url | str (required) | URL to fetch as filtered markdown |

Returns 15k-capped markdown (PruningContentFilter) with a `# Content from: <url>` header. No options. For raw, full-fidelity capture of a whole domain, use the Permanent Capture Workflow — not this.

### download_pdf

| Parameter | Type | Description |
|-----------|------|-------------|
| url | str (required) | PDF URL |
| --output-dir | str (default ~/Downloads) | Save directory |

## Search Strategy

1. `search_web` for the engine breakdown. For a deep dive, fire 2–4 parallel calls with query variations.
2. `search_engine_drilldown` per engine with a useful count to get its URLs. Drilldowns reuse the search_web cache (1h TTL).
3. `scrape_url` the relevant URLs. If a URL ends in `.pdf`, use `download_pdf` instead.

Write the query in the language you want results in.

Query diversity: when investigating an entity X, vary the angle across queries — X as the anchor, the broader category without X, alternatives/competitors, the underlying technique.

Mode flags: `--books` / `--pdf` / `--docs` restrict to google/duckduckgo/mojeek, append the modifier to the query, and post-filter the URLs. Use the same flag on `search_web` and its drilldowns.

---

## Permanent Capture Workflow

When the user wants to permanently capture a whole domain (or a set of PDFs) into RAG — "crawl X and index it", "RAG-fähig machen". A worker drives the capture; this is the Opus-side setup. Opus activates ONLY this skill (see top); the worker activates `searxng-cli-capture-and-index`.

**How the capture handles content (informative):** the worker scrapes each page RAW/maximal — no content filter, full fidelity (unlike the in-chat `scrape_url`, which returns pre-filtered 15k markdown). It then cleans the content AD-HOC per page-shape (diagnose shapes → per-shape strip scripts → block/thin-page drop) before indexing, via the `searxng-cli-capture-and-index` skill. Raw in, worker cleans. PDFs follow a parallel path: category-check → convert (born-digital or scan/OCR) → fidelity audit → clean → index.

**Worker placement (HARD RULE — no exceptions, no per-task judgment):** the worker is ALWAYS spawned into a worktree IN THE CURRENT PROJECT — the project the session is running in. This applies to **PDF capture too**: even though the output files live OUTSIDE the project (in the rag-cli collection dir) and the worker invokes everything via absolute paths, it STILL gets a worktree in the current project. The worktree is not for the output — it just makes `worker-cli response` work and keeps placement uniform. NEVER `--no-worktree` (it breaks `worker-cli response` → forces the noisier `capture` fallback), NEVER a parent or other project's path. Pass `<current_project_root>` explicitly to `worker-cli spawn`; the worktree must land at `<current_project_root>/.claude/worktrees/<name>`. Verify after spawn (step 3). This is also enforced by a spawn hook — a worker spawned outside the current project's worktree is blocked.

**1.** Identify the source: a seed domain URL (web-md), or PDF paths/URLs (pdf — download first via `download_pdf` if they are URLs).

**2.** Confirm the target collection with the user (MANDATORY ASK — never pick it yourself):
> "Target collection: `<project>_reference`. OUTPUT_DIR: `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<project>_reference/`. Confirm or override?"

Default is `<current_project>_reference`, but it may be another project's reference collection.

For **PDF mode**, Opus ALSO decides the canonical PascalCase stem per PDF, matching the target collection's existing naming convention (e.g. `BaiPerron2003MultipleStructuralChange`, `SugiyamaSuzukiKanamori2012DensityRatioEstimation`). Naming is Opus's call — pass the exact stems in the prompt; the worker does NOT invent names. Stem chars: alphanumeric + underscore only (no brackets, dots, spaces).

**3.** Spawn the worker. It activates the `searxng-cli-capture-and-index` skill and runs the pipe. The two modes differ in where Opus intervenes:
- **web-md:** Discovery → URL Selection → **STOP (Opus cull, Phase 1b)** → Scrape → Cleanup → Index.
- **pdf:** Acquisition (category-check + convert) → **STOP (Opus audit review, Gate A)** → Cleanup → Index. Plus the conditional Gates B/C/D below.

Opus provides the seed/input, collection, output dir, and (pdf) the canonical stems.

Worker prompt — **web-md** (`/tmp/spawn-<name>.md`):

```markdown
You are a WORKER.
FIRST: activate the searxng-cli-capture-and-index skill via Skill(skill="searxng-cli-capture-and-index").
Inputs:
- MODE: web-md
- SEED_URL: <root domain URL>
- COLLECTION: <name>
- OUTPUT_DIR: ~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<name>/
STOP at Phase 1b — report the URL-list path + per-section breakdown and WAIT for my cull decision before scraping. Then report the funnel when done (incl. blocks-detected). No commit needed (output is data files).
```

Worker prompt — **pdf** (`/tmp/spawn-<name>.md`):

```markdown
You are a WORKER.
FIRST: activate the searxng-cli-capture-and-index skill via Skill(skill="searxng-cli-capture-and-index"), Mode 2 (PDF).
Inputs:
- INPUT: <PDF file path(s) or dir>
- CANONICAL STEMS (rename PDFs to these before convert; do NOT invent names):
    <orig1> → <Stem1>
    <orig2> → <Stem2>
- COLLECTION: <name>
- OUTPUT_DIR: ~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<name>/

Gates — STOP and report, WAIT for my Go:
- GATE A (ALWAYS): after the Phase 1 fidelity audit, BEFORE any cleaning / backmatter-strip / index,
  report the Class A–F counts per md + one real prose-window line per md, then STOP for Go.
- GATE B: Class-A loss a reconvert can't fix → STOP, report which symbol/formula + which PDF + your read of the cause.
- GATE C: a scan part crashes on dense pages (ToC/index/reference lists) → STOP, report the page range + what it is.
- GATE D: md:null (convert produced no output) → report the PDF name, no auto-retry.

Completion Checklist: category decision + evidence per PDF · convert result (md? word/page counts) ·
Phase 1 audit table · index summary line · both docs confirmed in the collection.
No git commit (data files only).
```

```bash
# project_root = the CURRENT project's root — the project the session is working in.
# Pass it EXPLICITLY, never a bare path. The worker MUST land in the current project's OWN worktree.
worker-cli spawn capture-<collection_lower> /tmp/spawn-<name>.md <current_project_root> sonnet
```

**Verify worktree placement after spawn (MANDATORY).** The spawn output reports a `Worktree:` path and a `Session:` name. Confirm:
- `Worktree:` is `<current_project_root>/.claude/worktrees/<name>`
- `Session:` is `worker-<basename(current_project_root)>-<name>`

If the worktree landed under a PARENT directory instead (session named after an enclosing repo): STOP and resolve before sending the cull go — make the current project its own git repo, or pass its real root explicitly.

### Web-MD mode — Opus gates

**4.** Cull review (web-md only). When the worker stops at Phase 1b it reports the URL-list path + a per-section breakdown. Review it against what the user actually needs this session — drop sections that are valid content but off-topic (e.g. a GitHub REST capture aimed at search/contents/git-trees does not need `actions`/`enterprise-admin`/`scim`). Send the worker the sections/patterns to drop. The worker applies the cull and proceeds. This is YOUR call, not the worker's.

**5.** When the worker reports the funnel, check `blocks detected` — non-zero means it found cookie/paywall MDs (not auto-stripped). Decide from the reported patterns whether a `src/` strip-script is warranted.

**Between step 4 and step 5, Opus does NOTHING.** No log-checking, no `rag-cli status` polling, no waking the worker for Cleanup/Index, no progress probes. The worker owns Scrape → Cleanup → Index end-to-end. For web-md, Opus intervenes at exactly TWO points: (a) hand the worker the culled `/tmp` URL list + go (step 4), and (b) receive the final funnel report (step 5).

### PDF mode — Opus gates

PDF capture has NO Phase-1b cull stop. Instead Opus mans the gates below, baked into the PDF worker prompt above. The worker runs the pipeline (Phase 0 Acquisition → Phase 1 Cleanup → Index); Opus owns the setup (collection + canonical stems) and these gates.

| Gate | When it fires | Worker action | Who decides |
|---|---|---|---|
| **A — Audit-before-clean (ALWAYS ON)** | after the Phase 1 fidelity audit, before ANY cleaning / backmatter-strip / index | STOP, present Class A–F counts per md + one real prose-window line per md | **OPUS** — review convert fidelity; Go to clean+index. If the conclusion is "reconvert" → escalate to the USER first (see below) |
| **B — Class-A loss** | convert dropped formula content (`??`, ``, broken sub/sup) a reconvert can't recover | STOP, report which symbol/formula + which PDF + cause | **USER** — accept lossy / source a better PDF / split the doc |
| **C — Dense-page crash (scans)** | a scan part repeatedly crashes the OCR VLM on dense pages (ToC / index / reference lists) | STOP, report the flagged page range + what it is | **USER** — OK to cut those pages? |
| **D — md:null** | convert produced no output at all | report the PDF name, NO auto-retry | **USER** — better source / re-run |

**Reconvert is NEVER autonomous.** Opus does not tell the worker to reconvert on its own judgment. Any reconvert — whether the conclusion of a Gate-A audit review or triggered by a Gate-B loss — is presented to the USER first (better PDF? accept the loss? split?) and only run on the user's OK. Gate A is the standard always-on oversight gate; Gates B/C/D are conditional and fire only on a bad or scanned PDF, and all three escalate to the user because the call ("better PDF / split / accept loss / cut pages") is a corpus-owner decision.

Opus's PDF interventions: Gate A always, Gates B/C/D when they fire, and the final Completion Report. Between gates, same rule as web-md — Opus does NOTHING (no log-polling, no progress probes); the worker owns convert → clean → index.
