# OpenSense — Setup

## 0. Bright Data account (5 min)

1. Sign up: https://brdta.com/wemakedevs — no card needed; free tier is 5,000 credits/month.
2. Billing section → apply promo code `wemakedevs` (lowercase) → +$50 credits.
3. Create an **API token**: https://brightdata.com/cp/setting → API tokens. Put it in `.env`
   as `BRIGHTDATA_API_TOKEN=...` (copied from `.env.example`).

## 1. Step 0 — the pre-built-library check (hackathon rule)

For every source you enable, confirm it is NOT in Bright Data's 800+ pre-built library:
https://brightdata.com/cp/scrapers/browse — if it is covered, swap the source for another
long-tail one. Each `config/sources.yaml` entry has a `verify_not_prebuilt: true` flag as
a reminder; actually do the check.

## 2. Create collectors (the four commands)

```bash
npx -p @brightdata/cli bdata login --device     # device flow — most reliable inside agents

# per source (example: a careers listing page — Discovery type):
npx -p @brightdata/cli bdata scraper create https://www.zoho.com/careers/ \
  "job title, job url, location"
# → note the c_* Collector ID from the output

# verify it works, pretty-print a sample row:
npx -p @brightdata/cli bdata scraper run c_xxxxxxxxxxxx https://www.zoho.com/careers/ --pretty
```

Scraper types by source kind (pick per source, see docs.brightdata.com/datasets/scraper-studio/ai-agent):

| Source | Type | Fields to request |
|---|---|---|
| Careers/jobs listing page | `discovery` | title, url, location |
| Scholarship foundation page | `pdp` | title, deadline, url |
| Community/events site | `sitemap` | title, url |
| Hackathon listing | `discovery` | title, url, application deadline |

Then put the `c_*` id into `collector_id:` for that source in `config/sources.yaml`.

## 3. Run

```bash
pip install -r requirements.txt
python -m pytest -q              # 110 tests: normalize / dedup / delta / match / trends / bodyguard / bot
python -m pipeline run --dry     # smoke test: no Bright Data calls, and NOTHING written —
                                 # the event log / state / digest stay 100% production
python -m pipeline run           # real run: collectors + API/RSS feeds → normalize → dedup → enrich → diff → digest
python -m pipeline serve         # dashboard + API → http://localhost:8000/dashboard/
```

Extras:
- `python -m pipeline run --auto-heal` — enable the self-heal loop (CI runs this).
- `python -m pipeline heal --source <name> --prompt "<what broke>"` — manual heal (demo flow).
- Supplementary feeds (RemoteOK, Remotive, WorkingNomads, WWR RSS, YouTube channel RSS) run
  automatically inside every pipeline run — public APIs are rules-permitted; Scraper Studio
  collectors remain the core (see `pipeline/api_sources.py`, event-logged with transport=api).
