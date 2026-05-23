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

### Steps

#### 1. Identify Source

Web domain (e.g. `docs.crawl4ai.com`) OR a list of PDFs (paths or URLs).

#### 2a. For Web Domains: Explore + Filter URLs

```bash
# Discovers URLs via sitemap → BFS cascade, writes list to /tmp/explore_<domain>_urls.txt, prints stdout summary
searxng-cli explore_site https://docs.example.com --strategy sitemap --output /tmp/example_urls.txt
```

Review the URL list with the user. Kill noise: login pages, archive indexes, search-result pages, irrelevant subpaths. Save the filtered list as `/tmp/<collection>_urls.txt`.

#### 2b. For PDFs: Decide Which to Convert

Review PDF candidates with the user. Skip paywalls, redundant copies, off-topic PDFs. Build a list of paths (or URLs to download first via `searxng-cli download_pdf`).

#### 3. Decide Collection Name

PascalCase, descriptive: `SearXNG_Docs`, `Crawl4AI_Reference`, `RAG_Survey_2024`. Becomes the RAG collection name.

#### 4. Spawn Worker

Write to `/tmp/spawn-<worker_name>.md`:

```markdown
# Worker Task: Cleanup-and-Index <COLLECTION_NAME>

You are a WORKER.

FIRST: activate the cleanup-and-index skill via Skill(skill="cleanup-and-index").

Then follow its protocol with these inputs:

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

#### 5. Wait for Worker, Verify

```bash
rag-cli search --query "<topic from indexed content>" --top-k 3
```
