---
name: searxng-cli-capture-and-index
description: Discover URLs agentically (write /tmp scripts), select which to scrape, scrape raw/maximal, clean (incl. post-scrape noise drop), and index into RAG. Modes: web-md (Discovery→Select→Scrape→Cleanup→Index), pdf (Acquisition→Cleanup→Index).
---

# Capture-and-Index — Skill

---

### Mode 1: Web-MD Capture (discovery → select → scrape → clean → index)

Pipeline: Discovery → URL Selection (pre-scrape) → Scrape (raw) → Cleanup (incl. post-scrape drop) → Index.

**Scraper posture — best-effort, not guaranteed.** `src/crawler/pipe_scraper.py` is a GENERAL scraper; do NOT assume the scrape worked. Coverage verification is a first-class duty: every discovered URL that survives the cull must actually yield real content. On ANY systemic, diagnosable problem — a patterned coverage gap, a repeating block-type, a dominant error class (NOT scattered legit 404s) — STOP, do not push a half-broken capture into indexing, and report the IDENTIFIED problem to Opus: what fails, the evidence, your read of the cause. Iterate from there (different wait strategy, per-URL isolation, stealth, a per-site discover tweak — then re-run). The `>50%` / dozens-of-blocks thresholds below are hard floors, not the bar — a clearly-diagnosed problem warrants a STOP even under them.

#### Phase 0 — Discovery

Deliverable: `/tmp/<domain>_discovered_urls.txt` — one URL per line, maximum coverage of the target domain/section.

Write your discovery scripts to `/tmp` — no pinned reference script. Choose the path below based on structural signals from the seed page. **Any errors during discovery (HTTP failures, 429s, blocked fetches) MUST be recorded for the Completion Report.**

##### Step 0 — Structural Signals (always, ~30s)

Fetch the seed page HTML (plain HTTP, no browser). Check:

- `/sitemap.xml` and `/sitemaps/sitemap-0.xml` — does one exist?
- `<script id="__NEXT_DATA__">` in the raw HTML — signals Next.js SSR (see Path A).

`robots.txt` is NOT consulted.

##### Path A — `__NEXT_DATA__` Extraction (Next.js SSR sites, preferred)

Applicable when: `<script id="__NEXT_DATA__">` found in seed HTML.

No browser needed.

**Procedure:**

1. Parse the `__NEXT_DATA__` JSON blob from the seed page.
2. Walk any field containing `childPages`, `items`, or `navigation` keys paired with `href` or `url` strings — that is the nav tree. Key path is site-specific — discover by inspection (grep the blob for fields containing `childPages`/`href` pairs; do NOT assume `props.pageProps.mainContext.sidebarTree`).
3. Collect all URL strings matching the target section/domain from the primary nav (latest / free-pro-team / main version).
4. Check for an `allVersions`, `versions`, or equivalent version-list field in the blob. For EACH version:
   - Construct the version-scoped root URL.
   - Fetch it via plain HTTP.
   - Extract its nav tree (same walk logic).
   - Normalize version-prefixed URLs to canonical form (strip the version segment: `/de/enterprise-cloud@latest/rest/X` → `/de/rest/X`).
   - Union into the main set.
5. **Always check the OLDEST version** (same walk: construct its root URL, extract nav, union in).
6. Write the normalized union to `/tmp/<domain>_discovered_urls.txt`.

**Expected outcome:** 100% of pages appearing in ANY version's sidebar, in ~1–5s.

**Sitemap-coverage trap:** if the site also exposes a sitemap, verify it covers the target section (spot-check ≥5 known pages against the sitemap) before trusting it as an alternative.

##### Path B — Sitemap (non-Next.js, sitemap exists and is verified)

Applicable when: sitemap found AND spot-check confirms it covers the target section adequately.

Fetch and parse the sitemap; filter to target section URLs; write to `/tmp/<domain>_discovered_urls.txt`.

##### Path C — Playwright BFS (fallback — no `__NEXT_DATA__`, no usable sitemap)

Applicable when: neither Path A nor Path B applies.

Write a /tmp BFS script using `crawler.arun()` per frontier URL; extract `result.links.internal` from the fully rendered DOM. Config:

```python
wait_until = "domcontentloaded"
delay_before_return_html = 3.0   # the one genuine time↔completeness dial
page_timeout = 15000             # load ceiling; does NOT add to delay
concurrency = 1                  # WAF-safe default
```

