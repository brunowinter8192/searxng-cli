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

---
## 2026-06-11T20:19:21Z | sample | n=20,000 | concurrency=1000 | timeout=5.0s/5.0s

| Wall-clock | Throughput | Alive | Alive% | Dead |
|---|---|---|---|---|
| 240.1s | 83/s | 303 | 1.5% | 19,697 |

### Dead Reason Histogram

| Reason | Count | % of dead |
|---|---|---|
| connect_timeout | 174 | 0.9% |
| read_timeout | 23 | 0.1% |
| hard_timeout | 18,451 | 93.7% |
| connection_refused | 344 | 1.7% |
| proxy_handshake_error | 674 | 3.4% |
| resolve_error | 0 | 0.0% |
| tls_error | 0 | 0.0% |
| http_non200 | 29 | 0.1% |
| bad_body | 0 | 0.0% |
| unknown | 2 | 0.0% |

---
## 2026-06-11T20:23:51Z | sample | n=20,000 | concurrency=2000 | timeout=5.0s/5.0s

| Wall-clock | Throughput | Alive | Alive% | Dead |
|---|---|---|---|---|
| 120.1s | 166/s | 125 | 0.6% | 19,875 |

### Dead Reason Histogram

| Reason | Count | % of dead |
|---|---|---|
| connect_timeout | 86 | 0.4% |
| read_timeout | 18 | 0.1% |
| hard_timeout | 19,349 | 97.4% |
| connection_refused | 153 | 0.8% |
| proxy_handshake_error | 261 | 1.3% |
| resolve_error | 0 | 0.0% |
| tls_error | 0 | 0.0% |
| http_non200 | 7 | 0.0% |
| bad_body | 0 | 0.0% |
| unknown | 1 | 0.0% |

---
## 2026-06-11T20:26:17Z | sample | n=20,000 | concurrency=3000 | timeout=5.0s/5.0s

| Wall-clock | Throughput | Alive | Alive% | Dead |
|---|---|---|---|---|
| 84.1s | 238/s | 60 | 0.3% | 19,940 |

### Dead Reason Histogram

| Reason | Count | % of dead |
|---|---|---|
| connect_timeout | 56 | 0.3% |
| read_timeout | 17 | 0.1% |
| hard_timeout | 19,601 | 98.3% |
| connection_refused | 94 | 0.5% |
| proxy_handshake_error | 158 | 0.8% |
| resolve_error | 0 | 0.0% |
| tls_error | 0 | 0.0% |
| http_non200 | 12 | 0.1% |
| bad_body | 1 | 0.0% |
| unknown | 1 | 0.0% |

