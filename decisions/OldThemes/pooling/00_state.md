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

### Phase 7 — BM25 Sweep + Variants (executed 2026-05-09)

Five BM25-family probes run: parameter sweep (16+4 configs), 5-config side-by-side compare, IDF + engine-weighting variants, per-engine top-K cap. Best BM25 config 34/40 quality vs Hard-Slot 34/40 — no BM25 variant decisively beat the production baseline. `k1` had zero effect on short docs, `b` dominant axis with peak at 0.75, IDF didn't help on small-pool short-doc data, engine-inverse-weighting bipolar (helped Q2/Q3 by surfacing multi-engine consensus, over-rewarded sparse engines on Q4 — stack_exchange with 2 URLs got weight 0.5 → SO question floated to #1), per-engine top-K cap shrinks pool 5-7× without changing top-K quality (cap removes depth-tail noise but not engine-top-K noise like semscholar's PV-cell-defect false friend).

Detailed findings + eyeball quality table → `01_bm25_evaluation_findings.md`.

### Phase 8 — URL-Filter + BM25-Retrieve + Semantic Rerank (executed 2026-05-09)

Pivot to retrieve-then-rerank architecture. Pipeline: URL-pattern filter (search-results-pages like `?q=`, `/search/`) → BM25-Retrieve top-50 → semantic rerank → top-20. Two semantic methods compared: Qwen3-Embedding-0.6B bi-encoder (cosine similarity) vs Qwen3-Reranker-0.6B cross-encoder (joint pair scoring). Both are 0.6B-parameter Q8_0 GGUF on llama-server.

**Cross-Encoder is the first method in this investigation to outperform Hard-Slot.** Aggregate quality 35/40 (ties Hard-Slot) AND wins on Q1 with 9/10 vs Hard-Slot's 8/10 — semantic disambiguation eliminates the PV-cell/WSD/scholar-echo false-friends that BM25 cannot filter. Embedding-Cosine bi-encoder underperforms at 26/40 — architectural limitation of separate query/doc encoding on short snippets, not parameter count (8B bi-encoder ruled out earlier on latency). Latency cost: ~1.7s per query for 50 docs (rerank only); total per-query wallclock ~5s.

Detailed findings → `02_rerank_findings.md`. GitHub research note: SearXNG upstream's ranking formula is `score = num_engines × Σ(1/position_i)` — directly encodes multi-engine-overlap signal, similar to ranx CombMNZ. Independent confirmation that overlap signal matters, but our cross-encoder approach captures it via different mechanism (semantic match on jointly-encoded query+doc).

---

## Approaches Evaluated

| Approach | Method | Latency | Quality | Status |
|---|---|---|---|---|
| Hard-Slot 12/6/2 | class-bucket + slots | ~1 ms | 34-35/40 | current production baseline |
| RRF | Σ 1/(60+pos_i) over engines | ~1 ms | DOI-flood on Q1 | dropped Phase 3 |
| Embedding-Cosine (8B) | cos_sim, Qwen3-Embedding-8B | ~169 s | not quality-eval'd | DROPPED Phase 6 (latency) |
| Hybrid (Embedding+SPLADE+Rerank, 8B) | Dense+Sparse+Cross-Encoder | ~184 s | not eval'd | DROPPED Phase 6 (latency) |
| BM25 vanilla (k1=1.2, b=0.75) | TF + length-norm | ~50 ms | 32/40 | dropped Phase 7 |
| BM25 + per-pool IDF | BM25Okapi default | ~50 ms | 32/40 (IDF no effect) | dropped Phase 7 |
| BM25 + engine-inv-weighting | × Σ(1/engine_count) | ~50 ms | 34/40 (Q4 SE-overboost) | dropped Phase 7 |
| BM25-Capped | per-engine top-K cap | ~15 ms | 33-35/40 (Q1 weak) | reference, not winner |
| Filter+BM25-Retrieve+Embedding-Cosine (0.6B) | bi-encoder rerank | ~5 s total | 26/40 | DROPPED Phase 8 |
| **Filter+BM25-Retrieve+Cross-Encoder (0.6B)** | cross-encoder rerank | ~5 s total | **35/40, wins Q1** | **PRIMARY CANDIDATE pending validation** |

---

## Next Iteration (planned)

20-query validation probe before committing to production migration. Cross-Encoder's Q1 win is real but n=1 on the pathology category. Larger query set spanning academic / product / technical / mixed-intent (including multiple academic-noise cases) needed. Reranker domain-dependency warning from RAG eval (`/RAG/decisions/retrieval04_reranking.md`) applies — cross-encoders help on academic text but hurt on technical docs in full-document indexing; our snippet-rerank case differs but the warning stands.

If validation confirms: production migration design — modify `src/search/merge.py` to call the reranker via HTTP, register cross-encoder as managed service in RAG SERVERS dict (currently runs as one-off llama-server background process on port 8092 because port 8082 is occupied by Monitor_CC mitmdump session-proxy).

---

## Phase 9 (executed 2026-05-21, after bee-resolution)

20-query validation on capped pool — 4 ranking strategies (C1 Overlap-Count, C2 BM25, C3 Cross-Encoder direct, C4 Embedding-Cosine direct). Hard-Slot dropped from comparison per user direction.

