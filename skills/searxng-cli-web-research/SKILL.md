---
name: searxng-cli-web-research
description: SearXNG web research — CLI tool reference (search_web, search_engine_drilldown, scrape_url, download_pdf) + permanent-capture worker setup
---

# SearXNG Web Research — Skill

Ad-hoc web research via `searxng-cli`: search across 9 engines, drill into one engine for its URLs, scrape a page to filtered markdown, download a PDF. To permanently capture a whole domain into RAG, use the Permanent Capture Workflow at the bottom — that spawns a worker; this CLI is for in-chat lookups.

## CLI Invocation

All tools run via the `searxng-cli` wrapper (in PATH). Run them in the foreground — output lands directly in context, no `&`, no redirect.

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

1. `search_web` for the engine breakdown. For a deep dive, fire 2–4 parallel calls with query variations — each surfaces a different engines' URL set.
2. `search_engine_drilldown` per engine with a useful count to get its URLs. Drilldowns reuse the search_web cache (1h TTL).
3. `scrape_url` the relevant URLs. If a URL ends in `.pdf`, use `download_pdf` instead.

Write the query in the language you want results in — a German query returns German results.

Query diversity: when investigating an entity X, vary the angle across queries — X as the anchor (canonical sources), the broader category without X (academic landscape), alternatives/competitors (discussion engines), the underlying technique (academic engines). The same anchor on every query just returns the same top sources.

Mode flags: `--books` / `--pdf` / `--docs` restrict to google/duckduckgo/mojeek, append the modifier to the query, and post-filter the URLs. Use the same flag on `search_web` and its drilldowns.

---

## Permanent Capture Workflow

When the user wants to permanently capture a whole domain (or a set of PDFs) into RAG — "crawl X and index it", "RAG-fähig machen". A worker drives the capture; this is the Opus-side setup.

**1.** Identify the source: a seed domain URL (web-md), or PDF paths/URLs (pdf — download first via `download_pdf` if they are URLs).

**2.** Confirm the target collection with the user (MANDATORY ASK — never pick it yourself):
> "Target collection: `<project>_reference`. OUTPUT_DIR: `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<project>_reference/`. Confirm or override?"

Default is `<current_project>_reference`, but it may be another project's reference collection.

**3.** Spawn the worker. It activates the `searxng-cli-capture-and-index` skill and runs the pipe — but for web-md it **STOPS at the URL list (Phase 1b) for your cull review** before scraping (step 4). web-md: Discovery → URL Selection → **STOP (Opus cull)** → Scrape → Cleanup → Index; pdf: Acquisition → Cleanup → Index (no cull stop). Opus provides the seed/input, collection, and output dir.

Worker prompt (`/tmp/spawn-<name>.md`):

```markdown
You are a WORKER.
FIRST: activate the searxng-cli-capture-and-index skill via Skill(skill="searxng-cli-capture-and-index").
Inputs:
- MODE: <web-md | pdf>
- SEED_URL: <root domain URL>   (web-md)   OR   INPUT: <PDF file/dir>   (pdf)
- COLLECTION: <name>
- OUTPUT_DIR: ~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<name>/
web-md: STOP at Phase 1b — report the URL-list path + per-section breakdown and WAIT for my cull decision before scraping. Then report the funnel when done (incl. blocks-detected). No commit needed (output is data files).
```

```bash
# project_root = the CURRENT project's root — the project the session is working in.
# Pass it EXPLICITLY. Never a bare path that lets worker-cli walk up to a parent
# mono-repo git root: the worker MUST land in the current project's OWN worktree.
worker-cli spawn capture-<collection_lower> /tmp/spawn-<name>.md <current_project_root> sonnet
```

**Verify worktree placement after spawn (MANDATORY).** The spawn output reports a `Worktree:` path and a `Session:` name. Confirm:
- `Worktree:` is `<current_project_root>/.claude/worktrees/<name>`
- `Session:` is `worker-<basename(current_project_root)>-<name>`

If the worktree landed under a PARENT directory instead (session named after an enclosing repo), the current project is nested inside a larger git repo and `worker-cli` resolved to the parent git root. STOP and resolve before sending the cull go — make the current project its own git repo, or pass its real root explicitly.

**4.** Cull review (web-md only — the highest-leverage step). When the worker stops at Phase 1b it reports the URL-list path + a per-section breakdown. Review it against **what the user actually needs this session** — drop sections that are valid content but off-topic (e.g. a GitHub REST capture aimed at search/contents/git-trees does not need `actions`/`enterprise-admin`/`scim`). Send the worker the sections/patterns to drop. The worker applies the cull and proceeds. This is YOUR call, not the worker's — only you hold the user-need context.

**5.** When the worker reports the funnel, check `blocks detected` — non-zero means it found cookie/paywall MDs (not auto-stripped). Decide from the reported patterns whether a `src/` strip-script is warranted.

**Between step 4 and step 5, Opus does NOTHING.** No log-checking, no `rag-cli status` polling, no waking the worker for Cleanup/Index, no progress probes. The worker owns Scrape → Cleanup → Index end-to-end. Opus intervenes at exactly TWO points in the whole capture: (a) hand the worker the culled `/tmp` URL list + go (step 4), and (b) receive the final funnel report (step 5). The scrape / index wait mechanics are the worker's concern — never Opus's.
