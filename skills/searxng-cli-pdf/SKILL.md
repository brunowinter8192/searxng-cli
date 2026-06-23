---
name: searxng-cli-pdf
description: Convert PDF(s) to Markdown and index into a RAG collection. No worker, fully interactive — the USER runs every mineru/docling convert command; Claude does naming, backend routing, merge, cleanup, index. Page-chunked (50 pages), continue-on-failure, docling fallback for the chunks MinerU missed.
---

# PDF → MD → Index — Skill

No worker. Interactive. The USER runs every mineru + docling command. Claude does ONLY: naming, backend routing, merge, clean, index. One PDF at a time.

## Paths
- MINERU = `~/Documents/ai/Mineru/venv/bin/python ~/Documents/ai/Mineru/workflow.py`
- DOCLING = `~/Documents/ai/Docling/venv/bin/python ~/Documents/ai/Docling/workflow.py`
- WORK = `~/Documents/ai/Mineru/output/<STEM>/` (holds `parts.json` + `part_NNN.md`)
- COLLECTION = `trading-reference` (default; confirm only if user names another)
- OUTPUT_DIR = `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<COLLECTION>/`
- COMMAND FILE = `~/Downloads/<batch>_pdf_commands.md`

## Rule
Every command that CONVERTS (mineru, docling) → USER runs, from the COMMAND FILE. Claude never runs a convert. Claude runs: `pdfinfo`/`pdfimages` (routing), `summary`, parts.json patch, `merge`, cleanup scripts, `rag-cli index`.

## Phase 0 — Naming + Routing (CLAUDE)
1. Per PDF: assign a PascalCase STEM, alphanumeric + underscore ONLY — no brackets, parentheses, dots, commas, spaces. Rename the source PDF in place → `<STEM>.pdf`.
2. Per PDF: pick backend.
   - `pdfinfo "<pdf>"` → `Pages: N`. Sample pages `P ∈ {N/6, N/3, N/2, 2N/3, 5N/6}` (min 1).
   - Per P: `pdfimages -list -f P -l P "<pdf>"` → a row whose width (col 4) > 1000 = wide image.
   - ALL sampled pages have a wide image → `hybrid-engine`. Else → `pipeline`.
3. Skip any PDF that already has `<OUTPUT_DIR>/<STEM>.md`.

## Phase 1 — MinerU convert (USER runs, one PDF at a time)
Write the COMMAND FILE. Per PDF, one block:
```
mkdir -p <OUTPUT_DIR>
PYTHONUNBUFFERED=1 ~/Documents/ai/Mineru/venv/bin/python ~/Documents/ai/Mineru/workflow.py convert \
  --pdf "<PDF>" --chunk-pages 50 -b <backend> -l en 2>&1 | tee /tmp/<STEM>_mineru.log
```
- Always `--chunk-pages 50`. Continue-on-failure (a failed chunk does not stop the run). Parts land in WORK.
- USER runs each block, reports done per PDF.

## Phase 2 — Failed chunks → docling (CLAUDE lists, USER runs)
1. CLAUDE: `MINERU summary --stem <STEM>` → list of failed chunk indices (md:null).
2. Per failed idx, append to COMMAND FILE (USER runs):
```
~/Documents/ai/Docling/venv/bin/python ~/Documents/ai/Docling/workflow.py convert \
  --pdf ~/Documents/ai/Mineru/output/<STEM>/parts/part_<idx>.pdf \
  --out-dir ~/Documents/ai/Mineru/output/<STEM> 2>&1 | tee /tmp/<STEM>_docling_p<idx>.log
```
- Writes `WORK/part_<idx>.md`. USER runs, reports done.

## Phase 3 — Merge (CLAUDE)
1. Patch `WORK/parts.json`: for every idx whose `part_<idx>.md` now exists on disk, set its `md` field = `part_<idx>.md`.
2. `MINERU merge --stem <STEM> --out-dir <OUTPUT_DIR>` → writes `<OUTPUT_DIR>/<STEM>.md`.
   - merge aborts if any part is still missing → report which (index + page range), decide with user (docling re-run / accept gap).

## Phase 4 — Clean (CLAUDE)
Run on the merged `<OUTPUT_DIR>/<STEM>.md`. Audit FIRST (counts are signals — sample the hits), then strip.

Per-class detection + action:
- **A — lost formula (UNRECOVERABLE → do NOT clean, flag for re-run):** `??`, `` (U+FFFD), empty/`?`-containing `<sub>`/`<sup>` (`<su[bp]>[[:space:]]*</su[bp]>|<su[bp]>[^<]*\?[^<]*</su[bp]>`), whitespace-only `$$…$$` blocks (split on `$$`, test odd segments). Any A hit → report symbol/page to user; only that chunk's source is gone.
- **B — spaced math (RECOVERABLE → de-space):** `_ {`, `^ {`, `\ [a-z]( [a-z])+`, spaced single-char runs `([A-Za-z] ){3,}[A-Za-z]`. Collapse runs to real tokens (`\mathrm { a r g m i n }` → `\mathrm{argmin}`). Invariant: alphanumeric-char count EXACTLY stable; word count drops.
- **C — encoding (RECOVERABLE → unescape):** HTML entities `&(amp|lt|gt|quot|apos|nbsp|#\d+|#x[0-9a-fA-F]+);`, mojibake `Ã.`/`â€`. Entity count → 0.
- **D — prose char-typos:** ignore (negligible). Pervasive prose garble = treat as A → re-run.
- **E — backmatter (MANDATORY STRIP):** from the first References/Bibliography/Index/Symbols/Abbreviations/Nomenclature heading in the last ~40% (or headingless reference run: most non-blank lines match `\(\d{4}[a-z]?\)`/`^Surname, Init.`; index run: `,\s*\d+([–-]\d+)?`) through EOF. Confirm 3 lines above the cut are real content. Do NOT cut numbered content subsections (heading text starts with a digit) or per-chapter "Bibliographic Notes".
- **F — table markup (RECOVERABLE → pipe-text):** MinerU `<table>` HTML, markup ratio > 50%. Strip tags, one row per `</tr>`, cells `|`-separated, content unchanged, no truncation. Validate cell-text token set unchanged.

Prose window (every md): pull 1–2 body lines (len > 70, starts alpha, > 10 spaces, alpha-ratio > 0.78) from the middle third and READ. Coherent → pass; garbled → A → re-run.

Per-issue scripts: one `/tmp/fix_<issue>_<STEM>.py` each, test on the file, re-scan that class to 0, spot-check 10–15 middle lines. Preserve source content; overwrite in place; back up to `/tmp/backup_<STEM>.md` first.

## Phase 5 — Index (CLAUDE)
```
rag-cli index --collection <COLLECTION>
```
Incremental (hash-skip). Report files indexed + chunks. Confirm docs in the collection.
