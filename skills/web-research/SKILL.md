---
name: web-research
description: SearXNG web research — CLI tool reference (search_web, search_batch, search_engine_drilldown, scrape_url, scrape_url_raw, explore_site, download_pdf)
---

# SearXNG Web Research — Skill

Web research CLI plugin with 9 active search engines, Crawl4AI-based scraping, and site exploration. `search_web` returns an engine-breakdown table (no URLs). Use `search_engine_drilldown` to retrieve the URL list for a specific engine. Each `search_web` invocation is a fresh CLI process — fire calls in parallel for maximum throughput. Use `search_batch` when running multiple queries in one process to amortize Chrome startup cost.

## CLI Invocation

All tools are invoked via the `searxng-cli` wrapper (installed at `~/.local/bin/searxng-cli`, in PATH):

```
searxng-cli <cmd> [args]
```

### Output Handling (CRITICAL)

`search_web` / `search_batch` / `search_engine_drilldown` / `explore_site` produce **signal output** — run them in the **foreground**, no `&`, no `> /tmp/...` redirect. The full result lands in the tool result and is immediately available in context.

`scrape_url_raw` is the exception: it writes to a `.md` file by design (for RAG indexing). The other scrape/explore commands print to stdout for direct context use.

### Quick Reference — All 7 Tools

```bash
# Search (9 engines) — returns engine breakdown, no URLs
searxng-cli search_web "machine learning retrieval"
searxng-cli search_web "rust async runtime" --engines "google,duckduckgo,openalex"
searxng-cli search_web "RAG pipeline python" --language de --time-range month

# Search multiple queries in one warm-Chrome session
searxng-cli search_batch "SPLADE retrieval" "sparse vector search" "learned sparse retrieval"

# Get URL list for a specific engine (reads from cache or runs fresh search)
searxng-cli search_engine_drilldown "rust async runtime" --engine google
searxng-cli search_engine_drilldown "rust async runtime" --engine lobsters
searxng-cli search_engine_drilldown "rust async runtime" --engine openalex

# Scrape
searxng-cli scrape_url "https://example.com/article"
searxng-cli scrape_url "https://docs.example.com/api" --max-content-length 30000

# Scrape to file (RAG indexing)
searxng-cli scrape_url_raw "https://example.com/article" /tmp/rag_output/

# Explore site structure
searxng-cli explore_site "https://docs.example.com" --max-pages 50

# Download PDF
searxng-cli download_pdf "https://arxiv.org/pdf/2310.01526" --output-dir /tmp/papers/
```

On error (import failure, missing dependency, engine timeout): the CLI prints to stderr and exits non-zero.

## Tools

| Tool | Purpose |
|------|---------|
| search_web | Search across 9 engines in parallel. Returns engine-breakdown table (result counts per engine) |
| search_batch | Search multiple queries in one warm-Chrome session. Same breakdown output per query as search_web |
| search_engine_drilldown | Fetch URL list for a specific engine from cached search results (or re-runs search on cache miss) |
| scrape_url | Fetch page content as filtered markdown (PruningContentFilter). For in-conversation reading |
| scrape_url_raw | Fetch page content as raw markdown and save as .md file. For RAG indexing |
| explore_site | Discover URLs via sitemap + BFS prefetch. Returns structured URL list |
| download_pdf | Download PDF file from URL to local disk |

## Parameter Reference

### search_web

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| query | str | required | Search query (2–5 keywords) |
| --language | str | en | ISO language code (e.g. "de") |
| --time-range | day/month/year | None | Restrict results by recency |
| --engines | str | None | Comma-separated engine list (e.g. "google,duckduckgo,openalex") |
| --books | flag | off | Lookup books — +book modifier, book-domain whitelist post-filter. Mutually exclusive with `--pdf` / `--docs` |
| --pdf   | flag | off | Lookup PDFs — +pdf modifier, PDF-host whitelist post-filter. Mutually exclusive with `--books` / `--docs` |
| --docs  | flag | off | Lookup documentation — +documentation modifier, noise-blacklist post-filter. Mutually exclusive with `--books` / `--pdf` |

**Output:** Engine breakdown table — result count per engine. Format:
```
Engine breakdown for "rust async runtime":
  google               9
  duckduckgo           8
  mojeek               6
  lobsters             4
  openalex             11
  crossref             7
  stack_exchange       5
  semantic_scholar     3
  open_library         0

Use `searxng-cli search_engine_drilldown "rust async runtime" --engine <name>` to see URLs per engine.
```

**Pool cap:** pool sizes per engine are capped at K = google's result count (fallback 10 if google returned 0 or wasn't queried). If google returns 8 URLs, every engine is capped at 8. If google was CAPTCHA'd or not in the engine set, every engine is capped at 10. Engines that naturally return fewer than K URLs are unaffected. Cap prevents a single API engine (CrossRef, OpenAlex, Stack Exchange) from flooding a drilldown with 200 URLs.

**Engine set (9 active):** google, duckduckgo, mojeek, lobsters, semantic_scholar, openalex, crossref, stack_exchange, open_library.

Use `--engines` to restrict to specific engines (e.g. `--engines "openalex,crossref"` for academic-only searches).

