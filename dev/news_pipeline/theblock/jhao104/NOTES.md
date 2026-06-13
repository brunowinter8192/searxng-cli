# jhao104/proxy_pool — Stage 1 Notes

Self-maintaining proxy pool: scrape public sources → Redis → validate / evict → Flask API.
Stage 1 runs against the DEFAULT neutral targets (httpbin.org HTTP, www.qq.com HTTPS).
Upstream: https://github.com/jhao104/proxy_pool (depth-1 clone, gitignored).

## Setup

```
dev/news_pipeline/theblock/jhao104/
├── setup.sh       # one-shot bring-up (clone + deps + redis + start)
├── NOTES.md       # this file
├── upstream/      # gitignored — clone lives here
└── venv/          # gitignored — Python 3.12 venv
```

Run: `bash dev/news_pipeline/theblock/jhao104/setup.sh`

## Python / Dep Compatibility (Python 3.12)

jhao104 targets Python 3.8–3.11. Python 3.12 requires three pin relaxations:

| Dep | Pinned | Used | Reason |
|---|---|---|---|
| `lxml` | `==4.9.2` | `>=4.9.4` | 4.9.2 source-build fails: PyLong `ob_digit` removed from CPython 3.12 internal ABI |
| `APScheduler` | `==3.10.0` | `>=3.11.0` | 3.10.0 `__init__` imports `pkg_resources` which is not present in 3.12 venv |
| `gunicorn` | `==19.9.0` | `>=21.2.0` | 19.9.0 bundles its own `six.moves`; broken in 3.12 |

No functional behavior changes — API surface used by jhao104 is identical across these version ranges.

## Redis

Docker: `redis:alpine --requirepass pwdstring` on `127.0.0.1:6379`. Matches `setting.py` default `DB_CONN` — no config change needed.

```bash
docker run -d --name jhao104-redis -p 6379:6379 redis:alpine redis-server --requirepass pwdstring
```

## Env-Proxy Handling

This machine routes outbound through mitmproxy (`HTTPS_PROXY=http://localhost:8082`).

**Empirical finding (verified via `Session.merge_environment_settings()`):**

| Code path | Explicit `proxies=` | Effect of env `HTTPS_PROXY` |
|---|---|---|
| `httpTimeOutValidator` / `httpsTimeOutValidator` | YES — `{"http": "http://<proxy>", "https": "http://<proxy>"}` | **Overridden — no interference.** Traffic goes through the proxy under test, not mitmproxy. |
| `WebRequest.get()` (fetchers, region API) | NO | env proxy applied → fetcher HTTPS requests go through mitmproxy |

**Conclusion:** env `HTTPS_PROXY` does NOT corrupt validation results. Validators use explicit `proxies=` which overrides env in `requests`.

**Chosen approach:** strip `HTTP_PROXY='' HTTPS_PROXY=''` from the jhao104 process env anyway, so fetchers go direct (removes mitmproxy dependency; cleaner isolation).

## Architecture (confirmed)

| Component | Location | Behavior |
|---|---|---|
| Scheduler | `helper/scheduler.py` | Fetch every **5 min**, check every **2 min** |
| Check threads | `helper/check.py:Checker()` | **20 threads hardcoded** (`for index in range(20)`) |
| HTTP validator | `helper/validator.py:httpTimeOutValidator` | `requests.head(HTTP_URL)` via proxy; drives pass/fail |
| HTTPS validator | `helper/validator.py:httpsTimeOutValidator` | Sets `proxy.https=True` only — does not evict |
| Eviction gate | `helper/check.py:_ThreadChecker.__ifUse` | `fail_count > MAX_FAIL_COUNT` → delete |
| Redis store | `setting.py:TABLE_NAME='use_proxy'` | HASH keyed by `ip:port` |

**Aggressive eviction:** `MAX_FAIL_COUNT=0` (default) → first check failure = immediate evict.

## Stage 1 Baseline Data (2026-06-13)

Run against neutral targets: `HTTP_URL=http://httpbin.org`, `HTTPS_URL=https://www.qq.com`.

### Fetch cycle (first run, startup)

14 sources active: daili66, docip, freevpnnode, geonode, goodips, ihuan, ip3366, ip89, kuaidaili, kxdaili, proxifly, roundproxies, scdn, zdaye.

| Source | Fetched |
|---|---|
| scdn | 100 |
| geonode | 100 |
| daili66 | 60 |
| roundproxies | 50 |
| docip | 50 |
| ip89 | 40 |
| ip3366 | 30 |
| freevpnnode | 30 |
| kuaidaili | 24 |
| proxifly | 21 |
| kxdaili | 20 |
| goodips | 15 |
| ihuan | 0 (site timeout) |
| zdaye | 0 (site unreachable) |
| **Total** | **540** |

### Check cycle (first run, ~2 min after fetch)

20 threads; `VERIFY_TIMEOUT=10s`; target `http://httpbin.org`.

| Metric | Value |
|---|---|
| Proxies checked | 527 (13 rejected by `formatValidator` pre-check) |
| Passed HTTP check | **117** |
| Failed HTTP check | 410 |
| Pass rate | 22.2% |
| HTTPS (qq.com) | **0** — none of the 117 HTTP proxies tunneled HTTPS to qq.com |

