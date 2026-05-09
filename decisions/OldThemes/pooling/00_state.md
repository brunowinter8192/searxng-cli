# Pooling Feature — Investigation State

**Date:** 2026-05-09 (continuously updated)
**Bead:** searxng-g82 (open)
**Related beads:** searxng-bzh (--pdf widening), searxng-b1j (layer inventory), searxng-cuh (research questions)

---

## Scope

Replacement of the default search pipeline's result-merging step (`src/search/merge.py:_merge_and_rank`). Specifically:

- Hard-slot allocation `12 GENERAL / 6 ACADEMIC / 2 QA = 20 URLs` → replace
- Engine class bucketing (`GENERAL` / `ACADEMIC` / `QA` frozensets) → drop
- Within-class sorting heuristics (overlap-count for general; position+priority for academic/qa) → drop

Filter-flag overlay (`--books` / `--pdf` / `--docs`) stays as user-override engine set + post-merge URL filter. Out of scope for this rework.

---

## Problem Statement

The current `_merge_and_rank` reflects two ad-hoc design choices that were never empirically evaluated:

1. **Engine class assignments.** `Lobsters → QA`, `Open Library → GENERAL`, `Stack Exchange → QA` were chosen by intuition. Empirical data (Phase 3 below) shows Lobsters surfaces high-quality blog posts (jalammar.github.io, sebastianraschka.com) which the QA-class cap of 2 excludes for technical queries.
2. **Slot quotas (12/6/2).** No IR theory backs hard quotas — neither Cormack 2009 nor Croft 2010 endorse them. They were chosen because "proportional sounds reasonable".

Both fail under filter-flag mode (e.g. `--books` restricts to general engines, `ACADEMIC + QA` slots stay empty by construction → 8/20 dead slots).

---

## IST Production State (post 2026-05-09, bead f3i closed)

`src/search/`:
- `merge.py` — `_merge_and_rank` with class bucketing + hard slots (UNCHANGED, target of rework)
- `filter_modes.py` — `_DEFAULT_ENGINES` (9 engines, scholar excluded due to Google co-fire), `_BOOKS_ENGINES`, `_PDF_ENGINES`, `_DOCS_ENGINES`
- `search_web.py` — `_select_engines` returns `(selected, excluded)`, fan-out via `_query_engines_concurrent`, ranking via `_merge_and_rank`
- `query_logger.py` — `engines_excluded` field added with reason enum

10 engines registered in `ENGINES`, 9 in `_DEFAULT_ENGINES` (Scholar dormant per bead f3i).

---

## Investigation Phases

### Phase 1 — Source Selection (concluded)

**Question:** which engines fire on a query?

**Croft chapter 10.5:**

> "For a metasearch application... the resource representation and selection functions are trivial. Rather than selecting which search engines to use for a particular query, the query will instead be broadcast by the metasearch engine to all engines being used by the application." (chunk 747)
>
> "a distributed search that selected only 5-10 collections out of 200 was at least as effective as a centralized search... in a P2P testbed where the collection was distributed between 2,500 nodes and only 1% of these nodes were selected, the average precision at rank 10 was 25% lower" (chunk 752)
>
> "TREC experiments with metasearch have shown improvements of 5 - 20% in mean average precision... for combinations using four different search engines, compared to the results from the single best search engine (Montague & Aslam, 2002)." (chunk 752)

**Decision:** broadcast for N=10. Filter flags remain as user-override engine sets. No source-selection algorithm needed at our scale.

### Phase 2 — Result Fusion landscape (concluded)

**Question:** how to combine results from N engines?

**Cormack 2009 RRF (Chunks 1, 3, 6):**

> "RRFscore(d ∈ D) = Σ_{r ∈ R} 1 / (k + r(d)), where k = 60 was fixed during a pilot investigation and not altered during subsequent validation."
>
> "outperformed Condorcet all 7 times (p≈0.008), outperformed CombMNZ 6 of 7 times (p≈0.04), and outperformed the best individual result either 6 or 7 times"
>
> "Ranks may be computed and summed one system at a time, avoiding the necessity of keeping all rankings in memory."

**Cormack experimental conditions (matter for our case):**
- *Same-corpus, different-rankers* (TREC submissions over identical document collection, LETOR 3 over identical dataset)
- *Similar retrieval sizes* (~1000 docs each per system)
- *Implicit ranker independence* — different methods, different research groups
- These conditions match "data fusion" in Croft's taxonomy (chunk 751), not "collection fusion" or "arbitrarily overlapping databases" which is closer to our case