**Counts in filter modes:** `--books` / `--pdf` / `--docs` apply a URL post-filter before pool assignment. Counts in the breakdown reflect only URLs that survived the filter — expect lower counts than unfiltered mode.

### search_batch

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| queries | str+ | required | One or more search queries (positional — each query as a separate quoted argument) |
| --language | str | en | ISO language code (e.g. "de") |
| --time-range | day/month/year | None | Restrict results by recency |
| --engines | str | None | Comma-separated engine list |
| --books | flag | off | Book lookup mode. Mutually exclusive with `--pdf` / `--docs` |
| --pdf   | flag | off | PDF lookup mode. Mutually exclusive with `--books` / `--docs` |
| --docs  | flag | off | Docs lookup mode. Mutually exclusive with `--books` / `--pdf` |

**Output:** Engine breakdown per query, separated by `---`.

**Use case:** 3–5 query variations on the same topic in a single process. Chrome starts once (~5s), then each query runs in ~1s — amortized startup cost vs. ~5s cold-start per separate `search_web` invocation.

### search_engine_drilldown

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| query | str | required | Search query (must match a prior search_web call for cache hit) |
| --engine | str | required | Engine name: google, duckduckgo, mojeek, lobsters, semantic_scholar, openalex, crossref, stack_exchange, open_library |
| --language | str | en | Must match original search_web call (part of cache key) |
| --engines | str | None | Must match original search_web call (part of cache key) |
| --time-range | day/month/year | None | Must match original search_web call (part of cache key) |
| --books | flag | off | Must match original search_web call (part of cache key) |
| --pdf   | flag | off | Must match original search_web call (part of cache key) |
| --docs  | flag | off | Must match original search_web call (part of cache key) |

**Output:** Numbered list of URLs for the specified engine, in that engine's native rank order (position 1 first). Position numbers may have gaps — a gap means that URL is owned by another engine (appeared at a better position there).

```
Results from lobsters for "rust async runtime"

1. Async Rust in 2024
   URL: https://lobste.rs/s/xkq4j/async_rust_2024
   Snippet: …

3. Why async Rust?
   URL: https://lobste.rs/s/abc/why_async_rust
```

| Cache state | Behavior |
|-------------|----------|
| Hit + fresh (≤1h) | Returns engine pool directly |
| Miss or expired | Re-runs search_web_workflow, populates cache, then returns pool |
| Engine not in pools | Error message listing available engines |

**Key rule:** `--language`, `--engines`, `--time-range`, and `--books`/`--pdf`/`--docs` are part of the cache key — they must match the original `search_web` call exactly for a cache hit. Any mismatch triggers a fresh search.

### scrape_url

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| url | str | required | URL to fetch and convert to markdown |
| --max-content-length | int | 15000 | Character limit for returned content |

**Output:** Filtered markdown with `# Content from: <url>` header.

**Plugin routing:** arxiv.org, github.com, reddit.com URLs are automatically rejected with a routing message — use the dedicated plugins instead.

### scrape_url_raw

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| url | str | required | URL to scrape and save as markdown file |
| output_dir | str | required | Directory to save the .md file (created if not exists) |

**Output:** Confirmation with file path and char count.

### explore_site

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| url | str | required | Root URL to explore |
| --max-pages | int | 200 | Max pages to discover |
| --url-pattern | str | None | Regex filter for discovered URLs |

**Output:** Structured URL list discovered via sitemap → BFS cascade.

### download_pdf

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| url | str | required | URL of the PDF to download |
| --output-dir | str | ~/Downloads | Directory to save the downloaded PDF |

**Output:** Confirmation with file path and file size.

## Search Strategy

### Two-call drilldown workflow

`search_web` gives you a breakdown of how many results each engine has. Then use `search_engine_drilldown` per interesting engine to see the actual URLs:

```bash
# Step 1: get breakdown
searxng-cli search_web "rust async runtime"

# Step 2: drill into engines that look interesting
searxng-cli search_engine_drilldown "rust async runtime" --engine lobsters
searxng-cli search_engine_drilldown "rust async runtime" --engine openalex
searxng-cli search_engine_drilldown "rust async runtime" --engine google
```

Drilldowns use the cache from the search_web call (1h TTL). No extra engine fanout when cache is fresh.

### Parallel queries

Fire multiple `search_web` calls in parallel, each with a query variation. Each call fans out to 9 engines internally. 2–4 parallel calls is a good default for deep-research tasks.

```bash
# 4 parallel calls — one brand-anchored, three orthogonal angles
searxng-cli search_web "SPLADE retrieval"
searxng-cli search_web "learned sparse retrieval BM25 benchmark"
searxng-cli search_web "neural information retrieval embeddings 2025"
searxng-cli search_web "ColBERT TILDE Snowflake retrieval comparison"
```

### Query Diversity (CRITICAL)

When 2+ queries share the same anchor keyword, engine ranking puts the same canonical sources at the top of every query. Different engines surface different URL sets — use drilldown to pick the most valuable engines per query.

**Pattern when investigating a known entity X:**
- **One** query with X as primary anchor → canonical sources (docs, github, homepage) from google/duckduckgo
- **One** query about the broader category WITHOUT mentioning X → landscape from academic engines
- **One** query about alternatives / competitors → comparisons from lobsters/stack_exchange
- **One** query about the underlying technique → concepts from openalex/crossref

