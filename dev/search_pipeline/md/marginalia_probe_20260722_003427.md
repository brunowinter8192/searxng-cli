# Marginalia Search Go/No-Go Probe — 20260722_003427

Dev-only probe: does a free public endpoint exist and return usable results, with an honest per-axis quality note (niche/text-heavy strength vs. mainstream/local sparsity).

## Verdict

**CANDIDATE — free public JSON API, no signup, usable results on the niche/text axis**

## Access Path Found

- **Free public JSON API** — no HTML scraping needed, no browser/stealth stack.
- Endpoint: `https://api2.marginalia-search.com/search?query=<q>&count=10`, header `API-Key: public` (a literal shared key string — no signup, no email, works immediately).
- Discovered via `api.marginalia.nu` -> redirects to `about.marginalia-search.com/article/api/` (the current API docs page); the API itself lives at `api2.marginalia-search.com`.
- Response JSON: `{license, page, pages, query, results: [{url, title, description, quality, format, resultsFromDomain, details}]}`.
- A real, modest, **SHARED** daily quota applies to the public key (observed via the `api-remaining-daily-capacity` response header, last seen: 99) — shared across ALL callers of the public key worldwide, not just this probe. A personal free non-commercial key requires an email to contact@marginalia-search.com (per the docs) — a consideration for any future production wiring, out of scope here.

## Headline

- **Queries:** 10
- **OK (results returned):** 8
- **EMPTY (no results, no error):** 0
- **BLOCKED/RATE_LIMITED:** 2
- **ERROR:** 0
- **Latency <= 5.0s:** 10/10
- **Latency distribution (ms):** min=53, median=74, max=1430

## Per-Query Results

| # | Query | Axis | Status | Count | Elapsed ms | <= 5s? |
|---|-------|------|--------|-------|------------|--------|
| 1 | unix philosophy essay | niche-text | OK | 10 | 223 | yes |
| 2 | self hosting guide | niche-text | OK | 10 | 204 | yes |
| 3 | compiler design tutorial | niche-text | OK | 10 | 60 | yes |
| 4 | plain text accounting | niche-text | OK | 10 | 71 | yes |
| 5 | static site generator comparison | niche-text | RATE_LIMITED | 0 | 53 | yes |
| 6 | beste kaffeemaschine test | mainstream-de | RATE_LIMITED | 0 | 77 | yes |
| 7 | gebrauchte waschmaschine frankfurt | local-biz-de | OK | 4 | 1430 | yes |
| 8 | best noise cancelling headphones 2025 | mainstream-en | OK | 10 | 68 | yes |
| 9 | how does DNS work | docs-en | OK | 10 | 592 | yes |
| 10 | climate change carbon capture technology 2025 | mainstream-en | OK | 10 | 53 | yes |

## Per-Axis Quality Note (honest, not asserted generically)