**Croft chapter 7 — single-collection retrieval ranking:**
- BM25 (chunks 423-428): probabilistic, k₁=1.2, b=0.75, "performed very well in TREC retrieval experiments"
- Query Likelihood (chunks 440-444): "similar effectiveness to BM25, does better on most TREC collections"
- Vector Space + TF-IDF (chunks 405-411): older, "provides little guidance on the details of how weighting and ranking algorithms are related to relevance"

### Phase 3 — Empirical RRF vs Hard-Slot A/B (2026-05-09)

**Probe:** `dev/search_pipeline/rrf_vs_hardslot_smoke.py` (commit `86b7b0a`)
**Report:** `dev/search_pipeline/01_reports/rrf_vs_hardslot_20260509_013940.md`

4 queries × 9 default engines, both methods applied to identical raw URL pool.

| Query | Type | Raw URLs | Overlap (top-20) | Verdict |
|---|---|---|---|---|
| transformer attention mechanism | academic-leaning | 492 | 7/20 | **strong divergence** |
| best espresso machine 2026 | general/product | 439 | 18/20 | near-identical |
| python asyncio context manager | qa-leaning | 405 | 17/20 | near-identical |
| kubernetes service mesh comparison | mixed | 454 | 16/20 | near-identical |

**Q1 — three structural issues exposed:**

1. *Lobsters classification wrong.* RRF surfaces `jalammar.github.io/illustrated-transformer` + `sebastianraschka.com/self-attention-from-scratch` at positions 3-4 (lobsters-only URLs, high-quality tech blogs). Hard-Slot excludes both — Lobsters is QA-class, capped at 2 slots, Stack Exchange wins those. Lobsters is structurally a tech-link-aggregator, not Q&A.
2. *Cross-API DOI flooding in RRF.* Positions 5-15 dominated by `doi.org/...` URLs that appear in BOTH crossref AND openalex. Each gets 2× RRF score because it has 2 engine entries. But crossref and openalex index the same publication metadata — they're not independent rankers. Cormack's independence assumption fails.
3. *Engine retrieval quality variance on broad queries.* crossref and openalex match "transformer attention" against papers about tugboat scheduling, biology, eye imaging (surface keyword matches). Both Hard-Slot and RRF inherit this noise. Hard-Slot caps it at 6 academic slots; RRF lets it dominate 11 slots.

**Q2-Q4:** methods agree on top URLs. 16-18 / 20 overlap. The 2-4 differences are noise-level.

### Phase 4 — Pivot to Retrieve-and-Rerank (2026-05-09)

**User reframe:** ignore engines, treat the 600-URL pool as candidates, pick top-20 by query relevance.

This is classical IR retrieval, not metasearch fusion. Croft chapter 7 is the relevant foundation (see Phase 2 quotes above). Modern state of the art (post-2010, not in DB but standard in production retrieval systems):
- Sentence-transformer embeddings + cosine similarity (dense retrieval, "1st-stage")
- Hybrid: dense + sparse signal with RRF fusion (state-of-the-art 1st-stage)
- Cross-encoder reranking on top-K (highest precision, "2nd-stage")

### Phase 5 — RAG Infrastructure Reuse

The project's RAG stack provides three GPU services (running, healthy as of 2026-05-09 02:00):

| Service | Port | Purpose |
|---|---|---|
| embedding | 49445 | dense vector encoder (sentence-transformer) |
| splade | 49302 | sparse vector with learned synonym expansion |
| reranker | 49425 | cross-encoder relevance scorer |

Services accept arbitrary text input — no pre-indexing required. Directly applicable to ephemeral 600-URL pool per query. Implementation surface: HTTP calls.

---

### Phase 6 — Embedding / Hybrid probe (2026-05-09, dropped)

**Probe:** `dev/search_pipeline/embed_hybrid_smoke.py` (worker `pooling-probe`, branch deleted with kill — code not preserved)

Planned 3-method probe: Hard-Slot baseline + Pure Embedding-Cosine + Hybrid (Dense + Sparse + Cross-Encoder Rerank), same 4 queries as Phase 3.

**Q1 only completed (transformer attention mechanism):**

| Method | embed_ms | splade_ms | rrf_ms | rerank_ms | total |
|---|---|---|---|---|---|
| A Hard-Slot | — | — | — | — | 1 ms |
| B Embedding-Cosine | 169 431 | — | — | — | ~169 s |
| C Hybrid | 169 431 (shared) | 12 554 | 6 | 2 376 | ~184 s |

