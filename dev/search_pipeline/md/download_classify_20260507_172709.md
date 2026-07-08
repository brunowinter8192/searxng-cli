# Download-Classify Probe — 20260507_172709

## Section 1 — Run Metadata

| Field | Value |
|-------|-------|
| Timestamp | 20260507_172709 |
| Source smoke | pipeline_smoke_20260505_223430.md |
| Source free-word | free_word_injection_probe_20260507_033631.md |
| Total unique URLs in combined pool (with path) | 732 |
| Tier breakdown | T1=43 T2=244 T3=300 (sampled) T4=145 |
| doi.org: total in pool | (not probed: full pool has ~2013) |
| doi.org: sampled | 300 (seed=42) |
| doi_sample file | pool_doi_sample_20260507_172709.txt |
| Concurrency | global_max=8, keepalive=4, per_domain_cap=2 |
| Timeout | Tier-1=15.0s, all others=8.0s |
| Courtesy sleep | 0.5s per domain slot after request |
| Wall clock | 4m 4s |
| Outcomes | PDF_OK=47 HTML_HAS_PDF_LINK=124 HTML_PAYWALL=3 HTML_OK=491 TIMEOUT=4 CONN_ERROR=0 HTTP_4xx/5xx=63 |

## Section 2 — Per-Domain Aggregate Table

| Domain | Total | PDF_OK | HTML_OK | HTML_HAS_PDF_LINK | HTML_PAYWALL | HTTP_4xx | HTTP_5xx | TIMEOUT | CONN_ERROR |
|--------|------:|-------:|--------:|------------------:|-------------:|---------:|---------:|--------:|-----------:|
| doi.org | 300 | 4 | 145 | 107 | 3 | 35 | 2 | 4 | 0 |
| openalex.org | 243 | 0 | 243 | 0 | 0 | 0 | 0 | 0 | 0 |
| books.google.com | 59 | 0 | 59 | 0 | 0 | 0 | 0 | 0 | 0 |
| arxiv.org | 32 | 32 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dl.acm.org | 25 | 0 | 10 | 0 | 0 | 15 | 0 | 0 | 0 |
| link.springer.com | 15 | 0 | 4 | 11 | 0 | 0 | 0 | 0 | 0 |
| aclanthology.org | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ieeexplore.ieee.org | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| jstor.org | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| muse.jhu.edu | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| researchgate.net | 4 | 0 | 3 | 0 | 0 | 1 | 0 | 0 | 0 |
| sciencedirect.com | 4 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| search.proquest.com | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| direct.mit.edu | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| scribd.com | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| mdpi.com | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| nature.com | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| pmc.ncbi.nlm.nih.gov | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| thieme-connect.com | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| accpjournals.onlinelibrary.wiley.com | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| cyberleninka.ru | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| elib.uni-stuttgart.de | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| inspirehep.net | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| openreview.net | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| scijournals.onlinelibrary.wiley.com | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| search.ebscohost.com | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| semanticscholar.org | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| spiedigitallibrary.org | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| tandfonline.com | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |

## Section 3 — Tier-1 Transform Effectiveness

| Domain | Applied Transform | PDF_OK | HTML_HAS_PDF_LINK | HTML_OK | HTML_PAYWALL | HTTP_4xx | TIMEOUT | CONN_ERROR |
|--------|:-----------------:|-------:|------------------:|--------:|-------------:|---------:|--------:|-----------:|
| aclanthology.org | 6/8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| arxiv.org | 29/32 | 32 | 0 | 0 | 0 | 0 | 0 | 0 |
| openreview.net | 1/1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| pmc.ncbi.nlm.nih.gov | 0/2 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

### Tier-1 URL Detail

| Domain | Original URL | Transformed URL | Outcome |
|--------|-------------|-----------------|---------|
| aclanthology.org | https://aclanthology.org/2020.emnlp-main.400/ | https://aclanthology.org/2020.emnlp-main.400.pdf | PDF_OK |
| aclanthology.org | https://aclanthology.org/2021.acl-long.316/ | https://aclanthology.org/2021.acl-long.316.pdf | PDF_OK |
| aclanthology.org | https://aclanthology.org/2021.tacl-1.20/ | https://aclanthology.org/2021.tacl-1.20.pdf | PDF_OK |
| aclanthology.org | https://aclanthology.org/2023.paclic-1.82.pdf | — | PDF_OK |
| aclanthology.org | https://aclanthology.org/2024.findings-acl.372/ | https://aclanthology.org/2024.findings-acl.372.pdf | PDF_OK |
| aclanthology.org | https://aclanthology.org/2025.acl-industry.61/ | https://aclanthology.org/2025.acl-industry.61.pdf | PDF_OK |
| aclanthology.org | https://aclanthology.org/2025.findings-naacl.157/ | https://aclanthology.org/2025.findings-naacl.157.pdf | PDF_OK |
| aclanthology.org | https://aclanthology.org/2025.ijcnlp-long.7.pdf | — | PDF_OK |
| arxiv.org | https://arxiv.org/abs/1705.01509 | https://arxiv.org/pdf/1705.01509 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/1706.03741 | https://arxiv.org/pdf/1706.03741 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/1907.11157 | https://arxiv.org/pdf/1907.11157 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2010.00768 | https://arxiv.org/pdf/2010.00768 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2011.06171 | https://arxiv.org/pdf/2011.06171 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2109.10086 | https://arxiv.org/pdf/2109.10086 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2305.07477 | https://arxiv.org/pdf/2305.07477 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2307.10488 | https://arxiv.org/pdf/2307.10488 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2310.12773 | https://arxiv.org/pdf/2310.12773 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2311.18503 | https://arxiv.org/pdf/2311.18503 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2401.04055 | https://arxiv.org/pdf/2401.04055 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2407.11005 | https://arxiv.org/pdf/2407.11005 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2408.10343 | https://arxiv.org/pdf/2408.10343 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2408.11119 | https://arxiv.org/pdf/2408.11119 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2410.19771 | https://arxiv.org/pdf/2410.19771 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2412.06078 | https://arxiv.org/pdf/2412.06078 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2504.12501 | https://arxiv.org/pdf/2504.12501 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2505.07671 | https://arxiv.org/pdf/2505.07671 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2506.14707 | https://arxiv.org/pdf/2506.14707 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2603.13277 | https://arxiv.org/pdf/2603.13277 | PDF_OK |
| arxiv.org | https://arxiv.org/abs/2603.22008 | https://arxiv.org/pdf/2603.22008 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2504.10816v1 | https://arxiv.org/pdf/2504.10816v1 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2504.12501v2 | https://arxiv.org/pdf/2504.12501v2 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2506.18032v1 | https://arxiv.org/pdf/2506.18032v1 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2506.19233v1 | https://arxiv.org/pdf/2506.19233v1 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2507.03608v2 | https://arxiv.org/pdf/2507.03608v2 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2509.25487v1 | https://arxiv.org/pdf/2509.25487v1 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2510.27243v1 | https://arxiv.org/pdf/2510.27243v1 | PDF_OK |
| arxiv.org | https://arxiv.org/html/2602.11443v1 | https://arxiv.org/pdf/2602.11443v1 | PDF_OK |
| arxiv.org | https://arxiv.org/pdf/2109.10086 | — | PDF_OK |
| arxiv.org | https://arxiv.org/pdf/2408.11119 | — | PDF_OK |
| arxiv.org | https://arxiv.org/pdf/2502.15526 | — | PDF_OK |
| openreview.net | https://openreview.net/forum?id=TuFjICawSc | https://openreview.net/pdf?id=TuFjICawSc | PDF_OK |
| pmc.ncbi.nlm.nih.gov | https://pmc.ncbi.nlm.nih.gov/articles/PMC4763690/ | — | HTML_OK |
| pmc.ncbi.nlm.nih.gov | https://pmc.ncbi.nlm.nih.gov/articles/PMC9172927/ | — | HTML_HAS_PDF_LINK |