429 policy: back off 5s once; stop if second consecutive batch also 429 — report `stop_reason="429_persistent"`. No retry loops.

`stop_reason="frontier_exhausted"` means all link-reachable pages were found.

Write discovered URLs to `/tmp/<domain>_discovered_urls.txt`.

#### Phase 1 — URL Selection (pre-scrape)

The cull happens on the URL LIST, before any scraping — not by reading scraped `.md` files. Inspect `/tmp/<domain>_discovered_urls.txt`, decide which URLs are obvious noise (e.g. changelog/archive/legal/asset paths, known-dead sections), and write a `/tmp` script that rewrites the list so only the URLs worth scraping remain.

Record which patterns were dropped and why — this goes into the Completion Report (`URLs dropped (pre-scrape, pattern): K — patterns + why`).

Do NOT read page content here; that is impossible pre-scrape. This step is purely list-level pattern selection.

#### Phase 1b — Opus Cull Review (MANDATORY STOP)

After the pattern-noise cull, the list still contains pages that are valid content but may be **irrelevant to what the user actually needs**. Do NOT edit the list for relevance; present it, and **Opus edits the `/tmp` file directly**.

STOP here. Report to Opus:
- the URL-list path (`/tmp/<domain>_discovered_urls.txt`) and total count
- a **per-section breakdown**: group URLs by their first path segment under the target root, with counts — e.g. `rest/actions: 41 · rest/repos: 28 · rest/enterprise-admin: 35 · …`

Then WAIT. Opus strips the unwanted URLs from `/tmp/<domain>_discovered_urls.txt` itself. When Opus says go, re-read the now-shorter file and proceed to Phase 2 — do NOT modify the list yourself.

Do NOT scrape before Opus says go.

#### Phase 2 — Scrape

Scrape every URL in the filtered list **raw and maximal** — no content filter, no truncation.

```bash
mkdir -p $OUTPUT_DIR
```

Launch the pipe-scraper as a **background Bash call** (`run_in_background=true`), then go idle. Invoke via the absolute source path:

```bash
SEARXNG=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/searxng-cli
cd "$SEARXNG" && ./venv/bin/python -m src.crawler.pipe_scraper \
    --url-file /tmp/<domain>_discovered_urls.txt \
    --output-dir $OUTPUT_DIR > /tmp/<domain>_scrape.log 2>&1
```

> You own Scrape → Cleanup → Index end-to-end — never hand back to Opus mid-pipeline. After launch, go idle; do NOT `pgrep`/name-poll/`wait`-loop. When the run completes, read `/tmp/<domain>_scrape.log` ONCE for the `Scraped N/N ok` summary, then continue on your own to Cleanup → Index → final report.

The scraper's own output is short: a console line with **success count, error count, and total duration**, plus a full per-URL report written to `/tmp/<domain>_scrape_report.md` (per-URL status + outcome). It does NOT dump a per-URL list to the console — failures live in the report md.

Take from that console line for the Completion Report: scraped N, errors K, **duration T**. The error breakdown (429 / timeout / http_error) is already itemized in the scrape report md.

**Coverage gate — verify, don't assume.** Compare the scrape outcome against the cull-survived URL list — every URL should have yielded a usable body. `>50%` failed → STOP, report to Opus, do not proceed. STOP below that threshold too when the shortfall is SYSTEMIC and diagnosable: one block-type or error class hitting a coherent slice of URLs (e.g. all article pages regwalled while index pages pass). Report the identified problem to Opus — what failed, the evidence (block text / coverage delta / error breakdown), the suspected cause — and iterate; do NOT carry a patterned gap into Cleanup/Index. Scattered legit 404s / thin pages are NOT a stop — those flow to the post-scrape drop.

#### Phase 3 — Cleanup

Diagnose first. Don't write cleanup regex before classifying shape.

##### Diagnose Pass

Build a small script that scans ALL `.md` files in OUTPUT_DIR, extracts per-file fingerprints (h1 count, h2 count, prose density, table presence, source domain from `<!-- source: URL -->` comment, total LOC). Cluster by fingerprint similarity to identify 4-5 shape groups. ~50 LOC, ~5s runtime.

**Fold in — Block Detection (cookie / paywall / JS-wall / captcha).** In the same diagnose pass, ALSO match each file against a BROAD, high-recall block-signature list (case-insensitive substring set, extend freely):

