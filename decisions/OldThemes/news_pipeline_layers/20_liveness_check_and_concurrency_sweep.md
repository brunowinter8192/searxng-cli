# Iteration 20 — Liveness Check + Concurrency Sweep

## Design

**Script:** `dev/news_pipeline/theblock/probe_liveness.py`  
**Check target:** `http://ipv4.icanhazip.com` (HTTP, simple IP-return, no TLS failure modes)  
**Client:** `curl_cffi.AsyncSession` — native libcurl error codes, enables full reason classification  
**Proxy strings:** `http://`, `socks4://`, `socks5h://` (remote DNS for SOCKS5 — avoids local DNS load)  
**Concurrency:** `asyncio.Semaphore(N)`, one shared `AsyncSession`  
**Timeout:** `(connect_s, read_s)` tuple → `CONNECTTIMEOUT_MS` + `TIMEOUT_MS = (connect+read)*1000` (from curl_cffi `utils.py:set_curl_options`)

## System Limits

FD soft: 1,048,576 / hard: unlimited. Ephemeral ports: 49152–65535 (16,384). 14 cores (I/O-bound — irrelevant). Real ceiling: home-router NAT/conntrack (external, unmeasurable) — the sweep finds it empirically.

## Frozen Pool

Created with `--freeze` on 2026-06-11. Fetched from the same 68 sources as OldThemes 19. Written to `frozen_pool/` (gitignored, regenerated on demand):

| Bucket | Unique entries |
|---|---|
| http | 113,443 |
| socks4 | 94,453 |
| socks5 | 112,827 |
| **total** | **320,723** |

Fixed sample: `random.Random(42).sample(all_entries, 20_000)` — deterministic across all sweep runs.

## Dead Reason Classification

| Bucket | Exception / Code | Discriminator |
|---|---|---|
| `connect_timeout` | `Timeout` | elapsed ≤ connect_s + 0.5 → elapsed-primary; fallback: "Connection timed out" in msg |
| `read_timeout` | `Timeout` | elapsed ≥ total_s - 0.5 → elapsed-primary; fallback: "Operation timed out" in msg |
| `connect_timeout`/`read_timeout` → `unknown` | `Timeout` | neither elapsed nor text matched (libcurl version drift signal) |
| `resolve_error` | `CurlECode.COULDNT_RESOLVE_PROXY/HOST` (5, 6) | proxy hostname unresolvable |
| `proxy_handshake_error` | `ProxyError` / `GOT_NOTHING` (52) / `WEIRD_SERVER_REPLY` (8) | SOCKS/CONNECT negotiation failure; protocol-mislabelled proxies land here |
| `connection_refused` | `CurlConnectionError` (code 7) | TCP to proxy refused / unreachable |
| `tls_error` | `SSLError` (codes 35, 58–60, 80–83, …) | TLS handshake failure |
| `http_non200` | HTTP resp ≠ 200 | proxy returned error page |
| `bad_body` | HTTP 200, body not IPv4 | proxy returned garbage or modified response |
| `unknown` | anything else | logged to `probe_liveness_logs/unknown_errors_<UTC>.log` |

## Sweep Results

**PARTIAL — sweep still running at time of SUCCESSOR-HANDOFF.**

Concurrency sweep: 20k fixed sample, timeout=5s/5s.

| Concurrency | Wall-clock | Throughput | Alive | Alive% | Dead reason mix | Notes |
|---|---|---|---|---|---|---|
| 512 | TBD | TBD | TBD | ~10.9% (partial) | TBD | Run started, at 10k/20k at handoff |
| 1000 | — | — | — | — | — | Not started |
| 2000 | — | — | — | — | — | Not started |
| 3000 | — | — | — | — | — | Not started |

Partial alive rate at 10k/20k during 512 run: 1088/10000 = 10.9%.

*Update this table after successor completes the sweep.*

## Concurrency Recommendation

PENDING — fill after 4-run sweep is complete and reason-mix shift is observed.

## Raw Data Locations

- `/tmp/sweep_512.txt` — stdout of concurrency=512 run (may still be running)
- `dev/news_pipeline/theblock/probe_liveness_logs/sweep_log.md` — structured entries (written when each run completes)