- **Personalization (no login):** dashboard → ⚙️ personalize → pick kinds/skills/goal →
  Save (this browser, persists forever) or "Save + use for my digest" (server profile;
  next run's Telegram alert matches it). Free-text goals are parsed by deterministic rules
  ("2nd year, only internships", "competitions that lead to jobs").
- **Install on Android:** open `http://<your-PC-ip>:8000/dashboard/` in Chrome on the phone
  (same Wi-Fi), menu → *Install app* / *Add to Home screen*. Stars + personalization sync
  through the API. (Service worker needs https or localhost — on plain http from another
  device the app still works, SW just skips registering.)

## 4. Telegram digest (optional, 5 min)

@BotFather → `/newbot` → token → `.env` as `TELEGRAM_BOT_TOKEN`. Message your bot once,
get your chat id from @userinfobot → `TELEGRAM_CHAT_ID`.

## 5. CI (the reliability evidence)

```bash
git init && git add -A && git commit -m "OpenSense"
gh repo create opensense --public --source=. --push
gh secret set BRIGHTDATA_API_TOKEN
# optional: gh secret set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
```

Actions → "radar" → Run workflow. Every 6h cron run commits `data/` back — the repo's
commit history *is* the production-run log. (Workflow file: `.github/workflows/pipeline.yml`.)

## 6. The control plane — add/remove sources from your phone (Telegram bot)

1. Talk to **@BotFather** → `/newbot` → get the token → `TELEGRAM_BOT_TOKEN` in `.env`.
2. Message your new bot once (any text), then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy your numeric
   `"chat":{"id":...}` → `TELEGRAM_CHAT_ID` **and** `TELEGRAM_ADMIN_IDS` in `.env`
   (the allowlist — the bot ignores everyone else).
3. Run it: `python -m pipeline bot` (keep this terminal/host alive — your PC or a
   small VPS; the cron pipeline on GitHub Actions needs nothing from it).

Now from your phone:
```
/add https://xyz.com/scholarships scholarships
```
The bot runs the ladder — deny-list → probes → AI generation (~10 min) → verify →
heal-until-good → wire into sources.yaml → git commit — then replies:
`✅ added (N rows verified, live from next cron)` / `⚠️ benched (reason)` /
`❌ denied (reason — e.g. LinkedIn: login-walled + personal data + ToS)`.

Other commands: `/find <query>` (instant search over the live radar) ·
`/suggest [kind]` (the bot proposes its next sources with one-tap Add / Skip buttons) ·
`/remove <name|url>` · `/status` (fleet health line) · `/sources` (per-source success
rate, last 20 runs) · `/heals` · `/watch <keyword>` (pings when NEW listings match —
fired by the cron from CI too) · `/approve c_xxx` / `/reject c_xxx` for heal approvals.
Star a listing on the dashboard and, if it closes within 3 days, the **deadline
bodyguard** pings you daily until it passes (runs from both the bot and the cron;
dedupe lives in `data/bodyguard.json`).

**Optional LLM narration:** set `NARRATE_API_KEY` (any OpenAI-compatible API; optional
`NARRATE_BASE_URL`, `NARRATE_MODEL`) and the digest gains a clearly-labeled 2–3 line AI
narration on top of the rules-based summary. Off by default; any failure is silent.

**Email digest:** set `EMAIL_TO` plus either `RESEND_API_KEY` or Gmail SMTP
(`SMTP_USER` + 16-char app password from myaccount.google.com → Security →
App passwords). Every pipeline run then sends a categorized HTML digest with a
PDF one-pager attached.

## 7. The self-heal demo (reliability criterion)

Two heal moments, film both:

**A. In the wild.** With 15+ heterogeneous sources, something breaks on its own between
runs (a redesign, a JS widget). When a source fails:

```bash
npx -p @brightdata/cli bdata scraper heal c_xxxx "the title field returns empty; the site redesigned its listing cards"
npx -p @brightdata/cli bdata scraper approve c_xxxx
npx -p @brightdata/cli bdata scraper run c_xxxx <url> --pretty   # same Collector ID
```

**B. Controlled (undeniable, from the official repo's technique).** Host `demo-site/` on
GitHub Pages → build a collector against it → on camera, rename the `sch-title` class to
`sch-heading` and push → run (title breaks) → heal → approve → re-run (rows return,
Collector ID unchanged). The instructions are in the demo-site HTML comments.

## 7. Submission checklist (maps 1:1 to the rules)

- [ ] Public repo, this README, judge-runnable setup (this file)
- [ ] Example structured output committed (`data/latest.json`)
- [ ] Demo video ≤ 90s following `docs/DEMO_SCRIPT.md` (claim → timeline → heal → digest)
- [ ] README section: how Scraper Studio is used (the four commands + trigger API in CI)
- [ ] AI-use disclosure: coding-agent assisted, heal prompts written by us, ranking
      logic understood and explainable line by line
- [ ] No tokens/.env in repo or video; public data only; no .gov sites; no personal data
