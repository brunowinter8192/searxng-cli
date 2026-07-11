# Engine Distribution Analysis — 20260505_233412

Source: `pipeline_smoke_20260505_233355.md`  
URL records parsed: 579  
Queries: 30

## 1. Per-Engine Slot-Count Total

Each URL record contributes +1 to every engine listed in its `Engines:` field.  
Solo = engine is the only known contributor for that URL.  
Overlap = URL has ≥2 known engine contributors.

| Engine | Class | Total | GENERAL | ACADEMIC | QA | Solo | Overlap |
|--------|-------|------:|--------:|---------:|---:|-----:|--------:|
| google | GENERAL | 164 | 164 | 0 | 0 | 89 | 75 |
| duckduckgo | GENERAL | 159 | 159 | 0 | 0 | 81 | 78 |
| mojeek | GENERAL | 138 | 138 | 0 | 0 | 98 | 40 |
| google_scholar | ACADEMIC | 63 | 4 | 59 | 0 | 59 | 4 |
| openalex | ACADEMIC | 53 | 0 | 53 | 0 | 50 | 3 |
| crossref | ACADEMIC | 71 | 0 | 71 | 0 | 68 | 3 |
| stack_exchange | QA | 17 | 2 | 0 | 15 | 15 | 2 |
| lobsters | QA | 26 | 2 | 0 | 24 | 24 | 2 |

Column sums — GENERAL: **469** (URL count 360 = 12 × 30 queries; sum ≥ URL count due to multi-engine overlaps)  
ACADEMIC: **183** (URL count 180)  
QA: **39** (URL count 39)

## 2. Per-Engine Status Aggregate

Quoted through from `pipeline_smoke_20260505_233355.md` — no recomputation.

| Engine | OK | EMPTY | TIMEOUT | ERROR |
|--------|---:|------:|--------:|------:|
| google | 30 | 0 | 0 | 0 |
| duckduckgo | 30 | 0 | 0 | 0 |
| mojeek | 30 | 0 | 0 | 0 |
| google_scholar | 29 | 1 | 0 | 0 |
| openalex | 26 | 4 | 0 | 0 |
| crossref | 30 | 0 | 0 | 0 |
| stack_exchange | 15 | 15 | 0 | 0 |
| lobsters | 19 | 11 | 0 | 0 |

## 3. Slot-Share + Baselines

actual% = engine slot-count in class / total slot-count in class × 100  
uniform% = 1 / N_engines_in_class × 100 (33.3% GENERAL/ACADEMIC · 50.0% QA)  
ok_adj% = engine OK count / sum of OK counts in class × 100  
Δ = actual − baseline (negative = underrepresented · positive = overrepresented)

### GENERAL

| Engine | actual% | uniform% | ok_adj% | Δ_uniform | Δ_ok_adj |
|--------|--------:|---------:|--------:|----------:|---------:|
| google | 35.6 | 33.3 | 33.3 | +2.2 | +2.2 |
| duckduckgo | 34.5 | 33.3 | 33.3 | +1.2 | +1.2 |
| mojeek | 29.9 | 33.3 | 33.3 | -3.4 | -3.4 |

### ACADEMIC

| Engine | actual% | uniform% | ok_adj% | Δ_uniform | Δ_ok_adj |
|--------|--------:|---------:|--------:|----------:|---------:|
| google_scholar | 32.2 | 33.3 | 34.1 | -1.1 | -1.9 |
| openalex | 29.0 | 33.3 | 30.6 | -4.4 | -1.6 |
| crossref | 38.8 | 33.3 | 35.3 | +5.5 | +3.5 |

### QA

| Engine | actual% | uniform% | ok_adj% | Δ_uniform | Δ_ok_adj |
|--------|--------:|---------:|--------:|----------:|---------:|
| stack_exchange | 38.5 | 50.0 | 44.1 | -11.5 | -5.7 |
| lobsters | 61.5 | 50.0 | 55.9 | +11.5 | +5.7 |

## 4. Per-Query Distribution

Cell = slot-count contributed by that engine in that query.  
Row sums exceed 20 when GENERAL URLs have multiple contributing engines.

