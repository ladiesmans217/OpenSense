# Optional: n8n delivery layer

OpenSense's brain is the Python pipeline (keep it that way — clean-code judging). n8n is an
optional *visual* edge: a 4-node workflow that mirrors the digest into other channels and
gives you a nodes-lighting-up execution view for the demo.

## Run locally

```bash
cd n8n && docker compose up -d     # → http://localhost:7888
```

## The workflow (build in UI, then export JSON into this folder)

```
Schedule Trigger (every 6h)
  → HTTP Request   POST https://api.brightdata.com/dca/trigger?collector_id=c_xxx
                   (header: Authorization Bearer {{token}} — n8n credential, never in JSON)
  → Wait / poll    GET /dca/task until status "ready"
  → Code node      simple filter (deadline within 7 days)
  → Telegram node  send digest
```

Rules of engagement:
- Only time-based triggers — local Docker n8n can't receive webhooks without a tunnel.
- Export the workflow as JSON and commit it here; keep secrets in n8n credentials.
- If it ever fights you, drop it — GitHub Actions already does this job, and the event log
  is the better story.

Licensing note: self-hosted n8n under its Sustainable Use License is fine for hackathon use.