### API sample (`/count`, `/get`, `/all[0:3]`)

```
GET /count/
{"count":117,"http_type":{"http":117},"source":{"daili66":40,"docip":8,"geonode":2,"goodips":11,"ip89":2,"kxdaili":1,"proxifly":9,"roundproxies":1,"scdn":53}}

GET /get/
{"anonymous":"","check_count":1,"fail_count":0,"https":false,"last_status":true,
 "last_time":"2026-06-13 18:50:33","proxy":"16.162.88.123:8080","region":"HK","source":"scdn"}

GET /get/?type=https
{"code":0,"src":"no proxy"}
```

### Env-proxy interference assessment

**Case (c): pool filled normally.** 117 proxies in pool after first cycle. The env `HTTPS_PROXY` did NOT corrupt validation — validators use explicit `proxies=` (overrides env). Fetchers ran with env stripped (`HTTP_PROXY='' HTTPS_PROXY=''`).

## Stage 2 — theblock CF-pass validator (2026-06-13)

### Validator overlay

`patches/helper/validator.py` replaces `upstream/helper/validator.py` after clone (applied by `setup.sh` step 2).

Changes from stock:
| Function | Change | Reason |
|---|---|---|
| `httpTimeOutValidator` | Decorator removed | Not in `http_validator`; theblockValidator is sole gate |
| `customValidatorExample` | Decorator removed | Not in `http_validator` |
| `httpsTimeOutValidator` | Decorator removed | `https_validator` empty → all http-passers get `https=True` (accurate: they tunnelled HTTPS to theblock); no wasted qq.com HEAD per cycle |
| `theblockValidator` | `@addHttpValidator` | curl_cffi `impersonate="chrome"` → `sitemap_tbco_index.xml`; `http://` scheme for both proxy keys; 15s timeout; XML marker check |

`MAX_FAIL_COUNT=2` passed as env var at scheduler startup (ConfigHandler reads env first; overrides setting.py default of 0). Tolerates transient check failures before eviction.

### Stage 2 baseline data (2026-06-13)

**Cycle 1 (startup raw-check):**

| Metric | Value |
|---|---|
| Fetched | 538 |
| Pre-validated (formatValidator rejected) | 12 |
| Checked (theblock CF gate) | 526 |
| Passed | **1** |
| Failed | 525 |
| CF-pass rate | **0.19%** |
| Cycle time (raw-check) | 3m 17s |

Passing proxy: `103.24.214.190:8082` — source: geonode, region: ID (Indonesia), `https=True` (correct: tunnelled HTTPS to theblock).

**Cycle 2 (scheduled, +~5min — pool < poolSizeMin=20 → replenish triggered first):**

| Metric | Value |
|---|---|
| Fetched (cycle 2) | ~1016 |
| Checked (raw) | 651 |
| Passed | 0 |
| Use-check on surviving proxy | pass (still alive) |
| Pool after cycle 2 | **1** |

**Per-source breakdown (combined cycles):** geonode: 1 pass, all other sources: 0.

**Pool sustainability:** 1 proxy stable across 2 cycles. USE-check passed on the survivor → eviction counter reset. With MAX_FAIL_COUNT=2 it would tolerate 2 consecutive use-check failures before deletion.

**CF-pass rate context:** 0.19% vs OldThemes 17 discriminator result of 18.8% on a purposefully-selected fresh pool. Free proxy pool CF pass rates are highly variable by source composition and timing. The jhao104 source set skews heavily toward CN/generic IPs with low CF reputation.

## Gotchas

1. **lxml / APScheduler / gunicorn pins all need relaxing on 3.12** — see Dep Compatibility table.
2. **`MAX_FAIL_COUNT=0` default is extremely strict** — Stage 2 sets it to 2 via env var; tolerates transient failures.
3. **https_validator empty → all http-passers get `https=True`** — accurate for theblock gate (they did tunnel HTTPS), but means the flag is no longer a HTTPS-capable indicator in the traditional sense.
4. **ihuan + zdaye returned 0 proxies** — site timeouts during the run; they will retry on next 5-min fetch cycle.
5. **Region geo lookup** (`api.ip.sb/geoip/`) uses `WebRequest` without explicit proxies — goes through env proxy (fine with mitmproxy, but adds latency per new proxy).
6. **`PROXY_REGION=True` (default)** — geo-lookup fires for every newly added proxy, adding ~2s per proxy to the raw-check pass path.
7. **Docker container name `jhao104-redis`** — if Redis container already exists (stopped), `docker run` will fail. `setup.sh` handles this with `docker start`.
8. **Cycle time dominated by timeout, not network** — with 15s timeout and 20 threads, 526 proxies took 3m17s. Most proxies fail fast (connect refused/timeout), so practical rate is ~2.7 proxies/thread/min rather than the theoretical 1/15s minimum.

## Next stages (pending separate Go)

- Stage 3: recently-evicted dedup patch (prevent re-checking proxies evicted this cycle)
- Stage 4: benchmark against monosans machinery in `dev/news_pipeline/theblock/`
