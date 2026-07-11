# Engine Distribution Analysis — 20260505_230843

Source: `pipeline_smoke_20260505_223430.md`  
URL records parsed: 579  
Queries: 30

## 1. Per-Engine Slot-Count Total

Each URL record contributes +1 to every engine listed in its `Engines:` field.  
Solo = engine is the only known contributor for that URL.  
Overlap = URL has ≥2 known engine contributors.

| Engine | Class | Total | GENERAL | ACADEMIC | QA | Solo | Overlap |
|--------|-------|------:|--------:|---------:|---:|-----:|--------:|
| google | GENERAL | 170 | 166 | 1 | 3 | 84 | 86 |
| duckduckgo | GENERAL | 167 | 162 | 3 | 2 | 82 | 85 |
| mojeek | GENERAL | 143 | 139 | 0 | 4 | 94 | 49 |
| google_scholar | ACADEMIC | 67 | 5 | 62 | 0 | 59 | 8 |
| openalex | ACADEMIC | 51 | 0 | 51 | 0 | 48 | 3 |
| crossref | ACADEMIC | 70 | 0 | 70 | 0 | 67 | 3 |
| stack_exchange | QA | 17 | 2 | 0 | 15 | 13 | 4 |
| lobsters | QA | 26 | 2 | 0 | 24 | 22 | 4 |

Column sums — GENERAL: **476** (URL count 360 = 12 × 30 queries; sum ≥ URL count due to multi-engine overlaps)  
ACADEMIC: **187** (URL count 180)  
QA: **48** (URL count 39)

## 2. Per-Engine Status Aggregate

Quoted through from `pipeline_smoke_20260505_223430.md` — no recomputation.

| Engine | OK | EMPTY | TIMEOUT | ERROR |
|--------|---:|------:|--------:|------:|
| google | 30 | 0 | 0 | 0 |
| duckduckgo | 30 | 0 | 0 | 0 |
| mojeek | 30 | 0 | 0 | 0 |
| google_scholar | 29 | 0 | 1 | 0 |
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
| google | 35.5 | 33.3 | 33.3 | +2.2 | +2.2 |
| duckduckgo | 34.7 | 33.3 | 33.3 | +1.4 | +1.4 |
| mojeek | 29.8 | 33.3 | 33.3 | -3.6 | -3.6 |

### ACADEMIC

| Engine | actual% | uniform% | ok_adj% | Δ_uniform | Δ_ok_adj |
|--------|--------:|---------:|--------:|----------:|---------:|
| google_scholar | 33.9 | 33.3 | 34.1 | +0.5 | -0.2 |
| openalex | 27.9 | 33.3 | 30.6 | -5.5 | -2.7 |
| crossref | 38.3 | 33.3 | 35.3 | +4.9 | +3.0 |

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
| 1 | python asyncio best practices | 5 | 5 | 4 | 2 | 2 | 2 | 1 | 1 | 22 |
| 2 | rust ownership borrow checker explained | 5 | 4 | 4 | 2 | 2 | 2 | 1 | 1 | 21 |
| 3 | fastapi websocket reconnect handler | 6 | 5 | 4 | 3 | 1 | 2 | 0 | 0 | 21 |
| 4 | docker compose health check restart poli | 6 | 5 | 6 | 2 | 2 | 2 | 1 | 1 | 25 |
| 5 | git rebase vs merge workflow | 7 | 5 | 6 | 2 | 2 | 2 | 2 | 1 | 27 |
| 6 | PostgreSQL query optimization composite  | 5 | 7 | 4 | 2 | 2 | 2 | 1 | 1 | 24 |
| 7 | react server components vs client compon | 4 | 5 | 5 | 2 | 2 | 2 | 1 | 1 | 22 |
| 8 | nginx reverse proxy websocket configurat | 6 | 5 | 6 | 2 | 2 | 2 | 2 | 1 | 26 |
| 9 | transformer attention mechanism explaine | 5 | 5 | 5 | 2 | 2 | 2 | 1 | 1 | 23 |
| 10 | RLHF reinforcement learning human feedba | 8 | 8 | 8 | 2 | 2 | 2 | 0 | 3 | 33 |
| 11 | vector database approximate nearest neig | 6 | 6 | 4 | 2 | 3 | 2 | 1 | 1 | 25 |
| 12 | RAG retrieval augmented generation bench | 7 | 5 | 6 | 6 | 2 | 1 | 0 | 2 | 29 |
| 13 | climate change carbon capture technology | 5 | 4 | 4 | 2 | 2 | 2 | 0 | 0 | 19 |
| 14 | epidemiology cohort study design methodo | 5 | 6 | 4 | 3 | 2 | 2 | 0 | 0 | 22 |
| 15 | Bewerbung Lebenslauf Format Deutschland | 5 | 5 | 5 | 2 | 2 | 2 | 0 | 0 | 21 |
| 16 | Mietvertrag Kündigungsfrist gesetzliche  | 8 | 6 | 3 | 3 | 1 | 2 | 0 | 0 | 23 |
| 17 | GmbH Gründung Kosten Schritte | 7 | 6 | 3 | 3 | 0 | 3 | 0 | 0 | 22 |
| 18 | Krankenversicherung Vergleich gesetzlich | 6 | 5 | 4 | 2 | 2 | 2 | 0 | 0 | 21 |
| 19 | Python Programmierung Anfänger Tutorial  | 5 | 5 | 4 | 3 | 0 | 3 | 0 | 0 | 20 |
| 20 | Datenschutz DSGVO Website Impressum | 5 | 5 | 4 | 2 | 2 | 2 | 1 | 0 | 21 |
| 21 | crawl4ai stealth browser detection bypas | 7 | 8 | 6 | 1 | 0 | 5 | 0 | 0 | 27 |
| 22 | pydoll chromium CDP automation | 4 | 7 | 8 | 0 | 0 | 6 | 0 | 0 | 25 |
| 23 | tmux session management scripting | 4 | 4 | 4 | 2 | 2 | 2 | 1 | 1 | 20 |
| 24 | trafilatura vs readability content extra | 5 | 8 | 4 | 2 | 2 | 2 | 0 | 2 | 25 |
| 25 | SPLADE sparse retrieval model implementa | 7 | 8 | 8 | 3 | 2 | 2 | 0 | 3 | 33 |
| 26 | best programming language 2025 | 6 | 5 | 3 | 2 | 2 | 2 | 1 | 1 | 22 |
| 27 | how does DNS work | 6 | 6 | 3 | 2 | 2 | 2 | 1 | 1 | 23 |
| 28 | quantum computing error correction | 6 | 5 | 5 | 2 | 2 | 4 | 1 | 1 | 26 |
| 29 | kubernetes vs docker swarm comparison | 5 | 4 | 4 | 2 | 2 | 2 | 0 | 2 | 21 |
| 30 | open source alternative to notion | 4 | 5 | 5 | 2 | 2 | 2 | 1 | 1 | 22 |