**Query length:** 2–5 keyword tokens. Add a year token only when recency matters.

### Warm-Chrome batch (search_batch)

For 3–5 variations on the same topic in one process, prefer `search_batch`:

```bash
searxng-cli search_batch "SPLADE retrieval" "learned sparse retrieval BM25 benchmark" "neural IR embeddings" "ColBERT TILDE retrieval comparison"
```

Same Query Diversity rule applies. Chrome boots once (~5s), then each query runs in ~1s.

### Academic / paper topics

For topics where you want academic results, drill into `openalex`, `crossref`, `semantic_scholar` after the initial search_web:

```bash
searxng-cli search_web "SPLADE retrieval NDCG"
searxng-cli search_engine_drilldown "SPLADE retrieval NDCG" --engine openalex
searxng-cli search_engine_drilldown "SPLADE retrieval NDCG" --engine crossref
```

Or restrict engines upfront: `--engines "openalex,crossref,semantic_scholar"`.

### Books Lookup Mode

`--books` restricts the search to Google, DuckDuckGo, and Mojeek (plus Open Library which is already a catalog), appends `book` to the query, and post-filters through a 68-domain whitelist.

```bash
searxng-cli search_web --books "tolkien"
searxng-cli search_engine_drilldown --books "tolkien" --engine google
```

### PDF Lookup Mode

`--pdf` restricts the search to Google, DuckDuckGo, and Mojeek, appends `pdf` to the query, and post-filters through a PDF-serving host whitelist.

```bash
searxng-cli search_web --pdf "transformer attention mechanism"
searxng-cli search_engine_drilldown --pdf "transformer attention mechanism" --engine google
```

### Docs Lookup Mode

`--docs` restricts the search to Google, DuckDuckGo, and Mojeek, appends `documentation` to the query, and post-filters through a noise blacklist (forums, blogs, code-hosting, tutorial aggregators).

```bash
searxng-cli search_web --docs "react hooks"
searxng-cli search_engine_drilldown --docs "react hooks" --engine google
```

### Language

For German-language research, add `--language de` to all queries and drilldowns.

### Workflow

1. **Search broadly:** Fire 2–4 parallel `search_web` queries with variations (or `search_batch` for topically-related queries)
2. **Drilldown into interesting engines:** Call `search_engine_drilldown` per engine that has a useful count
3. **Filter results:** Categorize as scrape targets vs. plugin-routed (see Plugin Routing below)
4. **Scrape aggressively:** Call `searxng-cli scrape_url` on all relevant non-plugin URLs
5. **Report everything:** Return all findings using the Report Format below

For multi-topic tasks: before moving to the next topic, verify ≥5 unique URLs scraped and ≥2 HIGH quality sources. Fire 2–3 additional topic-specific queries if below minimum.

**Cookie wall detection:** If scrape output contains only consent/GDPR text, mark as `[cookie wall]` — do NOT rate as HIGH quality. Use the search snippet as fallback.

**PDF URLs:** If a result URL ends in `.pdf`, call `download_pdf` instead of `scrape_url`.

## Plugin Routing (CRITICAL)

**Do NOT scrape these domains — report them for plugin-based access:**

| Domain | Action |
|--------|--------|
| arxiv.org | Report: "Use RAG plugin (mcp__rag__search_hybrid) or /rag:pdf-convert" |
| github.com | Report: "Use GitHub Research plugin (github__get_file_content)" |
| reddit.com | Report: "Use Reddit plugin (reddit__search_posts)" |
| youtube.com | Skip entirely. Video content cannot be scraped. |

`scrape_url` and `scrape_url_raw` enforce this routing at the CLI level — they will return a routing message and exit without scraping.

## Report Format

```
## Scraped Content

### 1. <Title>
**URL:** <url>
**Domain:** <domain>
**Content Quality:** [high/medium/low]
**Key Content:**
[2-5 sentences: What does this page actually contain? Concrete takeaways, code examples, benchmark numbers, methodologies.]

### 2. <Title>
...

[ALL scraped URLs, not limited to 10]

## Plugin-Routed URLs

These URLs require dedicated plugins for proper access:

### arxiv.org (Use RAG plugin)
- <url> — <title>

### github.com (Use GitHub Research plugin)
- <url> — <title>

### reddit.com (Use Reddit plugin)
- <url> — <title>

## Search Metadata
**Queries Used:** query1, query2, query3, ...
**Total Results Reviewed:** N
**URLs Scraped:** N
**Plugin-Routed:** N
**Skipped (garbage/thin):** N
```

## Content Assessment

**HIGH quality:** Tutorials with code, benchmarks with numbers, API docs with examples, research papers with methodology
**MEDIUM quality:** Blog posts with some substance, overviews with useful links, discussion with concrete answers
**LOW quality:** Thin wrapper around other content, mostly links, surface-level overview without depth

## Scraping Tips

- **Default `--max-content-length` is 15000** — sufficient for most articles/docs. Increase for long documentation pages.
- **JavaScript-rendered content** is supported — Playwright renders the page before extraction.
- **Scrape before summarizing:** Never summarize from search snippets alone. If a page has content, scrape it.
- **Quantity over perfection:** 20 scraped URLs with quick assessments > 5 carefully curated summaries.

