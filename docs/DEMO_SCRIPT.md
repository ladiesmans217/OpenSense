# The 90-second demo video

One claim, one screen, no terminal JSON crawl. Presentation is scored as hard as code.

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:15 | Dashboard (desktop), reliability strip | "Internshala and LinkedIn index the platforms. The long tail — 10 startup career pages, hackathon listings, competitions — nobody covers. OpenSense does, with scrapers that heal themselves." |
| 0:15–0:35 | Event-log timeline scrolling | "Every six hours, CI triggers my Bright Data collectors. This append-only log is the spine: runs, rows, failures, heals, enrichment — every number on screen traces to the collector run that produced it. Click any listing —" |
| 0:35–0:50 | Lineage modal open | "— and there's the provenance: source, collector ID, first seen, the runs behind it." |
| 0:50–1:05 | Delta cards + "new" pills + enrichment event | "It compounds: new listings arrive, and watch — a hackathon that had no deadline just got one, filled by a second scraper that reads the event's own detail page. Now it's counted down in 'closing this week'." |
| 1:05–1:20 | **The heal scene** — demo-site editor + terminal | "Sites change; scrapers die — that's the maintenance tax everyone pays. Watch: I break this page's markup. The next run fails — there it is on the timeline — and the auto-heal loop repairs it, approved, same Collector ID, integrations untouched." |
| 1:20–1:30 | Phone: PWA + Telegram digest | "Same dashboard, installed on my phone — offline-capable, my starred watchlist synced. And it's personal: no login, one prompt — '2nd year, only internships, competitions that lead to jobs' — and the radar re-ranks itself, even flagging hackathons whose prizes include a job offer. The decision arrives as one alert. Long tail → one schema → one alert. OpenSense." |

## The control-plane beat (45–60s, closer — nobody else will have this)

1. Phone (Telegram): type `/add https://<some-listing-site> scholarships` →
   bot acks with the ladder ("deny-list → probes → generation → verify → heal-until-good").
2. Cut to the verdict message arriving: "✅ added — N rows verified, live from the next cron."
3. Dashboard: refresh → the new source appears with listings.
4. One-liner: "The radar grows new senses from a text message. LinkedIn? It refuses —
   login-walled, personal data, against the rules — and tells you why."
5. `/find ml internship bangalore` → instant formatted hits from the live radar
   ("it's an assistant, not just an admin panel").
6. `/suggest` → the bot proposes its OWN next sources with Add / Skip buttons —
   tap Add, the whole ladder runs. "It proposes its own expansion."
7. Star something closing soon on the dashboard → next day's bodyguard ping
   ("⭐ closes in 2 days") — screenshot it for the video.
8. Optional: `/watch gsoc` → next run pings when new GSoC-related listings land.

## The personalization beat (30–45s, if extending the video)

1. Fresh browser → nudge appears → click Personalize (no login anywhere).
2. Type the goal: "2nd year, only internships and competitions that lead to jobs" → Save.
3. Table re-ranks instantly; kinds filter to internships + hackathons/bounties; listings with
   the "→ job" pathway badge rise (prizes scraped by the enrichment collector say
   internship/PPO).
4. "Save + use for my digest" → the next pipeline run's Telegram alert matches it
   (show the profile_update event appearing on the timeline).
5. Close the browser, reopen — profile still there. localStorage, no accounts, never expires.

## The intelligence beat (15–20s — the alt-data pitch)

1. Dashboard: point at the trend card — "📈 this week: +38 new (↑45% vs last week)"
   with the 14-day sparkline underneath.
2. "No single-site aggregator can draw this line — it only exists because we hold
   thirty sources in one schema. That's the dataset as an asset."
3. `/sources` on the phone: per-source health ("shine-jobs · 🟢 97% · 22 runs") —
   "reliability is measured, not claimed."

## Shot list

1. Desktop dashboard hero scroll (5s) — cards + trend sparkline + timeline animating.
2. Type "machine learning" in the search box → instant filter; flip sort to deadline.
3. Click one listing → lineage modal (hold 3s on the collector ID).
4. Delta: hover "new" pills; point at the `enrich` event filling a deadline.
5. Heal (film exactly like this): pre-stage the broken `demo-site` commit → run pipeline
   (or CI run history) → show `source_fail` → auto-heal events → re-run green with the
   identical `c_*` id on screen. Never cut away from the Collector ID.
6. Phone: PWA on home screen → open (airplane mode for the offline beat) → star a listing.
7. Telegram: real starred+closing digest arriving (send it live before recording) with
   the 📈 trend line at the top; then `/find` and `/suggest` with buttons.
8. End card: repo URL + "built on Bright Data Scraper Studio" + the 4 commands.

## Extra 30 seconds (if the form allows longer)

- GitHub Actions run history: "production — every cron run committed back; the commit log is the uptime record."
- `pytest` passing locally / the CI test job.
- `config/sources.yaml`: the source registry with per-source Collector IDs + the enrichment collector.