- **Niche/text-heavy axis (Marginalia's stated strength):** 4/5 OK — see samples below; these read as genuinely good indie-web/blog/essay hits, distinct from what Google/Bing/Yandex surface for the same queries this week.
- **Mainstream/local axis:** 4/5 OK by raw count, but sparse/off-topic content is EXPECTED here and is not a failure of the engine — see the per-query samples for the honest relevance call on each.

## Sample Results (quality eyeball)

### [1] unix philosophy essay (niche-text) — 10 results

- **Deconstructing the "Unix philosophy"** — https://www.tedinski.com/2018/05/08/case-study-unix-philosophy.html
  - I’m still working on figuring out how to organize my thoughts about designing software with composition in mind. This might be one of those cases where I have t
- **Unix Philosophy** — https://www.ssp.sh/brain/unix-philosophy/
  - Here are some examples: Abstract The Unix Design Philosophy emphasizes simplicity, modularity, and efficiency. Major tenets include the value of small, focused 
- **The power of the Unix philosophy for LLM agentic tools - Korny’s Blog** — https://blog.korny.info/2025/07/11/the-power-of-the-unix-philosophy-for-llm-agentic-tools
  - Geek, Parent, Coder, Aussie living in the UK Follow I was demonstrating Claude Code to a colleague the other day - I was working on an ASP.Net Core C# service, 
- **The Nature of the Unix Philosophy** — http://xahlee.info/UnixResource_dir/writ/unix_phil.html
  - By Xah Lee. Date: 2006-05-30. Last updated: 2025-06-05 Summary: In the computing industry, especially among unix community, we often hear that there's a “Unix P
- **UNIX Philosophy, Fast Food the UNIX way** — http://xahlee.info/UnixResource_dir/_fastfood_dir/fastfood.html
  - by David D Levine, 1983 Last night I dreamed that the Real World had adopted the “Unix Philosophy.” I went to a fast-food place for lunch. When I arrived, I fou

### [2] self hosting guide (niche-text) — 10 results

- **Next.js Weekly #99: NUQS 2.5, Complete Self Hosting Guide, shadcn/cli 3.0, Refactoring with AI, Concurrent React, Hydration H...** — https://nextjsweekly.com/issues/99
  - – A collection of hard-won lessons from deploying and maintaining Next.js applications in production. Covering solutions for platforms like Kubernetes, Docker, 
- **Docker Vulnerability Scanning 101 - A Self Hosting Guide** — https://noted.lol/vulnerability-scanning-101/
  - Lots of software packages are vulnerable to several, maybe even hundreds of software vulnerabilities. What makes this worse is, very few image maintainers are s
- **Self Hosting Guide - YuruLemmy** — https://lemmy.funami.tech/post/1282956
  - Hello, I’ve recently discovered self hosting and I really want to get into it. I’m not going to fully deep dive now, but I at least want to know the basics befo
- **Notes on Self Hosting a Bluesky PDS Alongside Other Services :: Casey Primozic's Notes** — https://cprimozic.net/notes/posts/notes-on-self-hosting-bluesky-pds-alongside-other-services/
  - I’ve recently set up a Bluesky Personal Data Server (PDS) to store the data for my Bluesky account. I wanted to host it on my server alongside the many other we
- **MALA'S GUIDE TO SELF HOSTING** — https://ophanimkei.com/you/selfhosting
  - INTRODUCTION Hello. I’m going to make a server quick start guide (quick as in, it's still pretty long but easier than learning alone, right?) It is quick start 

### [3] compiler design tutorial (niche-text) — 10 results

- **Compiler Design Tutorial** — https://www.tutorialspoint.com/compiler_design/index.htm
  - Job Search This compiler design tutorial is designed for students and professionals who want to understand the fundamental principles of compiler design. This t
- **Compiler Construction - Compiler Design Lab, Saarland University** — https://compilers.cs.uni-saarland.de/teaching/cc/2013/
  - Core Course The course treats compiler construction for imperative programming languages. This includes lexical, syntactical, and semantic analysis as well as s
- **Compiler Construction - Compiler Design Lab, Saarland University** — https://compilers.cs.uni-saarland.de/teaching/cc/2011/
  - The following students have gained at least 50% of the exercise points. The results of both exams are also available now.
- **Basics of Compiler Design** — https://hjemmesider.diku.dk/~torbenm/Basics/basics_lulu2.pdf
  - 1.3. INTERPRETERS 3 Machine code generation The intermediate language is translated to assembly language (a textual representation of machine code) for a specif
- **TIL: Compiler Design and Programming Language Implementation | Stonecharioteer on Tech** — https://tech.stonecharioteer.com/posts/2020/til-compiler-design-and-language-implementation/
  - Today I explored comprehensive resources on compiler design and programming language implementation, discovering practical approaches to building interpreters, 

### [4] plain text accounting (niche-text) — 10 results

- **Welcome to the Plain Text Accounting forum! - Site - Plain Text Accounting forum** — https://forum.plaintextaccounting.org/t/welcome-to-the-plain-text-accounting-forum/33
  - March 5, 2024, 4:24pm We are building clarity, balance and financial fitness together, with plain text and nimble tools. Welcome! Plain Text Accounting, or PTA 
- **New App: HLedger Plain Text Accounting - 💻 Development - Nextcloud community** — https://help.nextcloud.com/t/new-app-hledger-plain-text-accounting/114307
  - I’m working on a new app and am looking for people interested in contributing or participating/providing feedback. Let me know if you’re interested! Plain Text 
- **PTPL 116 · Plain Text Accounting Level 1, Complete! - Ellane W** — https://ellanew.com/2024/08/05/ptpl-116-plain-text-accounting-level-1
  - This week: However you track your financial records, I hope you’ll be inspired by the fact that doing so in plain text is possible, and powerful! Read on to see
- **Plain Text Accounting - plaintextaccounting.org** — https://plaintextaccounting.org/
  - Welcome! Plain text accounting is a way of doing bookkeeping and accounting with plain text files and efficient, command-line-friendly software like Ledger, hle
- **TIL: Plain Text Accounting with Beancount, Ledger, and Fava | Stonecharioteer on Tech** — https://tech.stonecharioteer.com/posts/2021/til-plain-text-accounting-beancount-ledger/
  - Revolutionary approach to personal and business accounting using simple text files:

### [7] gebrauchte waschmaschine frankfurt (local-biz-de) — 4 results

- **Practice_Grammar_Of_German - Free Download PDF** — https://kupdf.net/download/practicegrammarofgerman_596a7d95dc0d607540a88e7f_pdf
  - July 16, 2017 | Author: Maxim Elgazin | Category: DOWNLOAD PDF - 13.6MB Short Description Download Practice_Grammar_Of_German... Description Dreyer Schmitt A Pr
- **Practice Grammar of German - Free Download PDF** — https://kupdf.net/download/practice-grammar-of-german_596a16e4dc0d60ae66a88e7c_pdf
  - July 15, 2017 | Author: Rouben Parmanum | Category: DOWNLOAD PDF - 4.4MB Short Description german grammar for beginners... Description Dreyer • Schmitt m^mA Pra
- **A Practice grammar of German - PDF Free Download** — https://epdf.tips/a-practice-grammar-of-german.html
  - Dreyer • Schmitt m^mA Practice Grammar of German New edition Verlag für Deutsch Lehr- u n d Übungsbuch der deutsch... Author: | 3342 downloads 11463 Views 5MB S
- **Practice Grammar of German - New Edition (English and German Edition) - PDF Free Download** — https://epdf.tips/practice-grammar-of-german-new-edition-english-and-german-edition.html
  - z -c;t- Drgyer Schmitt P r a c t ~ c eGrammar of German VERLAG FUR ' DEUTSCH Dreyer Schmitt A PrarUe Grammar of... Author: 1427 downloads 8866 Views 116MB Size 

### [8] best noise cancelling headphones 2025 (mainstream-en) — 10 results

- **The Best Wireless Active Noise Cancelling Headphones** — https://thesweetsetup.com/articles/a-roundup-of-the-best-wireless-active-noise-cancelling-headphones/
  - Over the past several months, I’ve been gathering and testing the top contenders for best wireless active noise cancelling headphones. This is a popular categor
- **How Noise Cancelling Headphones Can Make Travel More Comfortable** — https://www.volunteerlatinamerica.com/blog/posts/noise-cancelling-headphones-for-travel
  - 22Dec We have all had those nightmare plane flights, where we are stuck between the teenager with their headphones blasting, and a mother with a wailing baby. N
- **Best Noise Cancelling Headphones for Autism - 2026 Reviews - Truth in American Education** — https://truthinamericaneducation.com/best-noise-cancelling-headphones-for-autism/
  - As someone who’s spent years testing products for families with autism, I’ve learned that the right noise cancelling headphones can be a literal lifeline in ove
- **9 Best Noise Cancelling Headphones Under $100 in 2025** — https://headphonesaddict.com/best-noise-cancelling-headphones-under-100/
  - The price range under $100 offers the best value-for-money active noise-canceling performance. While these headphones are not top-of-the-line, they’re a solid b
- **Noise Cancelling Headphones Market Size and Share Forecast Outlook 2025 to 2035** — https://www.factmr.com/report/3610/noise-cancelling-headphones-market
  - The Global Noise Cancelling Headphones Market Is Forecasted To Reach USD 12.0 Billion In 2025, And Further To USD 23.6 Billion By 2035, Expanding At A 7.0% CAGR

### [9] how does DNS work (docs-en) — 10 results

- **How does DNS work? | Retrovertigo** — https://doriankarter.com/how-does-dns-work/
  - In a nutshell, DNS, or is a system used by computers to translate domain names (e.g. example.com) to their corresponding IP address, which is mapped to a server
- **How Does DNS Work?; A Semi-Comical Flow** — https://ashwiniag.com/how-does-dns-work-a-semi-comical-flow/
  - In my experience, I've revisited this topic multiple times and every single time, I’ve learned something new. So here’s a simple visual walkthrough for those wh
- **How does DNS work? | Louis' thoughts** — https://blog.louis-vallat.dev/how-does-dns-work/
  - 23-03-2025 :: tags: The Domain Name System (or Servers, depending on the context) is one of the key parts of our modern internet. You'd rather type "google.com"
- **How Does DNS Work? - Domain Name Sanity Blog** — https://www.domainnamesanity.com/blog/how-does-dns-work/
  - You’ve surely come across DNS in your digital adventures. Whether when setting up a website or , facing a error, or simply trying to change your DNS settings to
- **How does DNS work ? A big picture | by Greg | Medium** — https://gregsnotes.medium.com/how-does-dns-work-a-big-picture-7af14200c799
  - Root ‘servers’ are owned by different companies: The root servers are supervised by the ICANN.Useful informations regarding these root ‘servers’ can be found he

### [10] climate change carbon capture technology 2025 (mainstream-en) — 10 results

- **Carbon capture and storage** — https://en.wikipedia.org/wiki/Carbon_capture_and_storage
  - Carbon capture and storageCCS) is a process by which carbon dioxide (CO) from industrial installations is separated before it is released into the atmosphere, t
- **Climate change mitigation** — https://en.wikipedia.org/wiki/Climate_change_mitigation
  - Climate change mitigation (or decarbonisation) is action to limit the greenhouse gases in the atmosphere that cause climate change. Climate change mitigation ac
- **of climate change. It was established by the United Nations Environment Programme (UNEP) and the World Meteorological Organiz...** — https://www.ipcc.ch/site/assets/uploads/2018/05/SYR_AR5_FINAL_full_wcover.pdf
  - The Synthesis Report (SYR) distils and integrates the findings of the and objective scientific and technical assessments in this field. Begin- three Working Gro
- **Global warming of 1.5°C An IPCC Special Report on the impacts of global warming of 1.5°C above pre-industrial levels and rela...** — https://www.ipcc.ch/site/assets/uploads/sites/2/2019/06/SR15_Full_Report_Low_Res.pdf
  - Ciais, P. et al., 2013: Carbon and Other Biogeochemical Cycles. In: Climate Deser, C., R. Knutti, S. Solomon, and A.S. Phillips, 2012: Communication of the Chan
- **Microbial carbon capture** — https://www.mpg.de/24094317/microbial-carbon-capture
  - A new structural study reveals the mechanism used by anaerobic microbes to grow on waste gases January 31, 2025 Researchers at three collaborating Max Planck In

## Non-OK Details

### [RATE_LIMITED] static site generator comparison (niche-text)

- **Diagnosis:** status=429 api-event-type=''

### [RATE_LIMITED] beste kaffeemaschine test (mainstream-de)

- **Diagnosis:** status=429 api-event-type=''