Pool size: 481 raw → 447 unique URLs.

**Conclusion — dropped on latency.** 169 s/query is production-untauglich (target 5-10 s wallclock). Root cause: Qwen3-Embedding-8B is heavy (8B params), llama-server processes the batch sequentially.

**Deeper conclusion — embedding is structurally the wrong tool for our case.** Each engine has already done relevance ranking on the FULL document with its own retrieval model (Google's BERT, Mojeek's index, OpenAlex's bibliometric scoring). We get only title+snippet — a strict subset of what the engine saw. Re-encoding snippets duplicates work the engines did, with weaker input. The cases where embedding might help (synonym/paraphrase) — engines handle those on full text. No structural benefit, fatal latency cost.

Worker `pooling-probe` killed at user direction. Branch + worktree removed. GPU services (embedding/SPLADE/reranker on ports 49445/49302/49425) stopped.

### Phase 7 — Pool-Based Cheap Scoring (planned next)

User design intent: pool-as-flat-Documents (no engine groups, no class hierarchy), pick top-20 via cheap query-document scoring. With embedding ruled out, the remaining theory-aligned candidate is **BM25 over title+snippet** — Croft chapter 7, local CPU, ~ms latency, theory-backed (decades of TREC validation).

Trade-off vs embedding: weaker on synonym/paraphrase matching, but title+snippet is short text where embedding's lexical-vs-semantic gap is smaller. Latency: ~50 ms vs 169 000 ms.

---

## Approaches under evaluation

| Approach | Method | LOC | Latency | Status |
|---|---|---|---|---|
| Hard-Slot | class-bucket + 12/6/2 slots | 0 | ~1 ms | current production baseline |
| RRF | Σ 1/(60+pos_i) over engines | 30 | ~1 ms | tested Phase 3 — has DOI-flooding issue (cross-API correlation) |
| Embedding-Cosine | cos_sim(query, doc) | ~50 + GPU | ~169 s | DROPPED Phase 6 (latency + structural mismatch) |
| Hybrid (Embedding + SPLADE + Rerank) | Dense + Sparse + Cross-Encoder | ~150 + 3-4 GPU | ~184 s | DROPPED Phase 6 (latency + structural mismatch) |
| **BM25 over title+snippet** | local TF-IDF, Croft Kap. 7 | ~30 | ~50 ms | next probe — Phase 7 |

---

## Next Probe (planned)

`dev/search_pipeline/bm25_pool_smoke.py`
- Same 4 queries as `rrf_vs_hardslot_smoke.py` and the killed `embed_hybrid_smoke.py`
- BM25 ranking on the dedup'd flat pool (no class buckets, no engine groups, no engine-rank-fusion)
- Compare to Hard-Slot baseline (and reference Phase 3 RRF results for context)
- Measure: per-query latency, top-20 URLs, overlap with Hard-Slot

If BM25 produces top-20 lists comparable to or better than Hard-Slot at <100 ms latency, that's the production answer for `_merge_and_rank` rework.

---

## Sources

DB-state after cleanup 2026-05-09 (only sources actually extracted from):

| Source | Type | Status |
|---|---|---|
| Croft, Metzler, Strohman 2010 — Search Engines: Information Retrieval in Practice | Book | Indexed (RAG: searxng_reference, 868 chunks) |
| Cormack et al. SIGIR 2009 — Reciprocal Rank Fusion outperforms Condorcet | Paper | Indexed (RAG: searxng_reference, 7 chunks) |

Other initially-indexed pooling-research papers (Lillis 2006, Santos 2010, Baeza-Yates, Liu, Aslam-Montague, Renda, Wu, Akritidis, Ogilvie-Callan, Amin, MMMORRF, Trinity Thesis, Mourao Slides, Kafi WeightedRRF, UWaterloo TREC, Hu, Zhu, Zheng, He, Minack) were removed in the 2026-05-09 cleanup because they did not yield direct content extraction for the source-selection or result-fusion synthesis. See `sources/sources.md` for complete tracking.

---

## Related Beads

- **searxng-g82** (active) — this work, pooling rework
- **searxng-f3i** (closed 2026-05-09) — Scholar HTTP migration + Google decoupling, prerequisite for clean pooling design
- **searxng-bzh** — `--pdf` pool widening (admit landing pages); independent but related
- **searxng-b1j** — Layer-based improvement inventory (broader context)
- **searxng-cuh** — Research questions per priority lever (related research backlog)
