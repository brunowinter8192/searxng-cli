# Sources

**searxng_reference** — Single RAG collection. Search with `rag-cli search_hybrid <query> searxng_reference --top-k N`.

| Source | Type | Pipeline Steps | Status |
|--------|------|---------------|--------|
| searxng_reference | RAG Collection | search01, search02, search03, scrape01, scrape02, scrape03, explore01, g82 | Indexed |
| docs.searxng.org | Web Domain | search01, search02, search03, agent01 | Indexed |
| docs.crawl4ai.com | Web Domain | scrape01, scrape02, scrape03, explore01 | Indexed |
| docs.anthropic.com | Web Domain | agent01 | Indexed |
| playwright.dev | Web Domain | scrape01 | Indexed |
| trafilatura.readthedocs.io | Web Domain | scrape02 | Indexed |
| cookieyes.com | Web Domain | scrape02, scrape03 | Indexed |
| cookiebot.com | Web Domain | scrape03 | Indexed |
| developer.onetrust.com | Web Domain | scrape03 | Indexed |
| sitemaps.org | Web Domain | explore01 | Indexed |
| support.torproject.org | Web Domain | search02 | Indexed |
| github.com | Web Domain | search01, search02, search03, scrape01, scrape02, scrape03, explore01 | Not indexed |
| api.search.brave.com | Web Domain | search01 | Not indexed |
| huggingface.co | Web Domain | agent02 | Not indexed |
| info.arxiv.org | Web Domain | agent02 | Not indexed |
| lobste.rs | Web Domain | search05 | Indexed |
| developers.openalex.org | Web Domain | search05 | Indexed |
| api.stackexchange.com | Web Domain | search05 | Indexed |
| www.crossref.org | Web Domain | search05 | Indexed |
| www.mojeek.com | Web Domain | search05 | Indexed |
| blog.mojeek.com | Web Domain | search05 | Indexed |
| duckduckgo.com (help-pages) | Web Domain | search05 | Indexed |
| scholar.google.com | Web Domain | search05 | Indexed |
| support.google.com (websearch operators) | Web Domain | search05 | Indexed |
| blog.cloudflare.com (markdown-for-agents) | Web Domain | scrape04 | Indexed |
| seirdy.one (search-engines-with-own-indexes) | Web Domain | search05 | Referenced |
| morphllm.com (ai-web-scraping benchmarks) | Web Domain | scrape00 | Referenced |
| chuniversiteit.nl (extraction-comparison) | Web Domain | scrape02 | Referenced |
| vercel.com/docs (independent markdown-edge) | Web Domain | scrape04 | Referenced |

| GitHub Issue #5286 | github.com | Issue | search02_routing | Referenced |
| GitHub Issue #5922 | github.com | Issue | search02_routing | Referenced |
| GitHub PR #5644 | github.com | PR | search01_engines | Referenced |

| github.com/scrapy/scrapy (scrapy/core/downloader/__init__.py) | Repo | pipe_scraper | Referenced |
| daijro/camoufox | Repo | stealth01 | Referenced |
| saifyxpro/HeadlessX | Repo | stealth01 | Referenced |
| nichochar/stealth-browser-mcp | Repo | stealth01 | Referenced |
| Kaliiiiiiiiii-Vinyzu/patchright-python | Repo | stealth01 | Referenced |
| debug-it/brave-captcha-solver | Repo | stealth01 | Referenced |
| nullpt-rs/blog (reversing-botid.mdx) | Web | stealth01 | Referenced |
| FriendlyCaptcha/friendly-challenge | Repo | stealth01 | Referenced |
| BotBrowser CHANGELOG | Repo | stealth01 | Referenced |
| autoscrape-labs/pydoll | Repo | stealth00, stealth01, stealth03 | Referenced |
| opsdisk/yagooglesearch | Repo | stealth05 | Referenced |
| karust/openserp | Repo | stealth05, stealth07 | Referenced |
| 2captcha/2captcha-go | Repo | stealth07 | Referenced |
| github.com/StractOrg/stract | Repo | search05 | Referenced |
| github.com/MarginaliaSearch/MarginaliaSearch | Repo | search05 | Referenced |
| github.com/MarginaliaSearch/docs.marginalia.nu | Repo | search05 | Referenced |
| github.com/cyanheads/hn-mcp-server | Repo | search05 | Referenced |
| github.com/voska/hn-cli | Repo | search05 | Referenced |
| github.com/lucjon/Py-StackExchange | Repo | search05 | Referenced |
| github.com/searxng/searxng | Repo | search05 | Referenced |
| github.com/searxng/searxng (searx/engines/duckduckgo.py) | Repo | search05 | Referenced |
| github.com/searxng/searxng (searx/engines/mojeek.py) | Repo | search05 | Referenced |
| github.com/searxng/searxng (searx/engines/lobsters.py) | Repo | search05 | Referenced |
| github.com/hffmnnj/kagi-skill | Repo | search05 | Referenced |
| github.com/encode/httpx | Repo | search06 | Referenced |
| github.com/lxml/lxml | Repo | search06 | Referenced |

