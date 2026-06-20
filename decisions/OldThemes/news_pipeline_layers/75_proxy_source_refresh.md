# 75 — Proxy source refresh: databay-labs dead, +3 validated sources

Scope: the shared proxy-source loader `src/news/engine/proxy_pool/pool_loaders.py` (feeds BOTH the riding
engine and the theblock proxy_pool engine via `load_backfill_pool()`). Implementation in progress (worker
on `dev`).

## Trigger

During a cooldown A/B run, the pool-load log showed `databay-labs/free-proxy-list/master/http.txt` → 404.
Investigation: the repo was DELETED from GitHub entirely (GitHub GraphQL API: "Could not resolve to a
Repository with the name 'databay-labs/free-proxy-list'") — not renamed (gh-cli `search_repos` found no
successor; all "databay" matches are unrelated projects, e.g. Voyz/databay is a data-integration framework).
It had been contributing 0 proxies while costing retry-backoff on every pool load + every 30-min refresh
(3 dead URLs × exp-backoff retry).

## Existing source nature (context)

The 14-source config is already a MIX of validated + raw: monosans + proxifly publish validated/metadata
lists; roosterkid is a decorated/checked list (latency + country); TheSpeedX is a raw dump. Note: proxifly
IS in the config (`PROXIFLY_URL`, `_fetch_proxifly`, merged with monosans) despite a STALE docstring claiming
"proxifly excluded (rank 15, below cutoff)" — the comment was never updated after proxifly was added.

## Key finding (worker investigation)

`load_backfill_pool()` (the CoinDesk path: `_pool_provider` → `load_backfill_pool`) fetches 13 source-groups:
monosans, roosterkid, databay, TheSpeedX, themiralay, r00tee, iplocate, sunny9577, ALIILAPRO, dpangestuw,
Zaeem20, zloi, hookzof. **proxifly and jetkai are NOT in it** — they have fetchers (`_fetch_proxifly`,
`load_jetkai_proxies`/`JETKAI_SOURCES`) but those are only called from separate functions
(`load_curated_proxies`, `load_jetkai_proxies`) that the backfill path never invokes. So the docstring
"proxifly excluded (rank 15, below cutoff)" was ACCURATE for the backfill pool — proxifly genuinely was not
there. (Opus initially mis-stated "proxifly is already in" from seeing the fetcher in the file; the worker's
source read corrected it.)

## Decision

- Remove databay-labs (dead repo) — URLs + fetcher + docstring mention.
- **Wire the existing validated fetchers proxifly + jetkai INTO `load_backfill_pool`** — near-zero new code
  (fetchers already exist). proxifly (⭐5704, validated/metadata, the biggest source) + jetkai (online-tested,
  "proxies online at the time of testing", updated hourly). Revisits proxifly's deliberate survey-rank-15
  exclusion — justified by the current goal: maximise validated supply against the eligible-pool depletion.
- Fix the stale proxifly docstring → make the source inventory comment reflect reality (the actual backfill set).
- Add three more SOURCE-VALIDATED (pre-filtered) sources, deliberately small for high live-fraction / low churn
  (user: "am besten vorgefiltert ... so klein dass selbst wenn Trash, verwässert den Pool nicht arg"):
  - **prxchk/proxy-list** — validated ("highly anonymous, accuracy"), refreshed EVERY 10 MIN; ~58 http / ~10 socks5.
  - **ShiftyTR/Proxy-List** — updated hourly; ~40 http / ~279 socks5.
  - **vakhov/fresh-proxy-list** — "fresh, working"; ~528 http / ~21 socks5.
  Together ~936 vs ~19,576 currently-eligible → <5% dilution even if all were dead.

### Rejected

- **MuRongPIG/Proxy-Master** (~28k/protocol RAW dump, "maybe the best free proxy list"): rejected — user wants
  pre-filtered, not raw. Its validated `_checked` subset (~158 http / ~39 socks5) is too small to bother.
- **oxylabs/free-proxy-list** (⭐3068): rejected — NO data file; proxies live in a README markdown table,
  US-only, marketing repo. Not machine-readable.

## Rationale

Source-side validation = FREE validation: the maintainer already dropped dead IPs, directly attacking our
dominant failure mode (93% `connect_fail` on dead proxies, per job `20260620T010358Z`) WITHOUT costing us a
CoinDesk regwall-budget request per proxy. This is DISTINCT from the alive-feeder dropped in OT61 (which cost
one CoinDesk request per proxy). Caveat: source validation proves "proxy alive", not "passes CoinDesk's
IP-rate regwall" — but the connect_fail axis is exactly what it reduces, and the regwall axis we handle
ourselves via backoff (OT74).

## IST after change

`load_backfill_pool()` source set after change: monosans, roosterkid, TheSpeedX, themiralay, r00tee,
iplocate, sunny9577, ALIILAPRO, dpangestuw, Zaeem20, zloi-user, hookzof (the surviving 12 of the old 13),
**+ proxifly, + jetkai (wired in), + prxchk, + ShiftyTR, + vakhov** (− databay-labs). The 30-min pool
refresh auto-covers all of these via `_pool_provider()` → `load_backfill_pool()` — no separate wiring. Robust `ip:port` regex parser per source (roosterkid pattern),
404/failure recorded `ok=False` and skipped via `_try_source`.

## Open

- Live-fraction contribution of the three new validated sources after dedup with existing aggregators —
  the next pool-load smoke + job.md `## Pool source breakdown` per-source counts will show it.