## Known Limitations

- **Per-engine result ceiling varies:** google ~9-11, duckduckgo/mojeek/semantic_scholar ~10, lobsters 0-20, openalex up to 200, crossref up to 200, stack_exchange up to 100, open_library up to 100. Counts in the breakdown reflect URLs that survived URL dedup.
- **Scraper optimized for content sites** — articles, docs, wikis work best
- **scrape_url uses PruningContentFilter** — may damage code blocks. Use `scrape_url_raw` for full fidelity
- **Login-protected pages** will return login forms, not content
- **PDF URLs (.pdf)** — use `download_pdf` to save the file locally. Do NOT use `scrape_url` on PDFs.

## When to Stop

Stop when ALL of:
- Exhausted 4+ query variations
- Drilled down into the engines with the most relevant counts
- Scraped all non-plugin URLs from interesting drilldowns
- Additional queries return mostly duplicates

---

## Permanent Capture Workflow

For when ad-hoc lookup isn't enough — the user wants to permanently capture a domain (docs, blog, repo) or a set of PDFs into RAG for later semantic search.

### When to use this workflow

- "Crawl X and index it" / "permanent erhalten" / "RAG-fähig machen"
- After search surfaces multiple URLs from one domain that warrant indexing
- A folder of PDFs (research papers, books, conference proceedings) needs to be indexed

#### Setup (Opus-side, before spawning worker)

**1. Identify Source**

Web domain (e.g. `docs.crawl4ai.com`) OR a list of PDFs (paths or URLs).

**2a. For Web Domains: Explore + Filter URLs**

Two-stage filter — preemptive at discovery time, post-hoc after inspection.

**Stage 1 — preemptive (discovery time):** strips known structural noise as the list is written.

```bash
# Strip obvious noise globs upfront (e.g. Sphinx index/module pages)
searxng-cli explore_site https://docs.example.com --strategy sitemap --output /tmp/example_urls.txt \
    --exclude-patterns "*/genindex.html,*/_modules/*,*/search.html"
```

**Inspect:** `cat /tmp/example_urls.txt` or `head /tmp/example_urls.txt` — scan for patterns that only surface on seeing the full list.

**Stage 2 — post-hoc (after inspection):** drops additional patterns or exact URLs in-place.

```bash
# Preview first (file unchanged)
searxng-cli filter_urls /tmp/example_urls.txt --exclude-patterns "*/used-by.html" --dry-run

# Apply (atomic rewrite)
searxng-cli filter_urls /tmp/example_urls.txt --exclude-patterns "*/used-by.html"
```

Exact URLs (no wildcards) match literally. `--dry-run` prints dropped URLs + kept count to stderr without touching the file.

Proceed with the cleanup + index phases of Mode 1 on the trimmed `/tmp/example_urls.txt`.

**2b. For PDFs: Decide Which to Convert**

Review PDF candidates with the user. Skip paywalls, redundant copies, off-topic PDFs. Build a list of paths (or URLs to download first via `searxng-cli download_pdf`).

**3. Decide Collection Name**

PascalCase, descriptive: `SearXNG_Docs`, `Crawl4AI_Reference`, `RAG_Survey_2024`. Becomes the RAG collection name.

#### Common Inputs

Every worker spawn provides:

| Var | Meaning | Example |
|---|---|---|
| `MODE` | `web-md` or `pdf` | `web-md` |
| `INPUT` | Source path | `/tmp/searxng_urls.txt` or `/path/to/paper.pdf` |
| `COLLECTION` | RAG collection name — `<project>_reference` (lowercase, underscore). One reference collection per project, all indexed material lands here. | `searxng_reference` |
| `OUTPUT_DIR` | Where cleaned `.md` files land — folder name MUST match `COLLECTION` exactly | `~/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng_reference/` |

#### Spawn Worker

Write to `/tmp/spawn-<worker_name>.md`:

```markdown
# Worker Task: Capture-and-Index <COLLECTION_NAME>

You are a WORKER.

FIRST: activate the web-research skill via Skill(skill="web-research").

Then follow its "Permanent Capture Workflow" section, Mode <web-md | pdf>, with these inputs:

- MODE: <web-md | pdf>
- INPUT: <absolute path to URL list .txt OR PDF file/dir>
- COLLECTION: <COLLECTION_NAME>
- OUTPUT_DIR: ~/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/<COLLECTION_NAME>/

Report when done. No commit needed (output is data files, not code).
```

```bash
worker-cli spawn cleanup-<collection_lower> /tmp/spawn-<worker_name>.md \
    <current_project_root> sonnet
```

#### Wait for Worker, Verify

```bash
rag-cli search --query "<topic from indexed content>" --top-k 3
```

---

### Mode 1: Web-MD Capture (search → crawl → clean → index)

Input: absolute path to a URL list `.txt` (one URL per line) OR a directory of pre-crawled `*.md` files.

- If URL list: Phase 0 crawls all URLs via Crawl4AI.
- If pre-crawled directory: skip Phase 0.

Pipeline: [optional crawl] → block-level chrome cleanup (5-shape + Sphinx-specifics) → index.

#### Phase 0 — Acquisition

