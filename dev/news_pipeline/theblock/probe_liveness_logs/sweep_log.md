---
## 2026-06-11T20:10:28Z | sample | n=20,000 | concurrency=512 | timeout=5.0s/5.0s

| Wall-clock | Throughput | Alive | Alive% | Dead |
|---|---|---|---|---|
| 456.9s | 44/s | 781 | 3.9% | 19,219 |

### Dead Reason Histogram

| Reason | Count | % of dead |
|---|---|---|
| connect_timeout | 357 | 1.9% |
| read_timeout | 16 | 0.1% |
| hard_timeout | 16,198 | 84.3% |
| connection_refused | 812 | 4.2% |
| proxy_handshake_error | 1,761 | 9.2% |
| resolve_error | 0 | 0.0% |
| tls_error | 0 | 0.0% |
| http_non200 | 69 | 0.4% |
| bad_body | 2 | 0.0% |
| unknown | 4 | 0.0% |

