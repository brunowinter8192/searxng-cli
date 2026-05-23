# scrape04 — Cloudflare/Vercel Markdown Fast-Path

## Status Quo (IST)

`src/scraper/scrape_url.py` and `src/scraper/scrape_url_raw.py` execute an HTTP-only fast-path BEFORE invoking Crawl4AI's browser stack. Implementation: `fetch_markdown_fastpath()` in `scrape_url.py` (FUNCTIONS section), imported into `scrape_url_raw.py` via the existing cross-module import. Inserted in both workflows immediately after the entry-point `logger.info("Scraping…")` line and BEFORE Crawl4AI's `DefaultMarkdownGenerator` setup.

**Mechanism:**
- `httpx.AsyncClient(follow_redirects=True, timeout=MD_FASTPATH_TIMEOUT)` GET with header `Accept: text/markdown, text/html`
- ALL of: HTTP 200 + `Content-Type` contains `text/markdown` + body length ≥ `MD_FASTPATH_MIN_BYTES` → return body
- Otherwise (any miss, any exception) → return `None` → workflow falls through to existing Crawl4AI two-phase scrape unchanged

**Constants:**
- `MD_FASTPATH_MIN_BYTES = 200` — body-length threshold; rejects redirect-stub responses
- `MD_FASTPATH_TIMEOUT = 5.0` — generous for cold-edge CDN routing, tight enough to not delay Crawl4AI fallback

**Logging:**
- info: hit (`Markdown fast-path hit: <url> (<N> chars)`)
- debug: miss (sub-threshold / non-200 / wrong content-type) and network errors

**Routing interaction:** `cli.py` calls `check_plugin_routed()` before either workflow function — fast-path therefore runs only on already-routed-clean URLs. No interaction.

**Caching interaction:** Both scraper modules use `CacheMode.BYPASS` for Crawl4AI; no application-level cache. Fast-path is the first decision point in the chain.

## Evidenz

**Cloudflare announcement** — blog.cloudflare.com/markdown-for-agents/ (2026-02-12). Cloudflare CDN edge supports `Accept: text/markdown` content-negotiation for opted-in zones. Response includes `Content-Type: text/markdown; charset=utf-8`, an `x-markdown-tokens` integer header with the token count, and a `Content-Signal: ai-train=yes, search=yes, ai-input=yes` header. Beta for Pro/Business/Enterprise/SSL-for-SaaS plans; rollout began Feb 2026. Cited 80% token reduction on a sample blog post. Article notes Claude Code and OpenCode already send the header in production.

**Adoption probe** — `dev/scrape_pipeline/06_cloudflare_md_adoption.py`, run 2026-05-07 against 29-URL curated set across three categories:

| Category | URLs | MD-served | Notes |
|---|---|---|---|
| Cloudflare-owned (positive control) | 5 | 5/5 | 100% — expected |
| Likely CF-fronted (typical scrape targets: dev.to, npm, Discord, Shopify, HuggingFace, Vercel, Tailwind, Supabase, Fly.io, Linear, Hashnode, Deno, Astro, Pydantic, PostHog, Render, Medium, Anthropic) | 19 | 2/19 | docs.anthropic.com (12-byte stub anomaly) + vercel.com/docs (Vercel's own edge implementation, no cf-ray) |
| Non-CF negative controls (Wikipedia, Python.org, MDN, arXiv, GitHub-raw) | 5 | 0/5 | as expected |

Mean byte-reduction on positives: 92.3%, median 97.0%, range 71.2%–98.5%. Aggregate adoption rate among non-Cloudflare-owned CF-customers in May 2026 (3 months after Beta launch): ≈0%.

**Vercel finding (independent multi-vendor pattern):** vercel.com/docs returns `Content-Type: text/markdown` WITHOUT the `cf-ray` header — Vercel implements the same `Accept: text/markdown` convention on their own edge infrastructure independently of Cloudflare. The fast-path is therefore not Cloudflare-specific; it reflects an emerging multi-vendor convention.

**Live verification (post-merge, 2026-05-07):** `searxng-cli scrape_url https://blog.cloudflare.com/markdown-for-agents/` returned in 1.06s with clean markdown frontmatter and body. Typical Crawl4AI baseline path: ~5–15s. Fast-path verified working in production.

## Recommendation (SOLL)

Keep current implementation (no change needed). The probe-on-every-scrape strategy is correct given:
- Failure-mode is graceful (HTML fallback to existing path) and adds at most ~5s before falling back
- Adoption is currently low (~24% of probe set, but mostly Cloudflare-owned) but growing — the fast-path catches new opt-ins automatically without code changes
- The win-when-it-works is large: 97% median byte reduction, ~5x faster than browser path
- Multi-vendor extension (Vercel) confirms the pattern isn't going away

## Offene Fragen

- Does `x-markdown-tokens` count match what our downstream cleanup + index pipeline chunking would compute? Could be used to influence chunk size dynamically when present.
- Adoption tracking: re-run the probe quarterly. Track whether the May 2026 baseline (~24% of probe set) grows. The probe script is the persistent measurement artifact.
- Other multi-vendor edges that might already implement this pattern (Fastly, AWS CloudFront)? Out of scope for now — let the probe surface them when they appear.

## Quellen

- blog.cloudflare.com/markdown-for-agents/ (Cloudflare announcement, 2026-02-12)
- developers.cloudflare.com/fundamentals/reference/markdown-for-agents/ (config docs)
- vercel.com/docs (independent multi-vendor implementation, observed via probe; not formally documented by Vercel as of 2026-05-07)
- dev/scrape_pipeline/06_cloudflare_md_adoption.py (our adoption probe)
- dev/scrape_pipeline/06_reports/cf_md_adoption_20260507_*.md (run snapshots)