## Section 4 — HTML_HAS_PDF_LINK Sample

Total with citation_pdf_url: **124**

| Original URL | citation_pdf_url |
|-------------|-----------------|
| https://cyberleninka.ru/article/n/prakticheskoe-primenenie-asinhronnogo-programm | https://cyberleninka.ru/article/n/prakticheskoe-primenenie-asinhronnogo-programm |
| https://doi.org/10.1002/9781119573364.ch12 | https://onlinelibrary.wiley.com/doi/pdf/10.1002/9781119573364.ch12 |
| https://doi.org/10.1002/9781394213948.ch7 | https://onlinelibrary.wiley.com/doi/pdf/10.1002/9781394213948.ch7 |
| https://doi.org/10.1002/met.284 | https://onlinelibrary.wiley.com/doi/pdf/10.1002/met.284 |
| https://doi.org/10.1007/0-306-47019-5_3 | https://link.springer.com/content/pdf/10.1007/0-306-47019-5_3.pdf |
| https://doi.org/10.1007/1-4020-7911-7_10 | https://link.springer.com/content/pdf/10.1007/1-4020-7911-7_10.pdf |
| https://doi.org/10.1007/978-1-4842-3742-7_9 | https://link.springer.com/content/pdf/10.1007/978-1-4842-3742-7_9.pdf |
| https://doi.org/10.1007/978-1-4842-4401-2_10 | https://link.springer.com/content/pdf/10.1007/978-1-4842-4401-2_10.pdf |
| https://doi.org/10.1007/978-1-4842-4401-2_4 | https://link.springer.com/content/pdf/10.1007/978-1-4842-4401-2_4.pdf |
| https://doi.org/10.1007/978-1-4842-6399-0_3 | https://link.springer.com/content/pdf/10.1007/978-1-4842-6399-0_3.pdf |
| https://doi.org/10.1007/978-1-4842-6399-0_9 | https://link.springer.com/content/pdf/10.1007/978-1-4842-6399-0_9.pdf |
| https://doi.org/10.1007/978-1-4842-7058-5_4 | https://link.springer.com/content/pdf/10.1007/978-1-4842-7058-5_4.pdf |
| https://doi.org/10.1007/978-1-4842-7774-4_4 | https://link.springer.com/content/pdf/10.1007/978-1-4842-7774-4_4.pdf |
| https://doi.org/10.1007/978-1-4842-7815-4_3 | https://link.springer.com/content/pdf/10.1007/978-1-4842-7815-4_3.pdf |
| https://doi.org/10.1007/978-1-4842-7996-0_1 | https://link.springer.com/content/pdf/10.1007/978-1-4842-7996-0_1.pdf |
| https://doi.org/10.1007/978-3-031-02328-6_2 | https://link.springer.com/content/pdf/10.1007/978-3-031-02328-6_2.pdf |
| https://doi.org/10.1007/978-3-031-17258-8_4 | https://link.springer.com/content/pdf/10.1007/978-3-031-17258-8_4.pdf |
| https://doi.org/10.1007/978-3-031-54680-8_3 | https://link.springer.com/content/pdf/10.1007/978-3-031-54680-8_3.pdf |
| https://doi.org/10.1007/978-3-031-56060-6_29 | https://link.springer.com/content/pdf/10.1007/978-3-031-56060-6_29.pdf |
| https://doi.org/10.1007/978-3-031-88708-6_18 | https://link.springer.com/content/pdf/10.1007/978-3-031-88708-6_18.pdf |
| https://doi.org/10.1007/978-3-322-92743-9_5 | https://link.springer.com/content/pdf/10.1007/978-3-322-92743-9_5.pdf |
| https://doi.org/10.1007/978-3-540-75148-9_3 | https://link.springer.com/content/pdf/10.1007/978-3-540-75148-9_3.pdf |
| https://doi.org/10.1007/978-3-642-40991-2_11 | https://link.springer.com/content/pdf/10.1007/978-3-642-40991-2_11.pdf |
| https://doi.org/10.1007/978-3-658-51437-2_8 | https://link.springer.com/content/pdf/10.1007/978-3-658-51437-2_8.pdf |
| https://doi.org/10.1007/978-3-662-61172-2_2 | https://link.springer.com/content/pdf/10.1007/978-3-662-61172-2_2.pdf |
| https://doi.org/10.1007/978-3-7908-2084-3_9 | https://link.springer.com/content/pdf/10.1007/978-3-7908-2084-3_9.pdf |
| https://doi.org/10.1007/979-8-8688-0069-6_16 | https://link.springer.com/content/pdf/10.1007/979-8-8688-0069-6_16.pdf |
| https://doi.org/10.1007/s10462-011-9222-1 | https://link.springer.com/content/pdf/10.1007/s10462-011-9222-1.pdf |
| https://doi.org/10.1007/s10791-005-5658-8 | https://link.springer.com/content/pdf/10.1007/s10791-005-5658-8.pdf |
| https://doi.org/10.1007/s10791-006-9019-z | https://link.springer.com/content/pdf/10.1007/s10791-006-9019-z.pdf |

