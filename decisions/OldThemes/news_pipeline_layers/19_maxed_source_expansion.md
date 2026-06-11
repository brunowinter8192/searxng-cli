# Iteration 19 — 68-Source Pool Expansion

## What We Did

Assembled the maxed public-list source set (68 URLs) and measured the raw proxy pool available before any liveness filter. This was a pure scrape/count probe — no proxy was contacted.

**Dev script:** `dev/news_pipeline/theblock/probe_pool_size.py`  
**Run report:** `dev/news_pipeline/theblock/probe_pool_size_reports/pool_size_20260611T171324Z.md`  
**Run:** 2026-06-11T17:13:24Z | wall-clock: 1.7s | all 68 sources returned HTTP 200

## Source Set (68 URLs)

Three protocol buckets: 29 HTTP/HTTPS sources + 19 SOCKS4 + 20 SOCKS5.

Two mixed-protocol aggregate lists assigned to the HTTP bucket (protocol-unknown entries):
- `themiralay/Proxy-List-World/master/data.txt`
- `clarketm/proxy-list/master/proxy-list-raw.txt`

## Measured Pool Size

| Metric | Count |
|---|---|
| Total raw (all sources, incl. cross-source duplicates) | **422,873** |
| Global unique host:port | **119,413** |
| Sum of per-bucket uniques (http+socks4+socks5) | **320,963** |
| Cross-protocol bucket overlap | **201,550** |

Cross-bucket overlap = 201,550 means the same host:port appears in multiple protocol buckets in 63% of per-bucket unique entries. Sources like MuRongPIG/Proxy-Master list the same IPs across HTTP, SOCKS4, and SOCKS5 files.

### Per-Protocol Breakdown

| Bucket | Sources | Raw | Unique |
|---|---|---|---|
| http | 29 | 164,681 | 114,109 |
| socks4 | 19 | 119,102 | 94,347 |
| socks5 | 20 | 139,090 | 112,507 |

### Source Dominance

MuRongPIG/Proxy-Master dominates: 101,620 HTTP + 89,709 SOCKS4 + 100,664 SOCKS5 = **291,993 raw** (69% of total raw). The Proxy-Master list is itself an aggregator — its high count partially explains the large cross-bucket overlap.

Notable zero-yield sources (HTTP 200, 0 valid entries): `zloi-user/hideip.me` (http, https, socks4, socks5 files all returned 0 parseable lines).

Low-yield: monosans static GitHub files (http: 76, socks4: 1, socks5: 4 = 81 total). The old baseline of ~17,202 came from the monosans Docker scraper-checker running dynamically, not from these static pre-committed files.

## Baseline Comparison

| | Raw | Unique |
|---|---|---|
| OldThemes 16 (monosans single-source, Docker scraper) | ~17,202 | not measured |
| This run (68 sources, static fetch) | 422,873 | 119,413 |
| Expansion | **24.6×** raw | — |

Global unique (119,413) is **6.9×** the old raw baseline (which was itself un-deduped).

## Dead Sources

None — 68/68 HTTP 200, all yielded parseable content or zero lines.

## Parse Logic

Line formats handled: bare `host:port`, `proto://host:port`, `proto://user:pass@host:port`. Regex: `^([a-zA-Z0-9.\-]+):(\d{1,5})$` after stripping protocol and auth prefixes. Port validated 1–65535. Blank lines, comment lines (`#`), HTML/markdown silently skipped.

## Next Step

This raw count (119,413 global unique) is the input to the liveness filter. The curl_cffi-chrome pass rate was measured at 18.8% of a neutral pool (OldThemes 17). Projected CF-passing pool: ~22,000 proxies if the rate holds at this scale.
