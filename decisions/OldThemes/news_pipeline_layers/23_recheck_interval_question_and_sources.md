# 23 — Re-Check Interval: The Question + Where to Source It

**Date:** 2026-06-12
**State:** Open question. Research is the FIRST task next session (external sources first, then refine with our own log). Nothing measured yet.

## The question

After a `probe_liveness --source monosans` batch, the whole monosans pool (~103) is grazed in one go (concurrency 128 > pool size). Re-running immediately re-checks the same proxies for nothing. The cycle only becomes meaningful again once enough time has passed that a proxy's status might have CHANGED. So the governing parameter is:

> **Given a proxy that is currently unavailable, after how long is it worth re-checking?**

This is the crux of the whole batching/trying approach — it sets the cycle cadence.

## Two cases — same handling, DIFFERENT recovery clocks

The user framed dead and burned as "the same case". Operationally yes (don't use, re-check later), but the recovery MECHANISM — and therefore the interval AND the source — differ:

| Case | What it is | Recovery governed by |
|---|---|---|
| **Dead** | host offline / unreachable (timeout, refused) | free-proxy churn / host lifetime |
| **CF-burned** | host ALIVE (passes neutral check) but Cloudflare 403/429'd the IP | CF rate-limit / IP-reputation cooldown |

A CF-burned proxy is NOT dead — it still answers the neutral check. Conflating them means applying one re-check threshold to two different clocks.

## Role of the log (already built)

`logs/proxy_status_log.json` records `last_seen` + `last_status` per proxy. That IS the empirical instrument for the re-check interval: once it has runs across hours, we can ask "which proxies last failed > N ago" and tune N against observed recovery. External defaults SEED the threshold; the log TUNES it. The pain is that measuring from scratch is slow — hence: borrow community defaults first.

NOTE: the current log only knows neutral alive/dead (from `probe_liveness`). CF-burn is a later stage not yet logged. When CF-stage logging is added, "CF-blocked" should be a THIRD outcome distinct from alive/dead — precisely because its re-check clock differs. (This does not contradict the "don't store the liveness failure reason" rule — that concerned the dead-host buckets, which genuinely don't matter.)

## Where to source it (research targets for next session)

### Strand A — "dead proxy, when to re-check" (free-proxy churn)
- **Mature proxy-pool projects on GitHub** — e.g. `jhao104/proxy_pool` and peers implement scoring + recheck schedulers. Their defaults (recheck interval, fail-count-to-drop) are community-tested values to borrow. Read the scheduler code. → `gh-cli`.
- **monosans/proxy-scraper-checker itself** — rechecks HOURLY, publishes only currently-alive. The hourly cadence is a scale-tested default in its own right.
- **Academic free-proxy measurement studies** — proxy uptime/churn distributions. → arxiv.

### Strand B — "CF-burned proxy, when usable again" (CF cooldown)
- **Cloudflare rate-limiting docs** — documented block/counting windows + durations.
- **Web-scraping vendor engineering blogs** (ScrapeOps, ZenRows, Scrapfly) — empirical CF-ban-duration findings from scale.
- **r/webscraping** — practitioner reports on real CF cooldowns. → reddit-cli.
- **Our own OldThemes 15** — `probe_discovery` observed 429 persisting >5 min; the "1–2h recovery" there was an unmeasured guess.

## Open questions
- Dead-proxy re-check interval (Strand A) — borrow a default, then tune via the log.
- CF-burn cooldown (Strand B) — borrow a default, then measure directly (we burn proxies anyway in the CF stage).
- Should the log distinguish neutral-dead vs CF-blocked once the CF stage is wired? (Leaning yes — different recovery clocks.)