Verdict: C2/C3/C4 all floor-tied at 0 obvious-Müll across 20 queries × ~210 URL slots. C1 produces 12 Müll (5.9% rate), all clustered in one discriminating query (Q6 espresso machine where "500" keyword-matches academic papers).

Detailed findings → `05_capped_pool_probe.md`. Initially suggested BM25 migration as cheapest equivalent; Phase 10 then revealed this conclusion was premature.

## Phase 10 (executed 2026-05-21)

Single-query deep-dive on Q14 "postgresql index types btree gin gist performance". Full pool dump (57 URLs) alongside each config's Top-10 picks via comparison matrix.

Critical findings:
- 0 URLs picked by all 4 configs (no consensus)
- 34 of 57 pool URLs picked by no config
- Among the 34: 8 high-quality expert sources (hakibenita, pganalyze, depesz, citusdata, 2ndquadrant, percona, thoughtbot, mydbops) — ALL missed by ALL 4 rankers
- Lobsters surfaced 4 of 8 experts; Google had 3 in deep-tail (positions 4-10); Mojeek 1
- Lobsters is structurally penalized: single-engine origin → engine_count=1 → C1 demotes; terse snippets → C2/C3/C4 demote on text content

Detailed findings → `06_q14_pool_dump.md`. Production migration BLOCKED — Müll-floor masked top-source-recall failure.

Next-session direction: solve top-URL identification automation first. Lobsters-boost as structural prior is the leading hypothesis (cheap, broadly applicable).

## Phase 11 (executed 2026-05-22)

LLM-as-Oracle value-eval — 4 modes (general/pdf/books/docs) × 4 queries (strict from canonical 20) × 4 C-methods (C1 Overlap, C2 BM25, C2' BM25-Capped, C3 Cross-Encoder). Worker (Sonnet) reads each pool independently, picks Top-10, scripted Jaccard computes overlap with each C-method.

**Architecture pivot before the eval:** all three y6e-bead-proposed directions rejected by user (authority-domain list / LLM-judge / Lobsters-boost) plus structural-feature mining as too query-specific. Final architecture: keep ranker simple (one C-method), add runtime LLM-driven engine-drill-down on the cached pool. Phase 11 picks the ranker; the drill-down tool follows after migration.

**Results:**

| Mode | C1 | C2 | C2' | C3 | Winner |
|---|---|---|---|---|---|
| general | 0.179 | 0.181 | 0.162 | **0.302** | C3 (+0.121) |
| docs | 0.195 | 0.400 | 0.446 | **0.458** | C3 (+0.012) |
| pdf | 0.871 (tie, undersized pools) |
| books | 1.000 (tie, undersized pools) |
| **Overall** | 0.498 | 0.558 | 0.565 | **0.609** | **C3 Cross-Encoder** |

C3 wins overall and in both reliable modes. PDF and books are noise (pool sizes ≤ 10 = trivial Jaccard).

**Caveats:** Google was out on all 16 pairs due to CAPTCHA + exponential-backoff cascade (3 backoff events, 466s wasted, google=0 throughout). 8-engine eval, not 9-engine. Method-comparison is internally fair (all 4 saw same pool) but Google's absence in general-mode means the +0.121 margin could shift in a 9-engine re-eval. Books mode broken for ML/DL queries (Open Library returns philosophy classics), docs mode has academic-engine precision noise — separate engine-coverage baustellen.

Detailed findings → `07_value_eval.md`. Migration recommended-but-still-BLOCKED on: (1) rate-limiter fail-fast refactor (`decisions/rate_limiting.md` + `decisions/OldThemes/no_backoff_retry.md`, new bead created for the work), (2) optional 9-engine re-eval, (3) cache format extension for per-engine position (prerequisite for drill-down tool), (4) cross-encoder SERVERS-dict registration in RAG infra.

---

## Approaches Evaluated (refreshed 2026-05-22)

| Approach | Method | Latency | Quality (overall Jaccard) | Status |
|---|---|---|---|---|
| Hard-Slot 12/6/2 (= C1 Overlap as ranker key) | class-bucket + slots | ~1 ms | 0.498 (worst in Phase 11) | current production baseline |
| RRF | Σ 1/(60+pos_i) over engines | ~1 ms | DOI-flood on Q1 | dropped Phase 3 |
| Embedding-Cosine (8B) | cos_sim Qwen3-Embedding-8B | ~169 s | not eval'd at scale | DROPPED Phase 6 (latency) |
| Hybrid (Emb+SPLADE+Rerank 8B) | Dense+Sparse+Cross | ~184 s | not eval'd | DROPPED Phase 6 (latency) |
| BM25 vanilla (C2) | k1=1.2, b=0.75 sw=on full pool | ~13 ms | 0.558 | candidate, not winner |
| BM25-Capped (C2') | per-engine top-K cap | ~1 ms | 0.565 | candidate, not winner |
| Embedding-Cosine (0.6B C4) | bi-encoder rerank | ~5 s | 26/40 Phase 8 | DROPPED Phase 8 (architectural) |
| **Cross-Encoder (C3) Qwen3-Reranker-0.6B** | Filter+BM25→Rerank or direct | ~2-5 s total | **0.609 (Phase 11 winner)** | **RECOMMENDED for migration pending blockers** |

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