```bash
mkdir -p $OUTPUT_DIR
cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxng && \
./venv/bin/python -m src.crawler.crawl_site \
    --url-file $INPUT \
    --output-dir $OUTPUT_DIR \
    --concurrency 10
```

Report: `N URLs crawled, M succeeded, K failed`. List failed URLs.

If `>50%` failed → STOP, report to Opus, do not proceed.

If INPUT is a directory of `.md` files: skip Phase 0, set `OUTPUT_DIR=INPUT`.

#### Phase 1 — Cleanup

Diagnose first. Don't write cleanup regex before classifying shape.

##### Diagnose Pass

Build a small script that scans ALL `.md` files in OUTPUT_DIR, extracts per-file fingerprints (h1 count, h2 count, prose density, table presence, source domain from `<!-- source: URL -->` comment, total LOC). Cluster by fingerprint similarity to identify 4-5 shape groups. ~50 LOC, ~5s runtime.

##### The Five Shapes

1. **Blog-Shape** — one h1 in first 20%, prose-heavy, h2 sections, footer markers (Continue reading / Comments / Copyright / breadcrumb).
   - Strip pre-h1 chrome + footer from earliest tail-marker.
   - Keep: source comment, h1 title, posted/updated metadata, ToC, body content.

2. **Paper-Landing-Shape** — academic title h1/h2, author list, abstract, metadata table (Subjects, DOI). Short overall.
   - Strip site nav, sidebar forms, "View PDF/HTML" link clusters, license footer.
   - Keep title, authors, abstract, subject table, DOI.
   - Variant: ACL Anthology uses `## [Title]` not `# Title` — anchor on first `## ` h2 if no h1.

3. **Forum-Thread-Shape** — markdown-table layout, top-nav row, story/comment rows.
   - Site-specific (HN: anchor on first `vote?id=` link, strip everything before).
   - Keep story title row + comment threads. Markdown-table syntax stays (embedding handles it).

4. **Repo-Heavy-Chrome-Shape** — very long pre-content chrome (>100 lines), many h1 chrome lines (search box, feedback, sponsor, repo headers), real title appears late.
   - GitHub issue/PR: extract `#<N>` from URL, find `^# .+ #<N>` line, strip everything before.
   - GitHub repo home: anchor on README's first h1 or file-tree end-marker.

5. **Index-Aggregator-Shape** — page is mostly link list, no real prose. Wikipedia category pages, blog index pages, doc TOC pages.
   - Flag as low-content. Optionally exclude from indexing (skip the file).

##### Web-Specific: Sphinx Documentation

Sphinx-generated docs (SearXNG, ReadTheDocs, many Python project docs) have a distinctive pattern. Header avg 10.7 lines, footer avg 52.6 lines, total noise ~37% of chars (verified on 278 files).

Header (top of file, before first `# ` heading):
- `### Navigation` block with index/modules/next/previous links
- Breadcrumb trail with `»` separators
- Strip: everything between `<!-- source:` line and first `# ` heading

Footer (after last content line):
- Logo image line: `[ ![Logo of ...](...) ](...)` — RELIABLE content-end marker
- `### [Table of Contents]`, `### Project Links`, second `### Navigation`, `### Quick search`, `### This Page`, `© Copyright`
- Strip: everything from `^\[ !\[Logo of ` to EOF

Inline noise (`_modules_*` files only): `[docs][](URL)` markers before class/function defs. Regex: `\[docs\]\[]\(https://[^)]*\)`.

##### Per-Shape Cleaner Pattern

For each detected shape, write ONE small script in `/tmp/clean_<shape>_<COLLECTION_lower>.py` (~20-30 LOC each). NOT one big function with N patterns.

##### Script Safety Rules (CRITICAL — previous runs failed here)

- Every `while` loop MUST increment in ALL code paths (skip/continue/break/normal — all)
- Test on 1 file FIRST, then run on all
- ALWAYS `python3` (not `python`)
- Use `Path(__file__).parent` — NEVER hardcode absolute paths like `/Users/...`
- Preserve `<!-- source: URL -->` comments in every file (they are crawl metadata)
- Overwrite originals in-place

##### Edge Cases

- Files with no `# ` heading (auto-generated redirect pages) → keep content between source comment and logo line
- Files nearly empty after cleanup (<5 lines) → still output, don't delete
- `user_None.md` / `user_{}.md` files = crawled error pages, minimal content expected

---

### Mode 2: PDF Capture (search → download → convert → clean → index)

Input: absolute path to a single PDF file OR a directory of `*.pdf` files.

Pipeline: MinerU convert → OCR/LaTeX cleanup → index.

#### Phase 0 — Acquisition

If INPUT is a single PDF file:

```bash
mkdir -p $OUTPUT_DIR
STEM="<derive descriptive PascalCase name from filename or first page>"
cd /Users/brunowinter2000/Documents/ai/Mineru && \
./venv/bin/python workflow.py convert \
    --input "$INPUT" \
    --output "$OUTPUT_DIR/$STEM.md"
```

If INPUT is a directory: loop over `*.pdf`, derive STEM per file (read first page or arxiv abstract if filename is cryptic), run convert per file. Report progress: `[N/M] <STEM>: phase 0 done`.

**Concrete loop template — use exactly this shape, including both guards:**

