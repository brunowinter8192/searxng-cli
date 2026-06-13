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

## Gotchas

1. **lxml / APScheduler / gunicorn pins all need relaxing on 3.12** — see Dep Compatibility table.
2. **`MAX_FAIL_COUNT=0` is extremely strict** — a proxy that happened to time out on first check is gone immediately. Pool will shrink fast between 5-min replenish cycles.
3. **0 HTTPS proxies on first run** — expected: public free proxies rarely support HTTPS tunneling; qq.com may also block non-CN IPs. HTTPS pool requires a less restrictive check target.
4. **ihuan + zdaye returned 0 proxies** — site timeouts during the run; they will retry on next 5-min fetch cycle.
5. **Region geo lookup** (`api.ip.sb/geoip/`) uses `WebRequest` without explicit proxies — goes through env proxy (fine with mitmproxy, but adds latency per new proxy).
6. **`PROXY_REGION=True` (default)** — geo-lookup fires for every newly added proxy, adding ~2s per proxy to the raw-check pass path.
7. **Docker container name `jhao104-redis`** — if Redis container already exists (stopped), `docker run` will fail. `setup.sh` handles this with `docker start`.

## Next stages (pending separate Go)

- Stage 2: point check targets at theblock.co (change `HTTP_URL` / `HTTPS_URL`)
- Stage 3: custom `curl_cffi` validator for Cloudflare-passing check
- Stage 4: benchmark against monosans machinery in `dev/news_pipeline/theblock/`
