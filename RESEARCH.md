# Scrape-Verse Research Compendium

> Research for the Into the Scrape-Verse hackathon (WeMakeDevs × Bright Data, Aug 17–23, 2026).
> Compiled 2026-08-22 from: the hackathon site, Bright Data docs, Bright Data's own past hackathons,
> other vendor hackathons (Apify, Firecrawl, Browserbase), WeMakeDevs' 24 past hackathons,
> real scraping-built companies, GitHub open-source, and the Apify/Firecrawl/Bright Data ecosystems.

---

## A. What actually wins — the evidence

### A1. Bright Data's own past hackathons (strongest signal — same sponsor, same judges' taste)

**Web Scraping Challenge (dev.to, Jan 2025, $1,000 × 3):**
| Winner | Project | Why it won (per judges) |
|---|---|---|
| **Cheaperr** | Price comparison across Amazon/eBay/AliExpress | "Solving a real consumer need" — [post](https://dev.to/sarahokolo/compare-prices-across-aliexpress-ebay-amazon-1alj) |
| **Tech Trend Tracker** | Reuters scraping + AI keyword rankings + semantic search | "Beyond basic data collection" — [post](https://dev.to/yukaty/tech-trend-tracker-ai-powered-news-analysis-for-technology-insights-260g) |
| **Reddit Recap** | Reddit → AI summaries + audio briefings | "Simple, useful, clever" — [post](https://dev.to/dhanushreddy29/reddit-recap-3j6d) |

[Winners announcement](https://dev.to/devteam/congrats-to-the-bright-data-web-scraping-challenge-winners-46nf)

**Real-Time AI Agents Challenge (n8n + Bright Data) — 5 winners** ([announcement](https://dev.to/devteam/congrats-to-the-winners-of-the-real-time-ai-agents-challenge-powered-by-n8n-and-bright-data-104c)):
- **SOC-CERT** — threat-intel monitor: 100+ CVEs/day from CISA+OTX, AI scoring, Slack alerts
- **BrandGuard AI** — multi-agent brand-mention + sentiment monitor with dashboard + Slack bot
- **Event Butler** — daily Eventbrite scraping + Gemini curation → newsletter digest
- **Release & Deprecation Sentinel** — SRE copilot tracking release notes/deprecations from 18+ vendors (K8s, Docker, HashiCorp), fetch every 6h
- **Pixie** — voice-driven website builder: scrape target site → AI PRD → live prototype

**Web Data UNLOCKED (lablab.ai × Bright Data, May 2026)** — [recap](https://lablab.ai/ai-hackathons/brightdata-ai-agents-web-data-hackathon):
10 first-place projects: **Wayfinder** (geospatial dev-agent search), **C2** (crypto risk scraper), **VeriTrace** (misinformation verification), **HomeStar** (real estate), **Foreshock** (earthquake intel), **Uh Oh!** (network outage tracking), **Trading Card Block** (TCG market index), **War Room AI** (defense), **Verdict** (court-ruling digest).
Pattern: **niche domain + Bright Data scrapers + agent/LLM layer**.

### A2. Other vendor hackathons

- **Apify $1M Challenge** ([winners](https://apify.com/challenge)): Website Tech Stack Scanner (detects 6,000+ technologies), Google Maps AI Reviews Analyzer, FEC Campaign Finance Scraper, Shopify Store Intelligence, Google Flights API. Judges rewarded "code quality, concept, UX, and scraping + AI in a single workflow."
- **UC Berkeley AI Hackathon 2026 (Browserbase)** — 107 of ~400 teams used Browserbase/Stagehand; winners: **Narcore** (agent spotting hidden drug ads in social feeds), **Constructa** (find buildable land), **Accordion** ([Browserbase LinkedIn](https://www.linkedin.com/posts/paulkleiniv_we-sponsored-uc-berkeleys-ai-hackathon-this-activity-7476310900166062082-RU0j), [Devpost](https://ai-hackathon-2026.devpost.com/))
- **ElevenHacks (Firecrawl)** — winner **KLEOS**: cinematic audio documentary, Firecrawl + ElevenLabs, $10k ([event](https://hacks.elevenlabs.io/hackathons/0))
- **Platanus Hack (Firecrawl, Mexico City 2026)** — Best Use of Firecrawl: **Sendero**, missing-persons research platform ([recap](https://abimael.me/blog/platanus-hack-firecrawl-mexico-city-2026.html))
- **Agno Global Agent Hackathon** — winner **TripCraft AI** ([results](https://www.agno.com/articles/global-agent-hackathon-winners))
- **Meta-insight**: someone scraped 10,014 Devpost winners (1999–2026) and found stack choice doesn't predict winning (86.6% tagged "AI/ML") — **demo/story beats stack** ([Hackathon Explorer](https://www.kaushik.cv/blog/hackathon-explorer-10k-winners))

### A3. WeMakeDevs' own history (24 hackathons to date)

Recent/flagship events: AgentHack 2025 (Aug), FutureStack 2025 (Cerebras/Meta/Docker), MultilingualHack 2025, AI Agents Assemble, Backend Reloaded (Motia), The UI Strikes Back (Tambo), Hack All February, 2 Fast 2 MCP, Agents of SigNoz (Jul 2026), The Hangover Part AI (Cognee, winners: "Lethe" & "Classroom Memory"), Pirates of the Coral-Bean, Back to the Metadata (OpenMetadata). ([full list](https://www.wemakedevs.org/hackathons))

Winner data points:
- AgentHack 2025: MacBook Pro → Team Dark Mode (Anuj & Mohit Upadhyay); iPad Air → Atibhi Agrawal; top 10 included Hardik Khanduja, Prince Panchani, Gautam Khosla ([LinkedIn](https://www.linkedin.com/posts/wemakedevs_the-wait-is-over-meet-the-winners-of-activity-7368537533967708160-E8YQ))
- Hangover/Cognee winners: "Lethe" and "Classroom Memory" ([LinkedIn](https://www.linkedin.com/posts/wemakedevs_the-hangover-hackathon-track-winners-activity-7486026563558391808-BW5c))
- **Best-Blog side tracks exist in almost every WeMakeDevs hackathon** and winners are announced publicly — in Scrape-Verse this is the Daily Bugle LinkedIn track.
- Pattern across WeMakeDeVs events: **side tracks (UI, clean code, blog) let multiple people win**; the grand prize favors polished, demo-able, community-visible projects. Daily livestreams + Discord show-and-tell participation correlates with winning (organizers repeatedly pull projects from the "get feedback" channel for live reviews).

### A4. The winning formula (synthesized across all sources)

1. Niche/regional site class (long tail, not pre-built-covered)
2. Scheduled scraping — Collector ID treated as a production API
3. AI layer on top (summaries / sentiment / matching / agents)
4. Tangible delivery surface (Slack / newsletter / dashboard / alerts)
5. An on-video healing demo
6. A story: "problem → data nobody had → decision delivered"

---

## B. Real companies built on scraping (inspiration gallery)

Every one of these won by (a) aggregating a long tail nobody bothered with, (b) making the time-series/history the moat, (c) monetizing via subscription/affiliate/data sales.

### Price & deal tracking
- **Keepa** ([keepa.com](https://keepa.com)) — price-history charts for 7B+ Amazon products; freemium + API standard for FBA sellers. *Angle: niche e-commerce + time-series DB + drop alerts.*
- **CamelCamelCamel** ([about](https://camelcamelcamel.com/about)) — started 2008 as a code experiment; free tool, affiliate-monetized. *Angle: simplest viable build in the gallery.*
- **Honey** — scraped coupon codes; acquired by PayPal ~$4B (2019). *Angle: coupon/deal finder for one category.*
- **Slickdeals** — community-curated deal aggregation; ~$500M acquisition (2017).

### Travel
- **Skyscanner** — began as a spreadsheet crawling airline prices (2002); acquired ~£1.4B ([Wikipedia](https://en.wikipedia.org/wiki/Skyscanner)). *Angle: fare-anomaly radar for a few routes.*
- **Kayak** — metasearch over fragmented booking sites; $1.8B to Priceline.
- **Going** (ex-Scott's Cheap Flights) — deal newsletter → $49–199/yr subscriptions ([guide](https://www.going.com/guides/membership-guide)).

### Jobs & hiring
- **Indeed** — crawled Craigslist/Monster/career pages; ~$1B exit nearly bootstrapped ([origin story](https://www.businessinsider.com/indeed-an-almost-entirely-bootstrapped-job-search-giant-gets-a-monster-exit-2012-9)). *Angle: vertical Indeed for one niche.*
- **Levels.fyi** — started from Google Sheets, 3M+ monthly users ([about](https://www.levels.fyi/about/)). *Angle: scrape legally-mandated pay-transparency ranges into a comp explorer.*
- **Layoffs.fyi** — pandemic side-project spreadsheet → 450k+ layoffs tracked, media-cited ([NYT](https://www.nytimes.com/2023/05/05/business/roger-lee-layoffs.html)).
- **TrueUp.io** — jobs scanned minus layoffs = "net hiring" index ([tracker](https://www.trueup.io/layoffs)).

### Real estate
- **Zillow** — scraped county records + listings → Zestimate ([Wikipedia](https://en.wikipedia.org/wiki/Zillow)). *Angle: price/sqft model flagging mispriced homes in one city.*
- **Mashvisor** — Airbnb performance data → ROI projections (data that isn't in any MLS).

### Music & events
- **Bandsintown** / **Songkick** (scraped DB so valuable Ticketmaster fought a $110M war over it — [Billboard](https://www.billboard.com/pro/ticketmaster-songkick-settle-lawsuit-110-million/)) / **Resident Advisor**. *Angle: venue-crawl gig tracker for one city + weekly digest = the official demo repo's "Stagelight" idea.*

### Finance & alt-data
- **YipitData** — scraped consumer data → KPIs for 450+ hedge funds; Carlyle invested up to $475M, ~$3B valuation talk ([Bloomberg](https://www.bloomberg.com/news/articles/2021-12-06/carlyle-to-invest-up-to-475-million-in-alternative-data-firm-yipitdata)). *Angle: "alt-data in a box" for one public company (stock-outs, SKU velocity, review velocity).*
- **Thinknum** — job postings/store locations as fund data; acquired by FactSet.
- **AltIndex** — social+web scraping → AI stock signals.

### E-commerce intelligence
- **Jungle Scout** — FBA seller's Amazon research tool → $110M raised. *Angle: product-opportunity finder for one category.*
- **Similarweb** — crawl+panel web measurement; NYSE IPO. *Angle: tech-stack adoption crawler ("which sites adopted X").*

### Review analysis
- **Fakespot** — AI review-authenticity grading; Mozilla acquired then **shut it down June 2025 — the market gap is open** ([Mozilla](https://blog.mozilla.org/en/mozilla/building-whats-next/)).
- **ReviewMeta** — solo-founder Amazon review analyzer.

### AI/search infra
- **Common Crawl** — the open corpus under LLM pretraining.
- **Exa.ai** — embedding-based search API for agents.
- **Perplexity** — answer engine over live retrieval. *Angle: vertical answer engine with citations for one domain.*

### Niche & civic
- **NowInStock.net** — solo-run restock monitor (PS5/GPUs); cult status during shortages. *Angle: the canonical self-healing demo — product pages churn constantly.*
- **OpenCorporates** — scraped 140+ inconsistent company registries → largest open company DB ([Wikipedia](https://en.wikipedia.org/wiki/OpenCorporates)).
- **CourtListener/RECAP** — nonprofit PACER mirror + court opinions ([Wikipedia](https://en.wikipedia.org/wiki/CourtListener)). *Angle: docket-watcher alerting on keywords.* (Note: for the hackathon, government sites are banned — do the *news/legal-database* version, not .gov.)
- **Oddschecker** — real-time odds across 25+ bookmakers. *Angle: odds-divergence radar for one league.*
- **CarGurus** — scraped used-car listings + deal scores; $3.5B+ IPO ([Inc.](https://www.inc.com/magazine/201808/bill-saporito/cargurus-tripadvisor-langley-steinert.html)).
- **GovTrack.us** — solo civic scraper since 2004 (again: .gov is banned in this hackathon — pattern only).

### Top-10 hackathon-viable adaptations (from the gallery)
1. Restock tracker (NowInStock clone) — self-healing showcase
2. Fakespot successor — open market gap since June 2025
3. Layoffs/jobs net-hiring tracker (layoffs.fyi × TrueUp)
4. Keepa-mini price-history tracker for a niche store
5. Flight-deal anomaly radar (Going mini)
6. Pay-transparency comp explorer (levels.fyi mini)
7. Alt-data KPI dashboard (YipitData-lite for one company)
8. Deal-score finder for used cars/rentals (CarGurus/Mashvisor mini)
9. Vertical answer engine with citations (Perplexity mini)
10. Odds/value divergence detector (Oddschecker mini)

---

## C. GitHub open-source worth studying (stars verified 2026-08-22)

**Frameworks:**
- [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) — 170,663★ — born as a weekend hack; context API
- [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling) — 75,744★ — **adaptive self-healing scraping toolkit — thematically the closest OSS cousin to this hackathon**
- [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) — 79,014★ — LLM-friendly crawling for RAG
- [ScrapeGraphAI/Scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) — 29,805★ — "You Only Scrape Once": NL-described schemas, layout-change resistant
- [apify/crawlee](https://github.com/apify/crawlee) — 25,458★ — the engine behind Apify actors
- [browser-use/browser-use](https://github.com/browser-use/browser-use) — 110,046★ — LLM drives a real browser
- [dzhng/deep-research](https://github.com/dzhng/deep-research) — 19,581★ — iterative search+scrape+synthesize
- [getmaxun/maxun](https://github.com/getmaxun/maxun) — 17,254★ — open-source no-code scraping platform
- [brightdata/cli](https://github.com/brightdata/cli) — 6,382★ — the hackathon's own tool
- [lorien/awesome-web-scraping](https://github.com/lorien/awesome-web-scraping) — 8,128★ — the canonical list

**Application-level:**
- [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy) — 4,132★ — job-board aggregation standard
- [techwithtim/Price-Tracking-Web-Scraper](https://github.com/techwithtim/Price-Tracking-Web-Scraper) — 1,295★ — **price tracker built on Bright Data** + Playwright + React + Flask
- [Cybrarist/Discount-Bandit](https://github.com/Cybrarist/Discount-Bandit) — 732★ — self-hosted multi-store price tracker
- [PaulMcInnis/JobFunnel](https://github.com/PaulMcInnis/JobFunnel) — 2,179★ — multi-board jobs → one deduped sheet
- [shafiab/HashtagCashtag](https://github.com/shafiab/HashtagCashtag) — 509★ — Kafka/Spark/Cassandra sentiment pipeline (architecture reference)
- Firecrawl example apps: [fireplexity](https://github.com/firecrawl/fireplexity) (Perplexity clone), [open-deep-research](https://github.com/nickscamara/open-deep-research), [firegeo](https://github.com/firecrawl/firegeo) (GEO SaaS starter) — [10 AI projects blog](https://www.firecrawl.dev/blog/10-ai-projects-with-firecrawl)

---

## D. Tool landscape & ecosystem mines

### D1. The landscape (for context; Scraper Studio is required anyway)
| Tool | What it is | Note |
|---|---|---|
| Bright Data | Full-stack: proxies → unlocker → scraper APIs → datasets | 50k+ customers, compliance-first |
| Apify | Actor marketplace; ~3,000 devs earn ~$1.4M/mo | Distribution model |
| Firecrawl | URL → LLM-ready markdown; 170k★ OSS | Apple/Canva/Zapier customers |
| Oxylabs / Decodo / Zenrows / ScraperAPI / Zyte / SerpApi | One-layer scraping APIs | Various niches |
| Browserbase ($40M Series B) / Steel.dev / Browser Use | Browser infra for AI agents | "Act," not just "read" |
| Crawl4AI / ScrapeGraphAI / Jina Reader | OSS AI-native scraping | LLM-era patterns |

### D2. Apify Actor Store — what people actually pay for (top by users)
Google Maps Scraper (570K users), Instagram Scraper (370K), TikTok (241K), Google Search Results (169K), **RAG Web Browser (157K)**, Website Content Crawler (149K), LinkedIn Jobs (137K), Web Scraper generic (123K), YouTube (106K), Maps Email Extractor (86K). ([store](https://apify.com/store))
Store categories = demand taxonomy: SOCIAL_MEDIA, ECOMMERCE, LEAD_GEN, NEWS, TRAVEL, JOBS, REAL_ESTATE, VIDEOS, AI, AGENTS, SEO_TOOLS, MCP_SERVERS.

### D3. Firecrawl's 12 canonical use-cases ([page](https://www.firecrawl.dev/use-cases))
RAG/knowledge bases, price & inventory monitoring, content generation, MCP integrations, AI platforms reselling web data, investment intelligence dashboards, deep-research agents, model training data, SEO/SERP tracking, competitive monitors, lead enrichment, ETL/content migration.

### D4. Bright Data's own dataset catalog — the literal price list of valuable data
700+ datasets. Top sellers: **LinkedIn people profiles (122K downloads)**, LinkedIn companies (34K), **Amazon products (36K)**, Google Maps full+reviews, Indeed jobs, Glassdoor, Instagram/TikTok/X/YouTube social sets. ([datasets](https://brightdata.com/products/datasets))

### D5. Cross-mine signal
Local-business/Maps data, social media, Amazon/e-commerce, jobs, and web→markdown-for-RAG are what people pay for **repeatedly** — but remember the hackathon twist: **most of those top sellers are exactly what the 800+ pre-built scrapers already cover, so the winning move is the same *pattern* applied to a long-tail source nobody covers.**

### D6. Top 10 recurring build patterns across ecosystems
1. Local-business lead gen (Maps → contacts → CRM)
2. Social monitoring & content extraction
3. Web → LLM-ready markdown for RAG/agents
4. Price & e-commerce monitoring (history + alerts)
5. SERP scraping & rank tracking
6. Lead enrichment & contact discovery
7. Job-market intelligence
8. Review & reputation aggregation
9. News / competitive / finance intelligence
10. Agent browser automation (scraping as the sensing layer of agents)

Highest-proven-demand builds **combine 2+ patterns** (e.g., long-tail e-commerce scrape + LLM summarization + alert agent).

---

## E. Scrape-Verse-specific constants (from the official material)

- Required: build + run a **custom** scraper via Scraper Studio; pre-built scrapers alone don't qualify
- Demonstrate `bdata scraper heal` — Collector ID unchanged — **on camera**
- Wire the Collector ID downstream (schedule / DB / API / dashboard / agent)
- Public data only; no login/paywall/personal data; **no .gov sites**
- Long-tail targets (regional e-commerce, B2B catalogs, niche verticals, docs, changelogs)
- Judges score 6 criteria equally: impact, creativity, technical excellence, Scraper Studio use, reliability/self-healing, **presentation (demo video scored as hard as code)**
- Side-track lanes: Best UI (iPads), Best Clean Code (Keychrons), Best LinkedIn Post (Galaxy Watch)
- The official companion repo's demo ideas: Stagelight (venue gigs → map; UI track), OpenCall (grants/CFP deadlines → matched digest; grand-prize track), Signal Hire (100 careers pages → hiring trends; clean-code track), plus the "host your own page, break a selector, film the unattended heal" technique
- Repo: [anil-bd/scraper-studio-scrape-verse-hackathon-august-2026](https://github.com/anil-bd/scraper-studio-scrape-verse-hackathon-august-2026) · [kick-off blog](https://www.wemakedevs.org/blogs/scrape-verse-kick-off) · [Day 4 strategy stream](https://www.youtube.com/watch?v=xv5Uog-Xvt4)

---

## F. The convergence — where all four research lanes agree

Every independent lane (Bright Data's own winners, other hackathons, real companies, ecosystem demand data) converges on the same shape:

**A class of long-tail heterogeneous sites → scheduled scraping with self-healing at its core → an AI layer (match/summarize/score) → a delivered artifact (alert, digest, dashboard, answer) → a demo that leads with a claim and shows the heal.**

The differentiators, ranked by evidence:
1. The data asset nobody else has (coverage of a class, not a site; time-series, not snapshot)
2. The failure-handling story (heal on camera, partial-failure UX, coverage %)
3. The delivery surface (a decision arrives, not a dashboard that waits)
4. The narrative demo (90 seconds, claim first, screen not JSON)
5. Community visibility (Discord show-and-tell, LinkedIn post — both are literally scored)
