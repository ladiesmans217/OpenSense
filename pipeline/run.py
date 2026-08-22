"""Entrypoint: python -m pipeline run | serve | heal

run    — full pipeline pass (same code path locally and in CI):
         trigger → normalize → dedup → enrich (deadlines) → diff → match → digest,
         then auto-heal any source on a failure streak (opt-in with --auto-heal).
serve  — dashboard + tiny JSON API (stars, event queries) at :8000.
heal   — manual heal for one source (the demo flow).
"""
from __future__ import annotations

import argparse
import json
import os
import socketserver
import sys
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from . import api_sources
from . import enrich as enrichment
from . import event_log, profile as profile_mod, stars as watchlist, trends
from .bodyguard import check as bodyguard_check
from .narrate import narrate
from .notify import build_pdf, render_html_digest, send_email, send_telegram_message
from .brightdata import BrightData
from .dedup import dedup
from .diff import compute, save_state
from .digest import render, send_telegram
from .heal import auto_heal, heal_command
from .match import load_profile, rank as match_rank
from .normalize import normalize_rows


def load_state_listings() -> list[dict]:
    state = DATA / "state.json"
    if state.exists():
        return json.loads(state.read_text("utf-8")).get("listings", [])
    return []

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "sources.yaml").read_text("utf-8"))


def load_sources(dry: bool = False) -> list[dict]:
    sources = [s for s in load_config()["sources"] if s.get("enabled", True)]
    if dry:
        return sources          # dry mode exercises every enabled source with synthetic rows
    missing = [s["name"] for s in sources if not s.get("collector_id")]
    if missing:
        print(f"[skip] no collector_id yet: {', '.join(missing)}  "
              "(run `bdata scraper create` — docs/SETUP.md)", file=sys.stderr)
    return [s for s in sources if s.get("collector_id")]


def run_pipeline(dry: bool = False, auto_heal_enabled: bool = False) -> None:
    sources = load_sources(dry=dry)

    def _log(kind: str, **detail) -> None:
        # --dry is a smoke test: the production event log stays 100% production
        if not dry:
            event_log.log(kind, **detail)

    _log("run_start", sources=len(sources), dry=dry)
    if not sources:
        print("no live sources — create collectors first (docs/SETUP.md)")
        return

    all_rows: list[dict] = []
    failures: dict[str, str] = {}

    def fetch(src: dict) -> list[dict]:
        _log("source_trigger", source=src["name"], collector_id=src["collector_id"])
        try:
            if dry:
                rows = [{"title": f"Dry run listing from {src['name']}",
                         "url": src.get("seed_url", ""), "deadline": "2026-09-01"}]
            else:
                rows = BrightData().run(src["collector_id"], inputs=[src.get("seed_url", "")])
            unified = normalize_rows(src, rows)
            _log("source_result", source=src["name"], raw_rows=len(rows),
                 normalized=len(unified))
            print(f"[ok]   {src['name']}: {len(rows)} raw → {len(unified)} rows")
            return unified
        except Exception as exc:  # partial failure is expected at scale — quarantine, continue
            _log("source_fail", source=src["name"], status="fail", error=str(exc))
            failures[src["name"]] = str(exc)
            print(f"[fail] {src['name']}: {exc}")
            return []

    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(fetch, sources):
            all_rows.extend(rows)

    # supplementary public API/RSS feeds — same pipeline, transport=api in the log
    if not dry:
        for feed_name, rows in api_sources.fetch_all().items():
            src_cfg = {"name": f"api-{feed_name}", "kind": "job",
                       "collector_id": "", "seed_url": ""}
            all_rows.extend(normalize_rows(src_cfg, rows))

    listings = dedup(all_rows)
    _log("dedup", raw=len(all_rows), unique=len(listings))

    if not dry:
        filled = enrichment.enrich(listings, load_config().get("enrichment") or {})
        if filled:
            event_log.log("normalize", total=len(listings), deadlines_filled=filled)

    delta = compute(listings)
    if dry:
        # smoke result goes to the console only — no production data touched
        print(f"\n[dry] {len(sources)} sources → {len(all_rows)} rows → "
              f"{len(listings)} unique — pipeline OK, nothing written")
        return

    event_log.log("delta", **delta["summary"])
    save_state(listings)

    starred = watchlist.starred_ids()
    profile = load_profile()
    ranked = match_rank(listings, profile)
    for item in ranked:
        item["starred"] = item["id"] in starred

    DATA.mkdir(exist_ok=True)
    (DATA / "latest.json").write_text(json.dumps(
        {"generated": event_log.last_run_summary()["last_event_ts"],
         "summary": delta["summary"], "listings": ranked}, indent=1), "utf-8")

    signal = trends.weekly_signal(listings)
    digest = render(ranked, delta, profile, signal=signal)
    ai_lines = narrate(signal, delta.get("new", [])[:5])
    if ai_lines:
        digest = f"🤖 AI narration (optional, env-enabled):\n{ai_lines}\n\n" + digest
    try:
        channel = send_telegram(digest)
        event_log.log("alert", channel=channel, chars=len(digest),
                      narrated=bool(ai_lines))
    except Exception as exc:
        event_log.log("alert", channel="telegram", status="fail", error=str(exc))

    fire_watches(delta)
    send_email_digest(ranked, delta, signal)
    try:
        bodyguard_check()   # cron covers the bot's nap; dedupe lives on disk
    except Exception as exc:
        event_log.log("alert", trigger="bodyguard", status="fail", error=str(exc)[:150])

    if auto_heal_enabled and failures:
        sources_by_name = {s["name"]: s for s in load_sources()}
        auto_heal(failures, sources_by_name)

    event_log.log("run_end", **delta["summary"])
    print(f"\n{delta['summary']}")