```bash
for PDF in "$PDF_DIR"/*.pdf; do
    STEM="<derive descriptive PascalCase name — see Note below>"
    # GUARD 1 — empty STEM means "$OUTPUT_DIR/.md" which silently overwrites every iteration
    [ -z "$STEM" ] && { echo "BUG: empty STEM for $PDF — abort batch"; exit 1; }
    cd /Users/brunowinter2000/Documents/ai/Mineru && \
        ./venv/bin/python workflow.py convert \
            --input "$PDF" \
            --output "$OUTPUT_DIR/$STEM.md"
    # GUARD 2 — convert may exit 0 but produce empty/missing output
    [ -s "$OUTPUT_DIR/$STEM.md" ] || { echo "WARNING: empty or missing output for $STEM"; }
done
```

Note on STEM derivation: cannot be `basename "$PDF" .pdf` mechanically — original filenames are often hashes, ISBN-strings, library-uploader patterns. Derive a descriptive PascalCase name per file: read the first page header / title metadata, condense to ~30 chars (e.g. `AslamMontague2001MetasearchModels`, `ManningRaghavanSchutze2008IRTextbook`). Filename collisions inside one batch must be avoided — append year or first-author-initial when needed.

**STEM character constraints (hard rules):** alphanumeric + underscore ONLY. NEVER include brackets `[ ]`, parentheses `( )`, dots `.` (other than the trailing `.md` extension), commas, spaces, or any glob metachar. MinerU's internal `find_output_md` uses the stem as a glob pattern; characters like `[10.1007_978-3-642-14267-3]` from DOI-style filenames get interpreted as character classes and produce zero matches. The `glob.escape()` patch in MinerU `workflow.py` (2026-05-08) covers this defensively, but the cleanest preventive is sanitizing the stem at derivation time.

**Why both guards matter:** an empty `$STEM` at line 4 produces output path `$OUTPUT_DIR/.md`. MinerU happily writes to it, exits 0, and the next iteration overwrites the same file. Without GUARD 1, ten papers collapse into one `.md` and the bug is invisible until the directory is listed. GUARD 2 catches the rarer case where MinerU silently produces an empty file — index-time would skip it without explanation.

**ZSH trap to know about — bash assoc-arrays don't transfer.** A natural-looking pattern is `declare -A STEMS; STEMS["MyFile.pdf"]="MyStem"; for f in *.pdf; do stem="${STEMS[$f]}"; ...; done`. This works in bash. In zsh (default macOS shell, default in worker tmux sessions) `${STEMS[$f]}` does NOT expand when the key contains `.` or `-` — `$stem` silently becomes empty, GUARD 1 fires, and the batch aborts. Two safer patterns:

1. **Python script for any batch >3 files** (recommended): zero shell-quoting risk, easy to add per-file timing/error handling, single tool-call per batch. Build a small `subprocess.run([...])` loop over a `dict[str, str]` of `pdf_basename → stem` mappings.
2. **Bash-only loop with literal stems** (small batches): write the STEM literally inside the loop body per file, avoid associative arrays entirely.

Do NOT carry a bash assoc-array pattern into a zsh worker session expecting it to work — the GUARD will catch it but the whole batch is wasted.

If MinerU fails for any PDF: log + skip + continue. Report failed PDFs at end.

##### Background-Polling for Phase 0 Convert

Use this pattern whenever **any** of the following is true:
- Input PDF is >50 MB
- Batch over all PDFs in a directory (loop template above)
- Single PDF and wallclock is expected to exceed 60 s (rule of thumb: any academic paper >10 MB, any book PDF)

```bash
# Run as Bash(run_in_background=true)
( while pgrep -f 'workflow.py convert' > /dev/null 2>&1; do sleep 15; done; echo CONVERT_DONE ) &
wait
```

The `sleep 15` *inside* the loop is normal blocking sleep — it does NOT trigger CC tool-completion events. CC sees ONE backgrounded call, ONE completion when MinerU is truly gone. Zero cascade. Mirror of the Phase 2 indexing pattern.

##### Post-Convert Verify

After every convert (single file or end of batch loop), verify the output is non-empty and substantial:

```bash
[ -s "$OUTPUT_DIR/$STEM.md" ] && wc -w "$OUTPUT_DIR/$STEM.md"
```

Threshold: **≥ 100 words** = meaningful conversion. Below threshold:
- Log `WARNING: $STEM.md has <N> words — expected ≥100`
- Retry: add `--timeout 300` (or higher) to the `workflow.py convert` call
- If retry also fails: skip file, add to failed list, continue batch

##### Why Background-Polling for Convert

Claude Code auto-backgrounds any Bash call whose wallclock exceeds ~60 s AND whose output stream has been idle for >30 s. MinerU convert on large PDFs routinely meets both conditions — it's CPU-bound and silent during the OCR/LaTeX extraction phase.

**What happens without the polling pattern:**

1. Worker fires `Bash(workflow.py convert --input paper.pdf --output out.md)` with output redirected to a log file.
2. CC sees process running, output stream quiet → auto-backgrounds the call.
3. Bash tool-result returns immediately with exit code 0 (CC's backgrounding exit, NOT MinerU's exit).
4. Worker reads exit=0 → assumes convert succeeded, moves to Phase 1 cleanup.
5. MinerU is still running in the background (or was killed by CC). The `.md` output file is empty or partially written.
6. GUARD 2 in the batch loop (`[ -s "$OUTPUT_DIR/$STEM.md" ]`) fires — but only if the worker revisits the file. If the worker already reported "Phase 0 done" and moved on, the empty file silently enters Phase 1.