## Section 5 — HTML_PAYWALL Sample

Total with paywall markers: **3**

| Original URL | Matched Marker |
|-------------|----------------|
| https://doi.org/10.1079/cabicompendium.116647 | `institutional access` |
| https://doi.org/10.1093/benz/9780199773787.article.b00147230 | `institutional access` |
| https://doi.org/10.1146/annurev-statistics-010814-020120 | `institutional login` |

## Section 6 — Per-URL Detail

| Domain | Tier | Original URL | Transform? | Final Outcome | Notes |
|--------|------|-------------|:----------:|---------------|-------|
| accpjournals.onlinelibrary.wiley.com | T4 | https://accpjournals.onlinelibrary.wiley.com/doi/abs/10.1592/phco.30.1 | — | HTTP_403 |  |
| aclanthology.org | T1 | https://aclanthology.org/2020.emnlp-main.400/ | ✓ | PDF_OK |  |
| aclanthology.org | T1 | https://aclanthology.org/2021.acl-long.316/ | ✓ | PDF_OK |  |
| aclanthology.org | T1 | https://aclanthology.org/2021.tacl-1.20/ | ✓ | PDF_OK |  |
| aclanthology.org | T1 | https://aclanthology.org/2023.paclic-1.82.pdf | — | PDF_OK |  |
| aclanthology.org | T1 | https://aclanthology.org/2024.findings-acl.372/ | ✓ | PDF_OK |  |
| aclanthology.org | T1 | https://aclanthology.org/2025.acl-industry.61/ | ✓ | PDF_OK |  |
| aclanthology.org | T1 | https://aclanthology.org/2025.findings-naacl.157/ | ✓ | PDF_OK |  |
| aclanthology.org | T1 | https://aclanthology.org/2025.ijcnlp-long.7.pdf | — | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/1705.01509 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/1706.03741 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/1907.11157 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2010.00768 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2011.06171 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2109.10086 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2305.07477 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2307.10488 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2310.12773 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2311.18503 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2401.04055 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2407.11005 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2408.10343 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2408.11119 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2410.19771 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2412.06078 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2504.12501 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2505.07671 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2506.14707 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2603.13277 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/abs/2603.22008 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2504.10816v1 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2504.12501v2 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2506.18032v1 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2506.19233v1 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2507.03608v2 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2509.25487v1 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2510.27243v1 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/html/2602.11443v1 | ✓ | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/pdf/2109.10086 | — | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/pdf/2408.11119 | — | PDF_OK |  |
| arxiv.org | T1 | https://arxiv.org/pdf/2502.15526 | — | PDF_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=0d7dDwAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=1_50DwAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=4S-fBAAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=5SRIEQAAQBAJ&oi=fnd&pg=PP2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=5SRIEQAAQBAJ&oi=fnd&pg=PP2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=5SRIEQAAQBAJ&oi=fnd&pg=PP2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=6OOYDwAAQBAJ&oi=fnd&pg=PA2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=6OOYDwAAQBAJ&oi=fnd&pg=PA2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=6PXtDwAAQBAJ&oi=fnd&pg=PT6 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=8ef3-s6fixIC&oi=fnd&pg=PP6 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=8ef3-s6fixIC&oi=fnd&pg=PP6 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Aht1CgAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Aht1CgAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=CGAHEQAAQBAJ&oi=fnd&pg=PT1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=F23AAgAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=F23AAgAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=F23AAgAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=I9tCr21-s-AC&oi=fnd&pg=PR1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=JN_JDAAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=KY0BDObXftUC&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=M9xdEAAAQBAJ&oi=fnd&pg=PR1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=M9xdEAAAQBAJ&oi=fnd&pg=PR1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=M9xdEAAAQBAJ&oi=fnd&pg=PR1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=N8FwDwAAQBAJ&oi=fnd&pg=PR5 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=PseNEQAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=RhalDgAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Tn18DwAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Tn18DwAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Tn18DwAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Vbb3EAAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Vbb3EAAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Vbb3EAAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=WreZDwAAQBAJ&oi=fnd&pg=PR5 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=XYloDwAAQBAJ&oi=fnd&pg=PT9 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=XZmGEAAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Z8tHY0IjjQYC&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=Zt-sEAAAQBAJ&oi=fnd&pg=PT4 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=_97JDAAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=bE_lAwAAQBAJ&oi=fnd&pg=PT7 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=cYLhDwAAQBAJ&oi=fnd&pg=PT3 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=cYxHDwAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=cYxHDwAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=cYxHDwAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=fTxRAwAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=ifpBDwAAQBAJ&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=jGInCgAAQBAJ&oi=fnd&pg=PP3 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=jV_NDwAAQBAJ&oi=fnd&pg=PT2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=jV_NDwAAQBAJ&oi=fnd&pg=PT2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=jV_NDwAAQBAJ&oi=fnd&pg=PT2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=jV_NDwAAQBAJ&oi=fnd&pg=PT2 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=kKF9EAAAQBAJ&oi=fnd&pg=PA9 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=m5OF2rFh1wgC&oi=fnd&pg=PA1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=sPt9DwAAQBAJ&oi=fnd&pg=PR5 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=sPt9DwAAQBAJ&oi=fnd&pg=PR5 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=u0GbAgAAQBAJ&oi=fnd&pg=PR5 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=wRxdEAAAQBAJ&oi=fnd&pg=PA6 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=ynFrCgAAQBAJ&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?hl=en&lr=&id=zwvlqspyOK8C&oi=fnd&pg=PP1 | — | HTML_OK |  |
| books.google.com | T4 | https://books.google.com/books?id=YqljzgEACAAJ&printsec=copyright | — | HTML_OK |  |
| cyberleninka.ru | T4 | https://cyberleninka.ru/article/n/prakticheskoe-primenenie-asinhronnog | — | HTML_HAS_PDF_LINK | pdf_url=https://cyberleninka.ru/article/n/prakti |
| direct.mit.edu | T4 | https://direct.mit.edu/books/edited-volume/4027/Practical-Applications | — | HTTP_403 |  |
| direct.mit.edu | T4 | https://direct.mit.edu/tacl/article-abstract/doi/10.1162/tacl_a_00369/ | — | HTTP_403 |  |
| direct.mit.edu | T4 | https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00369/100684/Sp | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/10.1145/3465405 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/10.1145/3634912 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3269206.3271800 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3404835.3463098 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3459637.3482159 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3477495.3531774 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3477495.3531833 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3511808.3557588 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3539618.3591943 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3539618.3592065 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3589335.3651945 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3626772.3657834 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3626772.3657906 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3626772.3657968 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3634912 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3637870 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3652032.3657579 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3701228 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3726302.3730185 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3726302.3730225 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/abs/10.1145/3743127 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/full/10.1145/3634912 | — | HTML_OK |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/fullHtml/10.5555/1412202.1412204 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/pdf/10.1145/274440.274441 | — | HTTP_403 |  |
| dl.acm.org | T4 | https://dl.acm.org/doi/pdf/10.1145/3152823 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1002/2015jd024121 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1002/9781118562796.ch1 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1002/9781119573364.ch11 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1002/9781119573364.ch12 | — | HTML_HAS_PDF_LINK | pdf_url=https://onlinelibrary.wiley.com/doi/pdf/ |
| doi.org | T3 | https://doi.org/10.1002/9781119573364.ch20 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1002/9781394213948.ch7 | — | HTML_HAS_PDF_LINK | pdf_url=https://onlinelibrary.wiley.com/doi/pdf/ |
| doi.org | T3 | https://doi.org/10.1002/met.284 | — | HTML_HAS_PDF_LINK | pdf_url=https://onlinelibrary.wiley.com/doi/pdf/ |
| doi.org | T3 | https://doi.org/10.1007/0-306-47019-5_3 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/1-4020-7911-7_10 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-137-26401-5 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-137-26401-5_5 | — | TIMEOUT |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-137-26401-5_8 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-3742-7_9 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-4401-2_10 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-4401-2_4 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-5831-6_2 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-6399-0_3 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-6399-0_9 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-7058-5_4 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-7774-4 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-7774-4_4 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-7815-4_3 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-7996-0 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-7996-0_1 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-8140-6_10 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-8140-6_11 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-8140-6_5 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-1-4842-8140-6_7 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-3-031-02328-6_2 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-031-17258-8_4 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-031-54680-8_3 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-031-56060-6_29 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-031-88708-6_18 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-319-11755-3 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1007/978-3-322-92743-9_5 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-540-75148-9_3 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-642-40991-2_11 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-658-51437-2_8 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-662-61172-2_2 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/978-3-7908-2084-3_9 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/979-8-8688-0069-6_16 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/s10462-011-9222-1 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/s10791-005-5658-8 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/s10791-006-9019-z | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/s10791-017-9322-x | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/s11042-022-13428-4 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/s40747-020-00212-w | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/s41297-024-00227-0 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1007/springerreference_63496 | — | TIMEOUT |  |
| doi.org | T3 | https://doi.org/10.1016/b978-1-59-749957-6.00002-8 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.agrformet.2013.11.001 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.comnet.2024.110397 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.envres.2012.06.011 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.forsciint.2017.05.025 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.geoderma.2023.116710 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.heliyon.2024.e26937 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.ijggc.2013.03.003 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.jclepro.2015.02.004 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.patrec.2018.08.010 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1016/j.softx.2025.102463 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1017/cbo9780511812217.002 | — | TIMEOUT |  |
| doi.org | T3 | https://doi.org/10.1017/s027226310505014x | — | HTTP_404 |  |
| doi.org | T3 | https://doi.org/10.1023/a:1007612920971 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1029/2019rg000678 | — | HTML_HAS_PDF_LINK | pdf_url=https://onlinelibrary.wiley.com/doi/pdf/ |
| doi.org | T3 | https://doi.org/10.1029/94jd00219 | — | HTML_HAS_PDF_LINK | pdf_url=https://onlinelibrary.wiley.com/doi/pdf/ |
| doi.org | T3 | https://doi.org/10.1029/95jc00466 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1038/s41377-020-0302-3 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1038/s41467-025-60514-w | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1038/s41559-023-02206-6 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1038/s41598-026-40112-6 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1038/s41746-022-00589-7 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1038/s43586-021-00015-4 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1039/d4dd00040d | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1051/jphys:0199000510150158500 | — | HTML_HAS_PDF_LINK | pdf_url=http://jphys.journaldephysique.org/artic |
| doi.org | T3 | https://doi.org/10.1057/9780230599987_6 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1063/5.0190834 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1073/pnas.1802705116 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1079/cabicompendium.116647 | — | HTML_PAYWALL | marker=institutional access |
| doi.org | T3 | https://doi.org/10.1080/02643290143000169 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1086/382719 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1088/0305-4470/34/14/322 | — | HTML_HAS_PDF_LINK | pdf_url=https://iopscience.iop.org/article/10.10 |
| doi.org | T3 | https://doi.org/10.1088/0954-898x_2_4_004 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1093/actrade/9780192882042.001.0001 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1093/benz/9780199773787.article.b00147230 | — | HTML_PAYWALL | marker=institutional access |
| doi.org | T3 | https://doi.org/10.1093/bioinformatics/bth060 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1093/ooec/odac004 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1109/36.841980 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/5.726791 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/access.2014.2332453 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/access.2017.2698142 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/access.2019.2906934 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/access.2019.2956508 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/access.2020.3027357 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/access.2026.3686254/mm3 | — | PDF_OK |  |
| doi.org | T3 | https://doi.org/10.1109/comst.2015.2444095 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/csr57506.2023.10224985 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/icvrv.2014.16 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/jbhi.2020.2991043 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/jiot.2019.2942085 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/lsp.2025.3542965/mm1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/smartcomp58114.2023.00073 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tap.2026.3659989 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tci.2023.3332007/mm1 | — | PDF_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tcsvt.2013.2242594 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tip.2015.2416634 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tip.2016.2624140 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tmm.2009.2012913 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tpami.2023.3316020/mm1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tpami.2025.3563398/mm1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tpami.2025.3612480/mm1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1109/tsmc.2023.3305498/mm1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.11124/jbisrir-2017-003382 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1117/12.2630471 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1126/science.aal2108 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1136/amiajnl-2011-000464 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1136/bmj.m2632 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1142/9789813208322_0038 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/234533.234534 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/2578726.2578734 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/2661229.2661239 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1145/3065386 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/3077136.3080832 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/3097983.3098096 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/3178876.3186067 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1145/3240323.3240355 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1145/348.318586 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/3556536 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1145/3578337.3605126 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1146/annurev-statistics-010814-020120 | — | HTML_PAYWALL | marker=institutional login |
| doi.org | T3 | https://doi.org/10.1155/2022/6886086 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1158/1055-9965.epi-05-0456 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1159/000076784 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1162/coli.2006.32.1.13 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1162/tacl_a_00369 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1163/9789401201513_010 | — | HTML_HAS_PDF_LINK | pdf_url=https://brill.com/downloadpdf/display/bo |
| doi.org | T3 | https://doi.org/10.1175/jcli-d-20-0166.1 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.ametsoc.org/downloadpdf |
| doi.org | T3 | https://doi.org/10.1175/jhm-d-17-0063.1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1177/014833311005900318 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1177/014833318002900424 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1186/1472-6963-13-158 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1186/1750-0680-4-2 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1186/s13643-016-0249-x | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.1190/1.1822691 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.1201/b15056-18 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.13053/cys-18-3-2043 | — | TIMEOUT |  |
| doi.org | T3 | https://doi.org/10.13140/rg.2.1.3175.8968 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1351/goldbook.13120 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/chq.0.1882 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.0.0001 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.0.0018 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.0.0051 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.0.0078 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2004.0015 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2006.0012 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2007.0006 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2014.0005 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2014.0013 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2015.0000 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2015.0018 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2016.0003 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2016.0011 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2016.0013 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2016.0020 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2016.0021 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2017.0005 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2018.0001 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2018.0010 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2018.0013 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2018.0015 | — | HTTP_502 |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2019.0003 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2020.0000 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2021.0015 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1353/tks.2022.0027 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1371/journal.pcbi.1002854 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.plos.org/ploscompbiol/a |
| doi.org | T3 | https://doi.org/10.1371/journal.pgen.1002768 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.plos.org/plosgenetics/a |
| doi.org | T3 | https://doi.org/10.1371/journal.pone.0139779 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.plos.org/plosone/articl |
| doi.org | T3 | https://doi.org/10.1371/journal.pone.0140381 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.plos.org/plosone/articl |
| doi.org | T3 | https://doi.org/10.1371/journal.pone.0165449 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.plos.org/plosone/articl |
| doi.org | T3 | https://doi.org/10.14210/tva.v26.20139 | — | HTML_HAS_PDF_LINK | pdf_url=https://periodicos.univali.br/index.php/ |
| doi.org | T3 | https://doi.org/10.14778/2733085.2733096 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.14811/clr.v37i0.186 | — | HTML_HAS_PDF_LINK | pdf_url=https://barnboken.net/index.php/clr/arti |
| doi.org | T3 | https://doi.org/10.1515/9783111334608-024 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.degruyterbrill.com/document/ |
| doi.org | T3 | https://doi.org/10.1523/jneurosci.3737-05d.2006 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.jneurosci.org/content/jneuro |
| doi.org | T3 | https://doi.org/10.15276/hait.05.2022.18 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.15587/1729-4061.2022.267892 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.uran.ua/eejet/article/d |
| doi.org | T3 | https://doi.org/10.1609/aaai.v24i1.7686 | — | HTML_HAS_PDF_LINK | pdf_url=https://ojs.aaai.org/index.php/AAAI/arti |
| doi.org | T3 | https://doi.org/10.17615/r8ve-dy84 | — | HTML_HAS_PDF_LINK | pdf_url=http://cdr.lib.unc.edu/downloads/sq87bz2 |
| doi.org | T3 | https://doi.org/10.18290/pepsi-2021-0007 | — | HTML_HAS_PDF_LINK | pdf_url=https://ojs.tnkul.pl/index.php/jpepsi/ar |
| doi.org | T3 | https://doi.org/10.18637/jss.v070.b04 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/2020.acl-main.85 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/2021.naacl-main.45 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/2023.semeval-1.317 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/2024.acl-long.525 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/d18-1260 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/e17-1059 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/n16-2002 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.18653/v1/p19-1499 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.1920/wp.cem.2011.4111 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.21105/joss.05867 | — | HTML_HAS_PDF_LINK | pdf_url=https://joss.theoj.org/papers/10.21105/j |
| doi.org | T3 | https://doi.org/10.21203/rs.3.rs-6594833/v1 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.researchsquare.com/article/r |
| doi.org | T3 | https://doi.org/10.2139/ssrn.4296843 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.2139/ssrn.6635168 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.21547/jss.843678 | — | HTML_HAS_PDF_LINK | pdf_url=/en/download/article-file/1458164 |
| doi.org | T3 | https://doi.org/10.22215/etd/2020-13941 | — | HTML_HAS_PDF_LINK | pdf_url=https://carleton.scholaris.ca/bitstreams |
| doi.org | T3 | https://doi.org/10.22323/1.501.0921 | — | HTML_HAS_PDF_LINK | pdf_url=https://pos.sissa.it/501/921/pdf |
| doi.org | T3 | https://doi.org/10.22409/geograficidade2017.71.a12971 | — | HTTP_503 |  |
| doi.org | T3 | https://doi.org/10.2307/j.ctvpj75hk.12 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.24138/jcomss.v16i1.1027 | — | HTML_HAS_PDF_LINK | pdf_url=https://jcoms.fesb.unist.hr/pdfs/v16n1_1 |
| doi.org | T3 | https://doi.org/10.2478/mgr-2019-0004 | — | HTML_HAS_PDF_LINK | pdf_url=https://reference-global.com/download/ar |
| doi.org | T3 | https://doi.org/10.2495/air190051 | — | HTML_HAS_PDF_LINK | pdf_url=http://www.witpress.com/Secure/elibrary/ |
| doi.org | T3 | https://doi.org/10.25080/gerudo-f2bc6f59-003 | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/g |
| doi.org | T3 | https://doi.org/10.25080/majora-14bd3278-00a | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/M |
| doi.org | T3 | https://doi.org/10.25080/majora-1b6fd038-02b | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/p |
| doi.org | T3 | https://doi.org/10.25080/majora-7b98e3ed-00d | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/M |
| doi.org | T3 | https://doi.org/10.25080/majora-92bf1922-00a | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/M |
| doi.org | T3 | https://doi.org/10.25080/majora-92bf1922-00b | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/M |
| doi.org | T3 | https://doi.org/10.25080/majora-ebaa42b7-011 | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/M |
| doi.org | T3 | https://doi.org/10.25080/rjfg8479 | — | HTML_HAS_PDF_LINK | pdf_url=https://proceedings.scipy.org/articles/R |
| doi.org | T3 | https://doi.org/10.26034/cm.jostrans.2009.648 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.jostrans.org/article/downloa |
| doi.org | T3 | https://doi.org/10.26434/chemrxiv-2024-3xq9z | — | HTML_HAS_PDF_LINK | pdf_url=https://chemrxiv.org/doi/pdf/10.26434/ch |
| doi.org | T3 | https://doi.org/10.26565/2218-2926-2020-20-03 | — | HTML_HAS_PDF_LINK | pdf_url=https://periodicals.karazin.ua/cognition |
| doi.org | T3 | https://doi.org/10.26686/wgtn.13557857.v1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.26906/sunz.2018.4.095 | — | HTML_HAS_PDF_LINK | pdf_url=https://journals.nupp.edu.ua/sunz/articl |
| doi.org | T3 | https://doi.org/10.26907/1562-5419-2025-28-2-432-453 | — | HTML_HAS_PDF_LINK | pdf_url=https://rdl-journal.ru/article/download/ |
| doi.org | T3 | https://doi.org/10.29025/2079-6021-2025-3-229-240 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.30998/faktorexacta.v17i3.21920 | — | HTML_HAS_PDF_LINK | pdf_url=https://journal.lppmunindra.ac.id/index. |
| doi.org | T3 | https://doi.org/10.3102/1436209 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.3115/v1/n15-1020 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.3139/9783446468146.001 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.31390/gradschool_disstheses.1657 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.31673/2412-9070.2024.032327 | — | HTML_HAS_PDF_LINK | pdf_url=https://con.dut.edu.ua/index.php/communi |
| doi.org | T3 | https://doi.org/10.32520/eji.v5i2.1593 | — | HTML_HAS_PDF_LINK | pdf_url=https://ejournal-fkip.unisi.ac.id/eji/ar |
| doi.org | T3 | https://doi.org/10.32614/cran.package.reticulate | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.32782/2409-1154.2024.65.47 | — | PDF_OK |  |
| doi.org | T3 | https://doi.org/10.33612/diss.972290628 | — | HTML_HAS_PDF_LINK | pdf_url=https://research.rug.nl/files/972290630/ |
| doi.org | T3 | https://doi.org/10.33619/2414-2948/114/19 | — | PDF_OK |  |
| doi.org | T3 | https://doi.org/10.3389/fgene.2016.00066 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.3389/fmars.2019.00447 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.3389/fphy.2022.870560 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.3389/fpsyg.2010.00227 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.3389/fpsyg.2018.01792 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.3390/app142411978 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/2076-3417/14/24/119 |
| doi.org | T3 | https://doi.org/10.3390/electronics14010157 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/2079-9292/14/1/157/ |
| doi.org | T3 | https://doi.org/10.3390/en13153770 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/1996-1073/13/15/377 |
| doi.org | T3 | https://doi.org/10.3390/machines12020142 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/2075-1702/12/2/142/ |
| doi.org | T3 | https://doi.org/10.3390/rs3061104 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/2072-4292/3/6/1104/ |
| doi.org | T3 | https://doi.org/10.3390/s19030589 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/1424-8220/19/3/589/ |
| doi.org | T3 | https://doi.org/10.35819/tear.v9.n1.a4044 | — | HTML_HAS_PDF_LINK | pdf_url=https://periodicos.ifrs.edu.br/index.php |
| doi.org | T3 | https://doi.org/10.3758/s13423-016-1191-6 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.3758/s13428-014-0534-3 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| doi.org | T3 | https://doi.org/10.3790/978-3-428-51915-6 | — | HTML_HAS_PDF_LINK | pdf_url=https://elibrary.duncker-humblot.com/pdf |
| doi.org | T3 | https://doi.org/10.3997/2214-4609.202011831 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.4148/2373-0978.1073 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.4324/9781003517177 | — | HTML_HAS_PDF_LINK | pdf_url=https://api.taylorfrancis.com/content/bo |
| doi.org | T3 | https://doi.org/10.48550/arxiv.1911.05722 | — | HTML_HAS_PDF_LINK | pdf_url=https://arxiv.org/pdf/1911.05722 |
| doi.org | T3 | https://doi.org/10.48550/arxiv.2104.08663 | — | HTML_HAS_PDF_LINK | pdf_url=https://arxiv.org/pdf/2104.08663 |
| doi.org | T3 | https://doi.org/10.48550/arxiv.2212.14565 | — | HTML_HAS_PDF_LINK | pdf_url=https://arxiv.org/pdf/2212.14565 |
| doi.org | T3 | https://doi.org/10.48550/arxiv.2406.14088 | — | HTML_HAS_PDF_LINK | pdf_url=https://arxiv.org/pdf/2406.14088 |
| doi.org | T3 | https://doi.org/10.48550/arxiv.2408.16296 | — | HTML_HAS_PDF_LINK | pdf_url=https://arxiv.org/pdf/2408.16296 |
| doi.org | T3 | https://doi.org/10.48550/arxiv.2504.02670 | — | HTML_HAS_PDF_LINK | pdf_url=https://arxiv.org/pdf/2504.02670 |
| doi.org | T3 | https://doi.org/10.5040/9780755623693.ch-006 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9780755623693.ch-015 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9780755623693.part-001 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9780755623693.part-002 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9780755623693.part-003 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.0005 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.ch-005 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.ch-008 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.ch-012 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.ch-020 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.ch-021 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.ch-029 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5040/9798881820794.ch-030 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5167/uzh-45506 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5194/acp-10-4725-2010 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5194/acp-11-375-2011 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5194/acp-6-5067-2006 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5194/egusphere-egu26-15967 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5194/gmd-12-4955-2019 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.52058/2786-6165-2025-12(42)-36-52 | — | HTML_HAS_PDF_LINK | pdf_url=https://perspectives.pp.ua/index.php/vno |
| doi.org | T3 | https://doi.org/10.5281/zenodo.19431649 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5281/zenodo.19431650 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5281/zenodo.19497466 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.52843/cassyni.y7yb6y | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.53971/2718.658x.v15.n24.43445 | — | HTML_HAS_PDF_LINK | pdf_url=https://revistas.unc.edu.ar/index.php/re |
| doi.org | T3 | https://doi.org/10.54014/zr28-cpbp | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.55221/2572-7478.1375 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.55277/researchhub.4t56deyy.1 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.55738/alaic.v21i40.881 | — | HTML_HAS_PDF_LINK | pdf_url=https://revista.pubalaic.org/index.php/a |
| doi.org | T3 | https://doi.org/10.58532/v3biai4p1ch7 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5860/choice.26-4356 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.5860/ital.v44i4.17432 | — | HTML_HAS_PDF_LINK | pdf_url=https://ital.corejournals.org/index.php/ |
| doi.org | T3 | https://doi.org/10.6035/forumrecerca.2019.24 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.61468/jofdl.v21i1.276 | — | HTML_HAS_PDF_LINK | pdf_url=https://jofdl.nz/index.php/JOFDL/article |
| doi.org | T3 | https://doi.org/10.63418/nt41mk64 | — | HTML_HAS_PDF_LINK | pdf_url=https://revistacoletivocineforum.com.br/ |
| doi.org | T3 | https://doi.org/10.70675/f480bd4dz0f08z4e64z9c2fz484276575ac4 | — | HTML_OK |  |
| doi.org | T3 | https://doi.org/10.7287/peerj.preprints.27552 | — | HTML_HAS_PDF_LINK | pdf_url=https://peerj.com/preprints/27552.pdf |
| doi.org | T3 | https://doi.org/10.7312/stim91652-001 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.degruyterbrill.com/document/ |
| doi.org | T3 | https://doi.org/10.7551/mitpress/1006.003.0009 | — | HTTP_403 |  |
| doi.org | T3 | https://doi.org/10.7554/elife.78811 | — | HTML_OK |  |
| elib.uni-stuttgart.de | T4 | https://elib.uni-stuttgart.de/server/api/core/bitstreams/3e0a4123-b020 | — | PDF_OK |  |
| ieeexplore.ieee.org | T4 | https://ieeexplore.ieee.org/abstract/document/10539635/ | — | HTML_OK |  |
| ieeexplore.ieee.org | T4 | https://ieeexplore.ieee.org/abstract/document/10619146/ | — | HTML_OK |  |
| ieeexplore.ieee.org | T4 | https://ieeexplore.ieee.org/abstract/document/9126743/ | — | HTML_OK |  |
| ieeexplore.ieee.org | T4 | https://ieeexplore.ieee.org/abstract/document/9251051/ | — | HTML_OK |  |
| ieeexplore.ieee.org | T4 | https://ieeexplore.ieee.org/abstract/document/9406610/ | — | HTML_OK |  |
| ieeexplore.ieee.org | T4 | https://ieeexplore.ieee.org/abstract/document/9950068/ | — | HTML_OK |  |
| inspirehep.net | T4 | https://inspirehep.net/files/4fb38366dba24567857a866edaf6504a | — | PDF_OK |  |
| jstor.org | T4 | https://www.jstor.org/stable/26812028 | — | HTML_OK |  |
| jstor.org | T4 | https://www.jstor.org/stable/26812317 | — | HTML_OK |  |
| jstor.org | T4 | https://www.jstor.org/stable/26815505 | — | HTML_OK |  |
| jstor.org | T4 | https://www.jstor.org/stable/26815823 | — | HTML_OK |  |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-1-4842-4401-2_10 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-1-4842-5793-7_7 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-3-031-28241-6_7 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-3-031-56060-6_29 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-3-032-12972-7_4 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-3-032-21289-4_33 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-3-032-21321-1_57 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-3-662-05570-0_6 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/chapter/10.1007/978-3-662-56074-7_87 | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/content/pdf/10.1007/978-1-4471-6714-3.pdf | — | HTML_OK |  |
| link.springer.com | T4 | https://link.springer.com/content/pdf/10.1007/978-1-4842-4401-2.pdf | — | HTML_OK |  |
| link.springer.com | T4 | https://link.springer.com/content/pdf/10.1007/978-3-030-25943-3_34.pdf | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/content/pdf/10.1007/978-3-031-56060-6_29.pdf | — | HTML_HAS_PDF_LINK | pdf_url=https://link.springer.com/content/pdf/10 |
| link.springer.com | T4 | https://link.springer.com/content/pdf/10.1007/978-3-319-12000-3.pdf | — | HTML_OK |  |
| link.springer.com | T4 | https://link.springer.com/content/pdf/10.1007/979-8-8688-0069-6.pdf | — | HTML_OK |  |
| mdpi.com | T4 | https://www.mdpi.com/1424-8220/10/12/11259 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/1424-8220/10/12/112 |
| mdpi.com | T4 | https://www.mdpi.com/2313-7673/9/10/594 | — | HTML_HAS_PDF_LINK | pdf_url=https://www.mdpi.com/2313-7673/9/10/594/ |
| muse.jhu.edu | T4 | https://muse.jhu.edu/pub/20/article/197444/summary | — | HTML_OK |  |
| muse.jhu.edu | T4 | https://muse.jhu.edu/pub/20/article/240222/summary | — | HTML_OK |  |
| muse.jhu.edu | T4 | https://muse.jhu.edu/pub/20/article/389563/summary | — | HTML_OK |  |
| muse.jhu.edu | T4 | https://muse.jhu.edu/pub/79/article/693764/summary | — | HTML_OK |  |
| nature.com | T4 | https://www.nature.com/articles/s41586-024-08328-6 | — | HTML_OK |  |
| nature.com | T4 | https://www.nature.com/articles/s41586-024-08449-y | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1031139606 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W108568768 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W125374724 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W127401650 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W135218250 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W146315865 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1491137936 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1491267590 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1492336622 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1509337129 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1512930696 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1513209702 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1513875215 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1539548114 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1546514714 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W155441373 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1561846228 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1562311734 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1567266904 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W157847378 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1583051703 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1585737637 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1586034281 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1590736992 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1654036882 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1678529581 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1680167713 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1769225432 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1791808111 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W181011257 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W181169397 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W188713413 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W192192226 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1944154065 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W196106506 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W1961482515 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W199596423 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W199754645 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W211060801 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2110654099 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W211847521 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2126320627 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2167868137 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2174524719 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2179548826 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2203552747 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2208216474 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2215018963 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2216641999 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2217176459 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2236402289 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2259695429 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2259921548 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2273219947 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2304550456 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W23252248 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2339171114 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W238860993 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W241548074 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2472935185 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2488069739 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W248922549 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W249101252 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2499088509 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2514587947 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2515131953 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2516569829 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2524810257 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2526454192 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W254499196 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2555737872 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W257097882 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W257153631 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2578290449 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2583711937 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W258633232 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2597165374 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2597517053 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2606330043 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2610009655 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2610863486 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2611137021 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2611987247 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2617408051 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W262285765 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2733910099 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2735168483 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2738235914 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2748028560 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2775077584 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2782248565 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2787015666 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2788299508 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2790884903 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2793212898 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2798227087 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2802823396 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2804159452 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2807824556 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2883510698 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2884934054 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2895552733 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2902701004 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2905271929 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2910222397 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2913099421 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2923103442 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2937747161 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2946087732 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2949475438 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2949707494 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2950305569 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2950465679 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2952235855 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2955303407 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2956142570 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2969828688 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2972852102 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2981779961 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2994421956 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2995623960 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W2998017095 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3003434672 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3009418014 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3021117746 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3039854237 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W304111106 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3047630897 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W308878670 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3109022434 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3128731814 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3140407607 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W315628836 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3157489832 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3158119072 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3158302253 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3160539020 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3169206371 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3169640436 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3182801345 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3185368088 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3186345748 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3186628998 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3196676090 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3199002119 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3203668607 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3209014536 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W3217084913 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W325640893 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W329487651 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W339005490 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W350336773 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W382604515 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W4300792089 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W4302990361 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W4391299083 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W4392150037 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W49242403 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W560353855 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W56946216 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W572333959 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W579186030 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W579337233 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W590460742 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W593549549 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W601018461 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W613260912 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W628444394 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W631297601 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W643372212 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W644087883 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7110534603 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7111651098 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7111798728 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7111873083 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7111970428 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7111979094 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7112284008 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7112483058 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7113655565 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7115103540 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7115984906 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7120360085 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7120429629 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7120505710 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7120508044 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7120541820 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7120663966 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7124513424 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7124824398 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7125877136 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7128324140 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7128411582 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7131923859 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132121035 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132171172 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132196952 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132311915 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132326649 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132329945 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132356726 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132362253 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132367289 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132565577 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132877131 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132903460 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132964189 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7132971110 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7133420283 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7134019725 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7134093698 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7134291035 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7134700280 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7137385135 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7139355720 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7139554642 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7140066594 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7140066597 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7140068146 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7140071071 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7140262579 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7140347503 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7140967147 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7143260675 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7143265540 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7143267967 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7145624905 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7152331479 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7154539180 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7154539443 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7154539866 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7154660040 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7154799491 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W7157520790 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W764831308 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W780770231 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W780944978 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W788053552 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W798800632 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W801354797 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W806631164 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W808734770 | — | HTML_OK |  |
| openalex.org | T2 | https://openalex.org/W992009884 | — | HTML_OK |  |
| openreview.net | T1 | https://openreview.net/forum?id=TuFjICawSc | ✓ | PDF_OK |  |
| pmc.ncbi.nlm.nih.gov | T1 | https://pmc.ncbi.nlm.nih.gov/articles/PMC4763690/ | — | HTML_OK |  |
| pmc.ncbi.nlm.nih.gov | T1 | https://pmc.ncbi.nlm.nih.gov/articles/PMC9172927/ | — | HTML_HAS_PDF_LINK | pdf_url=https://pmc.ncbi.nlm.nih.gov/articles/PM |
| researchgate.net | T4 | https://www.researchgate.net/profile/Ibrahim-Al-Azher-2/publication/39 | — | HTTP_403 |  |
| researchgate.net | T4 | https://www.researchgate.net/publication/358741633_Designing_Effective | — | HTML_OK |  |
| researchgate.net | T4 | https://www.researchgate.net/publication/371704865_Temporal-Weighted_B | — | HTML_OK |  |
| researchgate.net | T4 | https://www.researchgate.net/publication/395463262_From_Sparse_to_Dens | — | HTML_OK |  |
| sciencedirect.com | T4 | https://www.sciencedirect.com/science/article/pii/S0012369220304645 | — | HTTP_403 |  |
| sciencedirect.com | T4 | https://www.sciencedirect.com/science/article/pii/S0959652614009536 | — | HTTP_403 |  |
| sciencedirect.com | T4 | https://www.sciencedirect.com/science/article/pii/S2352711025004297 | — | HTTP_403 |  |
| sciencedirect.com | T4 | https://www.sciencedirect.com/science/article/pii/S2666845924002010 | — | HTTP_403 |  |
| scijournals.onlinelibrary.wiley.com | T4 | https://scijournals.onlinelibrary.wiley.com/doi/abs/10.1002/ese3.70091 | — | HTTP_403 |  |
| scribd.com | T4 | https://www.scribd.com/document/238471206/Hobbit-The-J-R-R-Tolkien | — | HTML_OK |  |
| scribd.com | T4 | https://www.scribd.com/document/930453718/asyncio | — | HTML_OK |  |
| scribd.com | T4 | https://www.scribd.com/document/938916312/The-Hobbit-by-John-Ronald-Re | — | HTML_OK |  |
| search.ebscohost.com | T4 | https://search.ebscohost.com/login.aspx?direct=true&profile=ehost&scop | — | HTML_OK |  |
| search.proquest.com | T4 | https://search.proquest.com/openview/57706d46d96261044e6e46b986073f63/ | — | HTML_OK |  |
| search.proquest.com | T4 | https://search.proquest.com/openview/5ac4226472303b00897d954ee318d027/ | — | HTML_OK |  |
| search.proquest.com | T4 | https://search.proquest.com/openview/bac12f2ecbb0f82e9751449bfa2f592a/ | — | HTML_OK |  |
| search.proquest.com | T4 | https://search.proquest.com/openview/f4ad6714141c63ea98715eaf2aefe893/ | — | HTML_OK |  |
| semanticscholar.org | T2 | https://www.semanticscholar.org/paper/Learning-Retrieval-Models-with-S | — | HTML_OK |  |
| spiedigitallibrary.org | T4 | https://www.spiedigitallibrary.org/conference-proceedings-of-spie/1381 | — | HTML_OK |  |
| tandfonline.com | T4 | https://www.tandfonline.com/doi/abs/10.1080/00107514.2019.1667078 | — | HTTP_403 |  |
| thieme-connect.com | T4 | https://www.thieme-connect.com/products/all/doi/10.1055/s-2006-926779 | — | HTML_HAS_PDF_LINK | pdf_url=http://www.thieme-connect.com/products/e |
| thieme-connect.com | T4 | https://www.thieme-connect.com/products/ejournals/html/10.1055/s-0038- | — | HTML_HAS_PDF_LINK | pdf_url=http://www.thieme-connect.com/products/e |