```
cookie/consent : "accept cookies", "we use cookies", "cookie policy", "consent", "gdpr", "manage preferences"
paywall/sub    : "subscribe to", "sign in to continue", "members only", "create a free account", "register to read"
js/bot wall    : "enable javascript", "javascript is required", "verify you are human", "captcha", "checking your browser", "access denied"
```

A file is a CANDIDATE when it matches a signature AND is small (byte-size in the thin-page range). For every candidate, the diagnose script PRINTS its `<!-- source -->` URL + first ~15 lines into its own output — confirm real-block vs false-positive from that output. If the candidate set is large (dozens+) → STOP and report to Opus.

A confirmed block page is garbage → **DELETE it** (same as a thin page) — no content-stripping. REPORT the confirmed-block count + example URLs in the Completion Report.

##### Post-Scrape Drop — thin successful pages (part of the diagnose pass)

Scrape gaps (429 / timeout / http_error) are already reported by the scraper. The only thing to analyse here are the **successful but very small** `.md` files (HTTP 200, tiny byte size): pages that scraped fine but carry little or no real content (stub, redirect landing, pure nav).

Delete those. Record the count for the Completion Report. Re-read only the small successful files, not every page.

The two numbers stay separate in the report: scrape errors come from the scraper, thin/noise comes from this check.

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
   - Keep story title row + comment threads. Markdown-table syntax stays.

4. **Repo-Heavy-Chrome-Shape** — very long pre-content chrome (>100 lines), many h1 chrome lines (search box, feedback, sponsor, repo headers), real title appears late.
   - GitHub issue/PR: extract `#<N>` from URL, find `^# .+ #<N>` line, strip everything before.
   - GitHub repo home: anchor on README's first h1 or file-tree end-marker.

5. **Index-Aggregator-Shape** — page is mostly link list, no real prose. Wikipedia category pages, blog index pages, doc TOC pages.
   - Flag as low-content. Optionally exclude from indexing (skip the file).

##### Web-Specific: Sphinx Documentation

Sphinx-generated docs (SearXNG, ReadTheDocs, many Python project docs) have a distinctive pattern.

Header (top of file, before first `# ` heading):
- `### Navigation` block with index/modules/next/previous links
- Breadcrumb trail with `»` separators
- Strip: everything between `<!-- source:` line and first `# ` heading

Footer (after last content line):
- Logo image line: `[ ![Logo of ...](...) ](...)` — content-end marker
- `### [Table of Contents]`, `### Project Links`, second `### Navigation`, `### Quick search`, `### This Page`, `© Copyright`
- Strip: everything from `^\[ !\[Logo of ` to EOF

Inline noise (`_modules_*` files only): `[docs][](URL)` markers before class/function defs. Regex: `\[docs\]\[]\(https://[^)]*\)`.

##### Per-Shape Cleaner Pattern

For each detected shape, write ONE small script in `/tmp/clean_<shape>_<COLLECTION_lower>.py` (~20-30 LOC each). NOT one big function with N patterns.

##### Script Safety Rules (CRITICAL)

- Every `while` loop MUST increment in ALL code paths (skip/continue/break/normal — all)
- Test on 1 file FIRST, then run on all
- ALWAYS `python3` (not `python`)
- Use `Path(__file__).parent` — NEVER hardcode absolute paths like `/Users/...`
- Preserve `<!-- source: URL -->` comments in every file
- Overwrite originals in-place
- After cleaning, spot-check 2-3 files

##### Edge Cases

- Files with no `# ` heading (auto-generated redirect pages) → keep content between source comment and logo line
- Files nearly empty after cleanup (<5 lines) → still output, don't delete
- `user_None.md` / `user_{}.md` files = crawled error pages, minimal content expected

---

### Mode 2: PDF Capture (download → convert → clean → index)

Input: absolute path to a single PDF file OR a directory of `*.pdf` files.

Pipeline: Acquisition → Cleanup → Index.

#### Phase 0 — Acquisition

