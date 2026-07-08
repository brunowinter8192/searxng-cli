# Pool Diff — v2 vs v3

**v2 ref:** `value_eval_v2_20260523_000156`
**v3 run:** `value_eval_v3_20260523_021216`

## Per-Pair URL Overlap (16 pairs)

| mode | query (slug) | v2_size | v3_size | overlap_pct | new_in_v3 | removed_from_v2 | v2_google | v3_google |
|------|-------------|---------|---------|-------------|-----------|-----------------|-----------|-----------|
| general | transformer_attention_mechanis | 76 | 73 | 73.3% | 10 | 13 | 11 | 0 |
| general | postgresql_index_types_btree_g | 48 | 48 | 100.0% | 0 | 0 | 0 | 0 |
| general | python_asyncio_event_loop_conc | 66 | 66 | 97.0% | 1 | 1 | 0 | 0 |
| general | contrastive_learning_self_supe | 55 | 67 | 82.1% | 12 | 0 | 0 | 11 |
| pdf | transformer_attention_mechanis | 74 | 82 | 85.7% | 10 | 2 | 0 | 10 |
| pdf | postgresql_index_types_btree_g | 49 | 55 | 89.1% | 6 | 0 | 0 | 10 |
| pdf | python_asyncio_event_loop_conc | 69 | 77 | 87.2% | 9 | 1 | 0 | 10 |
| pdf | contrastive_learning_self_supe | 55 | 66 | 80.6% | 12 | 1 | 0 | 11 |
| books | transformer_attention_mechanis | 62 | 86 | 70.1% | 25 | 1 | 0 | 11 |
| books | postgresql_index_types_btree_g | 41 | 55 | 71.4% | 15 | 1 | 0 | 10 |
| books | python_asyncio_event_loop_conc | 59 | 77 | 72.2% | 20 | 2 | 0 | 10 |
| books | contrastive_learning_self_supe | 45 | 67 | 64.7% | 23 | 1 | 0 | 11 |
| docs | transformer_attention_mechanis | 63 | 88 | 71.6% | 25 | 0 | 0 | 11 |
| docs | postgresql_index_types_btree_g | 40 | 57 | 67.2% | 18 | 1 | 0 | 10 |
| docs | python_asyncio_event_loop_conc | 69 | 76 | 88.3% | 8 | 1 | 0 | 10 |
| docs | contrastive_learning_self_supe | 55 | 67 | 79.4% | 13 | 1 | 0 | 11 |

## Aggregate Stats

- **Mean URL-overlap across 16 pairs:** 80.0%
- **Pairs with overlap > 80%:** 8 / 16
- **Pairs with overlap < 50%:** 0 / 16

## Per-Engine Reliability (v2 vs v3)

| Engine | v2 OK | v2 n | v2 OK% | v3 OK | v3 n | v3 OK% |
|--------|-------|------|--------|-------|------|--------|
| crossref | 16 | 16 | 100% | 16 | 16 | 100% |
| duckduckgo | 16 | 16 | 100% | 16 | 16 | 100% |
| google | 1 | 16 | 6% | 13 | 16 | 81% |
| lobsters | 16 | 16 | 100% | 16 | 16 | 100% |
| mojeek | 16 | 16 | 100% | 16 | 16 | 100% |
| open_library | 4 | 16 | 25% | 4 | 16 | 25% |
| openalex | 16 | 16 | 100% | 16 | 16 | 100% |
| semantic_scholar | 9 | 16 | 56% | 16 | 16 | 100% |
| stack_exchange | 8 | 16 | 50% | 8 | 16 | 50% |

## Highlighted Examples

**Best overlap:** `general × postgresql_index_types_btree_g` — 100.0% (48/48 URLs shared)
**Worst overlap:** `books × contrastive_learning_self_supe` — 64.7% (44/68 URLs shared)
**Most Google-recovered:** `general × contrastive_learning_self_supe` — v2 google_count=0 → v3 google_count=11 (+11)