class Handler(SimpleHTTPRequestHandler):
    """Static files + the tiny JSON API the dashboard (and the phone PWA) uses."""

    def _json(self, payload, code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}") if length else {}

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/stars":
            return self._json(watchlist.load())
        if parsed.path == "/api/profile":
            return self._json(load_profile())
        if parsed.path == "/api/events":
            source = (parse_qs(parsed.query).get("source") or [None])[0]
            events = [e for e in event_log.recent(300)
                      if source is None or e["source"] == source]
            return self._json(events)
        if parsed.path == "/api/trends":
            return self._json(trends.dashboard_payload(load_state_listings(),
                                                       event_log.recent(300)))
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/star/"):
            listing_id = parsed.path.rsplit("/", 1)[-1]
            return self._json({"id": listing_id, "starred": watchlist.toggle(listing_id)})
        if parsed.path == "/api/profile":
            try:
                saved = profile_mod.sanitize(self._body().get("profile") or {})
            except ValueError:
                return self._json({"error": "invalid json"}, 400)
            saved.setdefault("skills", ["python", "react", "web scraping", "llm"])
            saved.setdefault("roles", ["intern", "junior developer"])
            saved.setdefault("locations", ["remote", "india"])
            saved.setdefault("min_match_score", 1)
            saved.setdefault("top_n_digest", 10)
            (ROOT / "config" / "profile.yaml").write_text(
                yaml.safe_dump(saved, sort_keys=True), "utf-8")
            event_log.log("profile_update", saved_kinds=saved.get("kinds", []),
                          source="personalize-tab")
            return self._json({"status": "saved", "profile": saved})
        if parsed.path == "/api/match":
            try:
                body = self._body()
            except ValueError:
                return self._json({"error": "invalid json"}, 400)
            prof = profile_mod.sanitize(body.get("profile") or {})
            goal = str(body.get("goal") or "")
            if goal:
                prof = profile_mod.apply_goal(prof, profile_mod.parse_goal(goal))
            ranked = match_rank(load_state_listings(), prof)
            return self._json({"profile": prof,
                               "ranked": [{"id": l["id"], "match": l["match"]}
                                          for l in ranked[:50]]})
        return self._json({"error": "not found"}, 404)

    def do_DELETE(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/star/"):
            listing_id = parsed.path.rsplit("/", 1)[-1]
            watchlist.save({k: v for k, v in watchlist.load().items() if k != listing_id})
            return self._json({"id": listing_id, "starred": False})
        return self._json({"error": "not found"}, 404)


def serve(port: int = 8000) -> None:
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    # threaded: one hung/aborted client request must never freeze the dashboard
    with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
        print(f"dashboard → http://localhost:{port}/dashboard/  (API: /api/stars, /api/profile, /api/events, /api/trends)")
        httpd.serve_forever()


def fire_watches(delta: dict) -> None:
    """Keyword watches: ping each chat whose keyword appears in NEW listings."""
    from .bot import load_watches
    watches = load_watches()
    if not watches:
        return
    for w in watches:
        hits = [l for l in delta.get("new", [])
                if w["keyword"] in (l.get("title", "") + " " + l.get("org", "")).lower()]
        if hits:
            lines = [f"👀 watch '{w['keyword']}': {len(hits)} new"] + [
                f"• {h['title'][:60]} ({h['org']})" for h in hits[:5]]
            try:
                send_telegram_message(w["chat_id"], "\n".join(lines))
                event_log.log("alert", channel="telegram", trigger="watch",
                              keyword=w["keyword"], hits=len(hits))
            except Exception as exc:
                event_log.log("alert", channel="telegram", status="fail",
                              trigger="watch", error=str(exc))


def send_email_digest(ranked: list[dict], delta: dict,
                      signal: dict | None = None) -> None:
    if not os.environ.get("EMAIL_TO"):
        return
    try:
        channel = send_email("📡 OpenSense radar",
                             render_html_digest(ranked, delta, signal),
                             build_pdf(ranked, delta, signal))
        event_log.log("alert", channel=f"email:{channel}")
    except Exception as exc:
        event_log.log("alert", channel="email", status="fail", error=str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="full pipeline pass")
    run_p.add_argument("--dry", action="store_true", help="no Bright Data calls")
    run_p.add_argument("--auto-heal", action="store_true",
                       help="auto-heal sources on a failure streak (CI mode)")
    serve_p = sub.add_parser("serve", help="serve the dashboard + API")
    serve_p.add_argument("--port", type=int, default=8000)
    heal_p = sub.add_parser("heal", help="manual heal for one source (demo flow)")
    heal_p.add_argument("--source", required=True)
    heal_p.add_argument("--prompt", required=True, help="what broke / what to change")
    sub.add_parser("bot", help="run the Telegram control plane (docs/SETUP.md)")
    args = parser.parse_args()

    # load .env if present (stdlib-only; CI uses real env vars)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text("utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    if args.cmd == "run":
        run_pipeline(dry=args.dry, auto_heal_enabled=args.auto_heal)
    elif args.cmd == "serve":
        serve(args.port)
    elif args.cmd == "bot":
        from .bot import main as bot_main
        bot_main()
    else:
        cfg = {s["name"]: s for s in load_sources()}
        if args.source not in cfg:
            sys.exit(f"unknown or collector-less source: {args.source}")
        print(heal_command(args.source, args.prompt, cfg[args.source]))


if __name__ == "__main__":
    main()