**What the polling pattern does:** CC sees ONE backgrounded Bash call. `wait` blocks until `pgrep -f 'workflow.py convert'` finds no process. Only then does `echo CONVERT_DONE` fire. Worker receives ONE completion notification after MinerU is truly gone, then runs the post-convert verify.

#### Phase 1 — Cleanup

PDFs come from MinerU as Markdown. Cleanup focuses on inline OCR artifacts, not block chrome.

##### Pre-cleanup: Backup + Word Count Baseline

```bash
cp "$OUTPUT_DIR/$STEM.md" "/tmp/backup_$STEM.md"
wc -w "$OUTPUT_DIR/$STEM.md"
```

##### Artifacts to Detect and Fix

- **LaTeX spaced** — `\ f r a c`, `\ s u m`, `\ m a t h r m` → `\frac`, `\sum`, `\mathrm`
- **Broken images** — `! [ ] ( ... )` with spaces between chars → `![](...)`
- **Split words** — "mod els", "alg orithm" — fix conservatively via dictionary check (`/usr/share/dict/words` or in-document vocabulary)
- **HTML entities** — `&amp;`, `&#39;` → unescape
- **Encoding artifacts** — UTF-8 mojibake (Ã©, Ã¤) → re-encode
- **Hyphenated line-end splits** — `comput-\ner` → `computer` (only when both halves are dictionary words)
- **Run-on duplicate headers** — Line N is garbage run-on, Line N+1 is correct → DELETE the garbage line

##### Per-Issue Script Pattern

For each issue type, create `/tmp/fix_<issue>_<STEM>.py`. Run, verify count reaches 0 for that issue, move to next. NOT one mega-script.

##### Validation (MANDATORY after each fix)

- Word count must be stable (+/- 1%)
- Check for run-on words (iscentral, tothe, ofthe) — must remain 0
- If word count drops >2% OR run-on words appear: ABORT, restore from backup, report

##### Stop Criteria — "Good Enough"

The pipeline downstream is: convert → clean (this phase) → embedding/index. Embedding handles small residual noise. Don't over-engineer.

Stop when:
- All known issue categories have 0 remaining matches in the file
- Word count is stable
- Spot-check 10-15 lines from the middle reads as natural text

---

### Phase 2 — Index (both modes)

Identical for both modes. Run as background job with `PYTHONUNBUFFERED=1` so the worker stays responsive (foreground would block on the long-running embed phase) and the log fills line-by-line for post-mortem if needed.

#### Skip-Logik (since 2026-05-08)

`workflow.py index-dir` is **skip-by-default**. Per file the SHA256 of the content is compared against the `indexed_files` tracking table:

- **skipped** — hash matches an existing entry → no work, no GPU touch
- **adopted** — file not in `indexed_files`, but a complete chunk set exists in `documents` (COUNT == MAX(total_chunks)) → register hash without re-embed (one-time bootstrap for collections that pre-date hash tracking)
- **indexed** — missing, partial, or hash-changed → chunk + embed + insert + register hash

Concretely: re-running `index-dir` on a directory where 14 of 168 files are new now indexes the 14, registers hashes for the 154 unchanged ones, and exits in seconds — not the previous full re-embed of all 168.

GPU servers are only started when there is real work to embed.

#### Pre-run: detect partial chunks from prior killed runs

A killed run can still leave partial chunks (e.g. abort happened mid-document insert). The skip-logic does NOT catch this case — partial documents are detected via the `total_chunks` mismatch, but the hash entry was never written for the killed file, so on re-run it lands in the **indexed** bucket and gets cleanly re-done. So the only scenario that needs manual intervention is a partial document whose hash was somehow already registered.

Check first:

```bash
rag-cli progress "$COLLECTION"
```

Any document showing `done < total` was interrupted mid-write. If you see one AND its hash is in `indexed_files`, delete the partial chunks so the re-run treats it as missing:

```bash
rag-cli delete --collection "$COLLECTION" --document "<doc>.md"
```

Don't pass `--remove-source` — the `.md` is fine, only the partial DB rows need to go. The next `index-dir` will treat the file as missing and re-index from scratch.

#### Run indexing

For multiple files (typical case — directory with N new + M existing):

```bash
cd ~/Documents/ai/Meta/ClaudeCode/MCP/RAG && \
PYTHONUNBUFFERED=1 ./venv/bin/python workflow.py index-dir \
    --input "$OUTPUT_DIR" --collection "$COLLECTION" \
    > /tmp/${COLLECTION}_index.log 2>&1 &
```

Skip-logic handles "only re-index new/changed files" automatically.

For an explicit single-file workflow (e.g. recovery of one specific document, or scripted per-file loops):

```bash
./venv/bin/python workflow.py index-file \
    --input "$OUTPUT_DIR/specific_paper.md" --collection "$COLLECTION"
```

`--force` is available on both subcommands and bypasses the skip — use only when the embedding model or chunker config changed and the entire collection genuinely needs re-embedding. Routine indexing should never need `--force`.