| # | Query | google | ddg | mojeek | scholar | openalex | crossref | stack_ex | lobsters | Sum |
|---|-------|---:|---:|---:|---:|---:|---:|---:|---:|----:|
| 1 | python asyncio best practices | 6 | 5 | 4 | 2 | 2 | 2 | 1 | 1 | 23 |
| 2 | rust ownership borrow checker explained | 5 | 5 | 4 | 2 | 2 | 2 | 1 | 1 | 22 |
| 3 | fastapi websocket reconnect handler | 6 | 4 | 4 | 3 | 1 | 2 | 0 | 0 | 20 |
| 4 | docker compose health check restart poli | 6 | 5 | 6 | 2 | 2 | 2 | 1 | 1 | 25 |
| 5 | git rebase vs merge workflow | 5 | 5 | 4 | 2 | 2 | 2 | 2 | 1 | 23 |
| 6 | PostgreSQL query optimization composite  | 6 | 7 | 3 | 2 | 2 | 2 | 1 | 1 | 24 |
| 7 | react server components vs client compon | 5 | 6 | 4 | 2 | 2 | 2 | 1 | 1 | 23 |
| 8 | nginx reverse proxy websocket configurat | 5 | 5 | 6 | 2 | 2 | 2 | 2 | 1 | 25 |
| 9 | transformer attention mechanism explaine | 5 | 5 | 5 | 2 | 2 | 2 | 1 | 1 | 23 |
| 10 | RLHF reinforcement learning human feedba | 7 | 6 | 6 | 2 | 2 | 2 | 0 | 3 | 28 |
| 11 | vector database approximate nearest neig | 5 | 5 | 4 | 2 | 3 | 2 | 1 | 1 | 23 |
| 12 | RAG retrieval augmented generation bench | 5 | 5 | 5 | 4 | 2 | 2 | 0 | 2 | 25 |
| 13 | climate change carbon capture technology | 6 | 5 | 4 | 2 | 2 | 2 | 0 | 0 | 21 |
| 14 | epidemiology cohort study design methodo | 4 | 5 | 4 | 2 | 3 | 2 | 0 | 0 | 20 |
| 15 | Bewerbung Lebenslauf Format Deutschland | 5 | 7 | 5 | 2 | 2 | 2 | 0 | 0 | 23 |
| 16 | Mietvertrag Kündigungsfrist gesetzliche  | 5 | 5 | 4 | 3 | 1 | 2 | 0 | 0 | 20 |
| 17 | GmbH Gründung Kosten Schritte | 6 | 5 | 4 | 3 | 0 | 3 | 0 | 0 | 21 |
| 18 | Krankenversicherung Vergleich gesetzlich | 6 | 4 | 4 | 2 | 2 | 2 | 0 | 0 | 20 |
| 19 | Python Programmierung Anfänger Tutorial  | 5 | 5 | 4 | 3 | 0 | 3 | 0 | 0 | 20 |
| 20 | Datenschutz DSGVO Website Impressum | 5 | 6 | 4 | 2 | 2 | 2 | 1 | 0 | 22 |
| 21 | crawl4ai stealth browser detection bypas | 8 | 7 | 6 | 1 | 0 | 5 | 0 | 0 | 27 |
| 22 | pydoll chromium CDP automation | 5 | 7 | 7 | 0 | 0 | 6 | 0 | 0 | 25 |
| 23 | tmux session management scripting | 6 | 4 | 4 | 2 | 2 | 2 | 1 | 1 | 22 |
| 24 | trafilatura vs readability content extra | 5 | 7 | 4 | 2 | 2 | 2 | 0 | 2 | 24 |
| 25 | SPLADE sparse retrieval model implementa | 6 | 6 | 7 | 2 | 3 | 2 | 0 | 3 | 29 |
| 26 | best programming language 2025 | 5 | 5 | 4 | 2 | 2 | 2 | 1 | 1 | 22 |
| 27 | how does DNS work | 5 | 5 | 4 | 2 | 2 | 2 | 1 | 1 | 22 |
| 28 | quantum computing error correction | 6 | 5 | 5 | 2 | 2 | 4 | 1 | 1 | 26 |
| 29 | kubernetes vs docker swarm comparison | 5 | 4 | 4 | 2 | 2 | 2 | 0 | 2 | 21 |
| 30 | open source alternative to notion | 5 | 4 | 5 | 2 | 2 | 2 | 1 | 1 | 22 |