## Pooling-Feature Quellen (g82)

DB-Aligned 2026-05-09 — nur die zwei Quellen, aus denen tatsächlich Inhalt für das Pooling-Feature extrahiert wurde, sind im Index. Alle anderen ursprünglich indexierten Pooling-Papers wurden gelöscht.

| Source | Type | Pipeline Steps | Status |
|--------|------|---------------|--------|
| Croft / Metzler / Strohman 2010 — Search Engines: Information Retrieval in Practice | Book | g82 | Indexed (RAG: searxng_reference, 868 chunks — primary foundation; Source Selection extracted from Kap. 10.5.1) |
| Cormack et al. SIGIR 2009 — Reciprocal Rank Fusion outperforms Condorcet | Paper | g82 | Indexed (RAG: searxng_reference, 7 chunks — Result Fusion foundation, kept for upcoming research phase) |

## Andere Features

| Source | Type | Pipeline Steps | Status |
|--------|------|---------------|--------|
| api.semanticscholar.org / semanticscholar.org/product/api | Web | 10y | Verified (browser-engine landed; API tier 429s without business-email key) |
| jarrodoverson.com / jsoverson.medium.com — Bypassing CAPTCHAs with Headless Chrome (Puppeteer + 2Captcha tutorial) | Web | ciw | Referenced (community knowledge of Scholar anti-bot detection patterns) |
| latenode.com — How Headless Browser Detection Works and How to Bypass It | Web | ciw | Referenced (enumerates navigator.webdriver / TLS fingerprint / canvas / WebGL / font / timing detection vectors) |
| alterlab.io — Why Your Headless Browser Gets Detected (and How to Fix It) | Web | ciw | Referenced (detection signal catalogue) |
| scrape.do — How to Scrape Google Scholar / 5 Working Methods to Bypass Cloudflare | Web | ciw | Referenced (residential proxy + undetected-chromedriver practitioner stack) |
| harzing.com — Publish or Perish Tutorial — Google Scholar CAPTCHAs | Web | ciw | Referenced (HTTP 429 + 24h block, IP-reputation-based anti-bot evidence) |
| scholarly Python package (PyPI + GitHub issues #131 Tor sustainability) | Repo | ciw | Referenced (open-source Scholar scraper, documents Tor exit shrinkage — Scholar specifically hostile to Tor) |
| support.google.com — How to solve unusual traffic problem for Google Scholar (official support thread) | Web | ciw | Referenced ("If Google Scholar works on a new network, it strongly indicates your home IP is the problem" — official IP-flag confirmation) |
| github.com/searxng/searxng (searx/engines/google_scholar.py) | Repo | ciw | Referenced (HTTP architecture reference; CONSENT cookie pattern, lxml `//div[@data-rp]` xpath, /sorry/ redirect detection — basis for dev/scholar_http_probe.py) |
| github.com/searxng/searxng (searx/search/__init__.py) | Repo | ciw | Referenced (multi-engine orchestration via `threading.Thread` confirmed parallel-fanout pattern matches our `asyncio.gather`) |
| github.com/searxng/searxng (issue #3615) | Forum | ciw | Referenced (SearXNG core dev confirms 5% Scholar CAPTCHA rate, no programmatic bypass available) |
| github.com/searxng/searxng (docs/admin/answer-captcha.rst) | Repo | ciw | Referenced (manual SSH-SOCKS-tunnel + browser CAPTCHA-solve workaround — explicit "not a permanent solution") |
| github.com/scholarly-python-package/scholarly (scholarly/_navigator.py) | Repo | ciw | Referenced (Singleton + dual ProxyGenerator pattern; "without CAPTCHAs" claim depends on paid proxy rotation, free path deprecated) |

Consult via RAG search before making assumptions. Pipeline step references match `decisions/` files.