This handles: server health check → start if needed → classify (skip/adopt/index) → chunk + embed only the indexed bucket → summary.

#### Wait for indexing to finish — match timer duration to expected wallclock

**Lock awareness**: The indexer holds a global RAG lock for its full duration (written to `~/.rag-locks/rag.lock`). Any `rag-cli` command other than `status` will fail with "rag busy" while the lock is held. **Do NOT call `rag-cli progress` while the indexer is running** — it would hit a DB query blocked by indexer DDL/write locks and hang (this was the root cause of the zombie-process bug). Use `rag-cli status` instead to check mid-run progress — it reads the lockfile directly, no DB query.

Indexing takes 30–90 minutes for typical book-sized collections. The default polling pattern `sleep 60 && rag-cli progress` is the single most expensive anti-pattern in worker orchestration: each `Bash(run_in_background=true)` completion arriving while an API stream is open fires a new REQ, cancels the in-flight stream client-side, and gets billed input + cache-read. A 60-minute index with 60s polls = ~60 cascade events. **Never** set a short timer for a long-running job.

Two correct patterns, depending on whether anything follows the indexer:

**A) Indexing is the last work step before the completion checklist** — wait passively. ONE backgrounded bash fires ONE completion when the indexer is gone:

```bash
# Run as Bash(run_in_background=true)
( while pgrep -f 'workflow.py index-dir' > /dev/null 2>&1; do sleep 30; done; echo INDEXING_DONE ) &
wait
```

The `sleep 30` *inside* the loop is normal blocking sleep — it does NOT trigger CC tool-completion events. CC sees ONE backgrounded call, ONE completion at the very end. Zero cascade.

**B) More steps follow after the indexer (e.g. sample-query verification, cleanup pass on an output dir)** — set ONE timer that approximates the expected remaining wallclock. **The timer duration must match the work, not a default like 60–120s.** For a 29-minute remaining run, set the timer to ~25 minutes. ONE completion fires, then check `rag-cli status` (lock free = done; still held = still running + shows progress). If more time needed, set another sized-to-remaining timer. Never fire 14 short timers for a single long run.

If the user asks "how far?" at any moment, do ONE manual `rag-cli status` in foreground — shows document progress from the lockfile with no DB query. The anti-pattern is *automated repeated short polling*, not a single user-triggered status read.

After indexing completes (lock released, `rag-cli status` shows FREE), run the post-checks:

```bash
rag-cli progress "$COLLECTION"          # all docs must show done == total (safe: lock is free)
tail -30 /tmp/${COLLECTION}_index.log    # confirm "Done: N files indexed (X chunks), Y skipped, Z adopted"
```

**Output shape of `rag-cli progress`:**

```
Indexing Progress: <COLLECTION>

  Document                  Done / Total       %  Status
  doc_a.md                   579 / 579    100.0%  done
  doc_b.md                  1248 / 1390    89.8%  in-progress
  doc_c.md                     0 / 0        0.0%  ...   (not yet started — won't appear)
```

A document is currently being indexed when its row shows `done < total`. Documents not yet started don't appear in the table at all. Documents with `done == total` are committed.

#### Failure check (after indexing done)

```bash
tail -20 /tmp/${COLLECTION}_index.log
```

Confirm the summary line `Done: N files indexed (X chunks), Y skipped, Z adopted` — N+Y+Z must equal the total number of `.md` files found. Cross-check with `rag-cli progress` — every document should show `done == total` (call only after lock is free). NULL-embedding skips are logged at WARNING level in `src/rag/logs/indexer.log` (search for `NULL embedding skipped`); investigate via the indexer log before treating the collection as complete if any are present.

#### Verify

```bash
cd ~/Documents/ai/Meta/ClaudeCode/MCP/RAG && \
./venv/bin/python workflow.py search \
    --query "<topic from collection content>" \
    --top-k 3
```

Top result should be a chunk from the just-indexed collection.

---

### Completion Report

Output back to Opus when done:

```
CLEANUP-AND-INDEX REPORT
=========================
Mode:             [web-md | pdf]
Collection:       <COLLECTION>
Input:            <INPUT path> (N items)
Phase 0:          [crawl: M ok, K failed | convert: M ok, K failed]
Cleanup shapes:   [shape: file_count, ...]  (web-md only)
Cleanup issues:   [issue: count, ...]       (pdf only)
Char reduction:   X% total                  (web-md)
Word stability:   ±Y%                       (pdf)
Indexed:          N chunks across M documents
Verification:     query "<q>" → top result snippet (~50 chars)
Status:           [Success | Issues — describe]
```

End with this report. STOP. No commit needed (output is data files, not code).

---

### Anti-Patterns (both modes)

- One mega-script with N regex patterns instead of per-shape/per-issue small scripts
- Treating `strip%` (web-md) or `% removed` (pdf) as a quality metric — bytes-out vs bytes-in says nothing about indexability
- Hardcoded absolute paths in cleanup scripts
- Infinite loops — every `while` MUST increment in all paths
- Skipping the backup step (pdf mode) — restore is impossible without it
- Skipping spot-check after cleanup — strip% can lie, eyeballing 2-3 files catches over-strip