**Naming — PDFs carry speaking names, the md inherits them.** A source PDF must have a speaking
PascalCase name BEFORE conversion (e.g. `NadeauBengio2003InferenceGeneralizationError.pdf`). If a PDF
has a cryptic name (`6280358.pdf`, `2104.03667v1.pdf`, a libgen / Anna's-Archive string), RENAME it in
place first — derive the name from the first page / title metadata, sanitize per the char rules below.
The markdown then simply inherits the PDF's basename: `STEM = basename(PDF without .pdf)`, output =
`$OUTPUT_DIR/$STEM.md`. PDF name and md name stay identical.

##### Category Check — handled by the driver

The driver categorizes each PDF via `pdfinfo`/`pdfimages` internally — born-digital → MinerU `pipeline` backend; scan → `--scan-backend` (default: `vlm`). No manual pre-check required.

##### Convert — one hybrid-driver call over all PDFs

Set `OUTPUT_DIR` to the collection directory **before** the driver call:

```bash
RAG_ROOT=~/Documents/ai/Meta/ClaudeCode/cli/rag-cli
OUTPUT_DIR="$RAG_ROOT/data/documents/$COLLECTION"
mkdir -p "$OUTPUT_DIR"
```

Launch as a **background Bash call** (`run_in_background=true`) and go idle:

```bash
/Users/brunowinter2000/Documents/ai/Docling/venv/bin/python \
    /Users/brunowinter2000/Documents/ai/Docling/hybrid_driver.py convert \
    --pdf <pdf1> [<pdf2> ...] \
    --out-dir "$OUTPUT_DIR" \
    > /tmp/hybrid_engine_map.json
```

The driver runs sequentially (MinerU and docling never overlap — Req 3):
- Categorizes all PDFs; processes born-digital first (Req 2).
- **Pass 1 — MinerU:** formula-weight chunked, continue-on-failure. Born-digital → `pipeline`; scan → `vlm` (override: `--scan-backend hybrid-engine`).
- **Pass 2 — docling:** fallback for failed MinerU chunks; full-PDF fallback if MinerU fails catastrophically. Only after Pass 1 fully complete.
- **Merge:** assembles each PDF's chunks into `$OUTPUT_DIR/<stem>.md`.
- **Engine map:** JSON printed to stdout (captured to `/tmp/hybrid_engine_map.json`).

Note on naming a cryptic PDF: derive a descriptive PascalCase name from the first page header / title metadata, condensed to ~30 chars (e.g. `AslamMontague2001MetasearchModels`, `ManningRaghavanSchutze2008IRTextbook`), and RENAME the PDF before the driver call. The md inherits the PDF stem. Avoid filename collisions inside one batch — append year or first-author-initial when needed.

**STEM character constraints (hard rules):** alphanumeric + underscore ONLY. NEVER include brackets `[ ]`, parentheses `( )`, dots `.` (other than the trailing `.md` extension), commas, spaces, or any glob metachar. Sanitize at derivation time.

##### Engine-Map Report — MANDATORY before Phase 1 (Req 1)

After the driver completes, read and report the engine map **before** proceeding to Cleanup:

```bash
cat /tmp/hybrid_engine_map.json
```

Report to Opus:
- Which engine (MinerU / docling) handled each chunk and page range for every PDF.
- Any PDF with `"engine": "docling-full-fallback"` — MinerU failed entirely for that document; docling converted the whole PDF.
- **Any chunk with `"status": "null"` — both engines failed; that page range is missing from the md.**

**If any `"status": "null"` chunk exists: STOP. Report PDF name + page range to Opus. Do not proceed to Cleanup or Index until Opus decides (accept the gap / retry / other).**

#### Phase 1 — Cleanup

PDFs are produced as Markdown by the hybrid driver (MinerU for most chunks, docling for fallback chunks). Phase 1 opens with a per-md fidelity check that both catches bad converts AND detects the cleanable artifacts. Cleanup itself focuses on inline OCR artifacts, not block chrome. Skip any md where all chunks have `"status": "null"` in the engine map (both engines failed — already reported to Opus before this phase).

##### Audit — systematic fidelity scan (EVERY md, BEFORE cleaning)

Run on EVERY produced md, not a sample. NEVER full-read a book md. Build one `/tmp` scan script that
tabulates the five classes below per file (count) — then SAMPLE the hit lines with offset-reads. A
count is a signal, not a verdict: read the actual hits to classify. **Word count is NOT a fidelity
signal** — a fully garbled scan sits at a normal words-per-page (a 366p scan OCR'd to garbage measured
530 w/p). The class counts and the samples decide, never the word count.

**Class A — Lost formula content (UNRECOVERABLE → reconvert, do NOT clean):**
- `??` — failed-OCR symbol(s): `grep -c '??' "$MD"`. Example of the damage: `compute the vector
  <sup>??</sup>` — a vector symbol gone.
- `` (U+FFFD) replacement char.
- garbled `<sub>`/`<sup>` — empty or `?`-containing:
  `grep -coE '<su[bp]>[[:space:]]*</su[bp]>|<su[bp]>[^<]*\?[^<]*</su[bp]>' "$MD"`.
  (Plain `<sup>1,*</sup>` author/footnote markers are legitimate — not this.)
- genuinely empty display math — detect by SPLITTING on `$$` and testing odd segments for
  whitespace-only (single-quote the `-c` so bash leaves `$$` alone):
  `python3 -c 'import sys;p=open(sys.argv[1]).read().split("$$");print(sum(1 for i in range(1,len(p),2) if not p[i].strip()))' "$MD"`.
  Do NOT use a `$$\s*$$` regex — it false-matches the blank gap between two consecutive formula blocks
  and reports phantom empties.
- Any Class-A hit = source content is gone, no regex recovers it. Flag the file and report to Opus — re-run `hybrid_driver.py convert` on that PDF to retry. List which symbol/formula is lost.

**Class B — Spaced math (RECOVERABLE → de-space):**
- spaced sub-/superscripts: `_ {` , `^ {`
- spaced single-char runs: `([A-Za-z] ){3,}[A-Za-z]` — WARNING: this ALSO matches legitimate math
  single-letters in running prose ("a K class outcome", "K-medoids is far more"). A high count flags a
  file for de-spacing; the small residual AFTER de-spacing is mostly these false positives. Sample
  before calling a residual a defect.
- spaced command names: `\ [a-z]( [a-z])+`
- Discriminator: collapsing a run yields a real token (`\mathrm { a r g m i n }` → `\mathrm{argmin}`).

**Class C — Encoding (RECOVERABLE → unescape / re-encode):**
- HTML entities: `&(amp|lt|gt|quot|apos|nbsp|#[0-9]+|#x[0-9a-fA-F]+);`
- UTF-8 mojibake: `Ã.` , `â€`

**Class D — Prose char-typos (low-impact, not auto-fixable):**
- single-char OCR errors ("diferent", "emai1", "BIUE"). No reliable grep — needs a dictionary pass.
  Negligible for retrieval; do not chase. If a file is PERVASIVELY garbled in prose it is Class A → reconvert.

**Class E — Backmatter (MANDATORY STRIP — every md except web-scraped API docs):**

WHAT goes out — from the first backmatter heading (or, when headingless, the first backmatter entry) through EOF:
- **References / Bibliography** sections.
- **Symbols and Abbreviations / Nomenclature / Notation** glossaries.
- **Index / Author Index / Subject Index / Stichwortverzeichnis** (term + page-number lists).

HOW to find the cut line:
1. Heading scan — markdown heading lines (`^#{1,6}\s`) whose text matches
   `references|bibliography|index|symbols|abbreviations|nomenclature`, in the last ~40% of the file.
2. Headingless backmatter (no heading on the reference list / index) — detect by line-pattern density in 100-line buckets:
   - reference run = most non-blank lines match `\(\d{4}[a-z]?\)` (year in parens) or `^Surname, Init.`,
   - index run = most non-blank lines match `,\s*\d+([–-]\d+)?` (term + page number).
   Cut line = first line of the first sustained reference/index run after the last real-content section.

HOW to cut:
- Read 3 lines above the cut line (must be real content) + the heading/first-entry line to confirm the boundary.
- Back up the file; truncate from the cut line through EOF; rstrip trailing blanks.
- Re-scan: no backmatter heading in the last ~40%, and the new last line is real content.

Do NOT cut these (they are CONTENT, NOT backmatter):
- **Numbered content subsections** with a keyword in the title (`6.3.4 Discussion and further references`,
  `3.2.3. Rand index`, `2.11 Discussion and bibliography`) — filter any heading whose text starts with a digit.
- **Per-chapter "Bibliographic Notes"** (prose, not a list).
- **Exercises with inline citations** above the reference list (`(Author, year)` + `$$` formulas). The reference LIST
  starts where entries are alphabetical `Surname, Init. (year). Title…` with no `$$`/`Ex.`/`(a)`. Anchor there.

Owner-decision sections (default: strip as backmatter; ask the corpus owner before keeping):
- Mid-document per-part **Nomenclature / Notation** boxes (symbol glossaries) — these can sit anywhere, not only at EOF.
- Front matter **List of Tables / List of Figures**.
- Resource / software **appendices** (web-site lists, software guides).
- Inline image refs `![](images/...)`.
These are not always at EOF — scan the WHOLE file for them, strip each section from its heading to the next real-content heading.

**Class F — Table markup noise (RECOVERABLE → strip to pipe-text):**
MinerU emits tables as HTML `<table>` blocks; table-dense / OCR'd PDFs carry ~65–80% pure markup
(`<td>`/`<tr>`/`rowspan`/`colspan`) around the data. ONE treatment for ALL tables, regardless of PDF
category: strip the HTML to flat pipe-text, cells AS-IS — do NOT fix structure.

- Detect (per `<table>`): markup ratio = chars-in-`<…>` / total table chars, flag at >50% (typical 65–80%);
  `rowspan`/`colspan` count; secondary signal = merged-value cells (several whitespace-separated values in
  one `<td>`: `KLIEP KLR KMM OSVM`, `0.919 0.934`).
- Fix (ad-hoc script, same pattern as Class B/C): per `<table>`, drop every tag + attribute, one row per
  `</tr>`, cells `|`-separated, content unchanged, full table (no `…` truncation). Header separator after row 0.
- Validate: cell-text token set unchanged (only tags removed); table-char count drops by the markup fraction.
  Spot-check 1–2 tables render as readable pipe rows.
- Limit: strips NOISE, not CONTENT errors. OCR-corrupted cells stay as-is — no strip recovers source content.
  Source re-extraction (camelot/gmft/pdfplumber, see `dev/table_extraction`) was tested and judged not worth
  the matching/splice complexity for the marginal gain. Leave such tables de-noised; an LLM consumer can read
  a flat pipe table even with imperfect structure.

**Prose window — one real prose paragraph per md (MANDATORY, every convert):**
The class greps catch detectable defects only; wordlike garble passes every one of them — a region OCR'd
to plausible-but-wrong words ("Ed Formet Yiew Compuurtonel" from a screenshot, "to replaced the data
samples"). So for EVERY convert, also pull a genuine body prose line and READ it. Extract candidates
programmatically — a body line with length > 70, starting alphabetic, > 10 spaces, and alpha-ratio
> 0.78 (this skips formula/table/header lines) — and read 1–2 from the middle third of the file:

```python
import glob, os
from pathlib import Path
for f in sorted(glob.glob(f"{OUTPUT_DIR}/*.md")):
    lines = Path(f).read_text(errors="replace").splitlines()
    n = len(lines); hits = []
    for s in (l.strip() for l in lines[n//3:2*n//3]):
        if len(s) > 70 and s[:1].isalpha() and s.count(" ") > 10 \
           and sum(c.isalpha() or c.isspace() for c in s)/len(s) > 0.78:
            hits.append(s)
        if len(hits) >= 2: break
    print(os.path.basename(f), "->", (hits[0][:140] if hits else "NO PROSE WINDOW (formula/table-heavy — inspect manually)"))
```

Coherent academic prose → pass. Garbled prose → escalate; pervasive prose garble = Class A → reconvert.
A file that yields no prose window is formula/table-heavy — inspect it by hand.

**Verdict per file:**
- Class A > 0 → reconvert (hybrid). Do NOT clean a lossy file.
- Class B / C only → clean (de-space, unescape), then re-scan that class to 0.
- Class D → policy decision, not a blocker.
- Class E (backmatter) → MANDATORY strip (see Class E above) for every md except web-scraped API docs.
- Class F (table markup) → strip to pipe-text (ad-hoc script), all PDFs.

**Limit of this audit:** it catches DETECTABLE losses (`??`, ``, broken markup). A formula that OCR'd
to valid-but-wrong LaTeX looks clean and is only catchable against the source PDF — no grep finds it.
A zero Class-A count means "no detectable loss", not "guaranteed perfect".

##### Pre-cleanup: Backup + Baseline

```bash
cp "$OUTPUT_DIR/$STEM.md" "/tmp/backup_$STEM.md"
# de-spacing invariant baseline: alphanumeric-char count (NOT word count)
python3 -c "import sys;print(sum(c.isalnum() for c in open(sys.argv[1]).read()))" "$OUTPUT_DIR/$STEM.md"
```

##### Artifacts to Detect and Fix

- **LaTeX spaced command name** — `\ f r a c`, `\ s u m`, `\ m a t h r m` → `\frac`, `\sum`, `\mathrm`
- **LaTeX spaced command contents** — `\mathrm { t h e \ d e s i g n }` → `\mathrm{the design}`; `\operatorname* { m i n }` → `\operatorname*{min}`
- **Broken images** — `! [ ] ( ... )` with spaces between chars → `![](...)`
- **Split words** — "mod els", "alg orithm" — fix conservatively via dictionary check (`/usr/share/dict/words` or in-document vocabulary)
- **HTML entities** — `&amp;`, `&#39;` → unescape
- **Encoding artifacts** — UTF-8 mojibake (Ã©, Ã¤) → re-encode
- **Hyphenated line-end splits** — `comput-\ner` → `computer` (only when both halves are dictionary words)
- **Run-on duplicate headers** — Line N is garbage run-on, Line N+1 is correct → DELETE the garbage line

##### Per-Issue Script Pattern

For each issue type, create `/tmp/fix_<issue>_<STEM>.py`. Run, verify count reaches 0 for that issue, move to next. NOT one mega-script.

##### Validation (MANDATORY after each fix)

- **De-spacing:** alphanumeric-character count must be EXACTLY stable (de-spacing removes only spaces).
  The word count DROPS — that is intended; NEVER validate de-spacing on word count.
- **Entity unescape:** entity count must reach 0; each entity collapses to exactly one char.
- Re-scan the fixed class → must reach 0 (minus the Class-B spaced-run false positives in prose).
- Spot-check 10-15 prose lines from the middle — natural text, no merged run-ons ("cambridgeuniversitypress").
- On any anomaly (alnum changed, run-ons appear, class not cleared): ABORT, restore from backup, report.

##### Stop Criteria — "Good Enough"

Don't over-engineer. Stop when:
- All known issue categories have 0 remaining matches in the file
- Word count is stable
- Spot-check 10-15 lines from the middle reads as natural text

---

### Index — Final Phase (both modes)

One script call. `rag-cli index` is incremental (hash-based skip) — re-running only embeds new/changed files.

**Important — OUTPUT_DIR must be the collection dir.** Set `OUTPUT_DIR` to the rag-cli collection directory:

```bash
RAG_ROOT=~/Documents/ai/Meta/ClaudeCode/cli/rag-cli
OUTPUT_DIR="$RAG_ROOT/data/documents/$COLLECTION"
mkdir -p "$OUTPUT_DIR"
```

Set this BEFORE the Scrape phase (Phase 2).

Then launch index as a background Bash call:

```bash
PYTHONUNBUFFERED=1 rag-cli index --collection "$COLLECTION" \
    > /tmp/${COLLECTION}_index.log 2>&1
```

The script prints per file `Indexed <doc> -> N chunks` and a final summary line:

```
Done: N files indexed (X chunks), Y skipped, Z adopted
```

Report `N` (files indexed) and `X` (chunks) from that line — `N` is the **final md** count for the Completion Report.

Launch index as a background Bash call (`run_in_background=true`) and go idle; do NOT `pgrep`/name-poll/`wait`-loop. When it completes, read `/tmp/${COLLECTION}_index.log` ONCE for the summary line, then output the Completion Report.

No separate verify step inside the pipe.

---

### Completion Report

Output back to Opus when done.

**web-md — the funnel:**

```
URLs discovered:                    N
URLs dropped (pre-scrape, pattern): K    — which patterns + why
URLs scraped:                       N − K
Scrape:                             M ok, E errors   ·   duration: T   (errors itemized in /tmp scrape report md)
md dropped (post-scrape, thin):     D
blocks detected (cookie/paywall):   B    — confirmed real-block MDs + example URLs (NOT auto-stripped)
Final md indexed:                   M − D
Collection:                         <COLLECTION>
```

Keep the two drop reasons separate: scrape errors **E** come from the scraper, thin/noise **D** comes from the cleanup check.

**pdf:** `engine-map: M PDFs (N chunks MinerU, K chunks docling-fallback, J status:null — reported to Opus before cleanup)` · `bad converts excluded (reported, need reconvert): B` · `cleaned: C files` · `indexed: N chunks across M documents`.

End with this report. STOP. No commit needed (output is data files, not code).