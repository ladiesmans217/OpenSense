"""Deadline bodyguard: starred listings closing within 3 days get a daily ping
until the deadline passes (one 'passed' notice, then silence until unstarred).

Runs from two places — the bot loop (always-on) and the end of each pipeline
run (CI cron) — so the dedupe lives in data/bodyguard.json, not in memory:
two runners can never double-ping. Stale past deadlines in the data (rows
parsed from historical text) are ignored, not announced.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

from . import event_log
from .normalize import days_left

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "bodyguard.json"
LATEST = ROOT / "data" / "latest.json"
WINDOW_DAYS = 3
CHECK_INTERVAL_S = 3600          # at most one scan per hour even with two runners


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text("utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), "utf-8")


def due(listings: list[dict], starred_ids: set[str]) -> list[dict]:
    """Starred listings with 0 <= days_left <= WINDOW_DAYS, soonest first."""
    out = []
    for l in listings:
        if l.get("id") not in starred_ids:
            continue
        dl = days_left(l.get("deadline"))
        if dl is not None and 0 <= dl <= WINDOW_DAYS:
            out.append({"id": l["id"], "title": l["title"], "org": l.get("org", ""),
                        "url": l.get("url", ""), "days_left": dl})
    out.sort(key=lambda x: x["days_left"])
    return out


def plan_messages(due_list: list[dict], listings: list[dict], starred_ids: set[str],
                  state: dict, today: str | None = None) -> tuple[list, list, dict]:
    """Pure: which pings/notices to send + the next state. A listing pings at
    most once per calendar day; a starred item whose deadline just passed gets
    one 'passed' notice only if we'd pinged it before."""
    today = today or date.today().isoformat()
    still_starred = {l["id"]: l for l in listings if l.get("id") in starred_ids}
    new_state = {k: dict(v) for k, v in state.items() if k in still_starred}

    pings = []
    for d in due_list:
        rec = new_state.setdefault(d["id"], {"last_ping": "", "passed_notified": False})
        if rec.get("last_ping") != today:
            pings.append(d)
            rec["last_ping"] = today

    due_ids = {d["id"] for d in due_list}
    passed = []
    for lid, l in still_starred.items():
        if lid in due_ids:
            continue
        dl = days_left(l.get("deadline"))
        if dl is None or dl >= 0:
            continue
        rec = new_state.get(lid)
        if rec and not rec.get("passed_notified") and rec.get("last_ping"):
            passed.append({"id": lid, "title": l["title"], "url": l.get("url", "")})
        if rec:
            rec["passed_notified"] = True
    return pings, passed, new_state


def check() -> int:
    """One scan (throttled to CHECK_INTERVAL_S). Returns pings sent."""
    if not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        return 0
    state = load_state()
    if time.time() - state.get("_last_check", 0) < CHECK_INTERVAL_S:
        return 0

    from .notify import send_telegram_message
    from .stars import starred_ids

    listings = []
    if LATEST.exists():
        listings = json.loads(LATEST.read_text("utf-8")).get("listings", [])
    starred = starred_ids()
    records = {k: v for k, v in state.items() if not k.startswith("_")}
    pings, passed, new_records = plan_messages(
        due(listings, starred), listings, starred, records)

    save_state({**new_records, "_last_check": time.time()})
    for d in pings:
        when = "closes TODAY" if d["days_left"] == 0 else f"closes in {d['days_left']}d"
        send_telegram_message(os.environ["TELEGRAM_CHAT_ID"],
                              f"⭐ bodyguard: {d['title']} ({d['org']}) — {when}\n{d['url']}")
    for p in passed:
        send_telegram_message(os.environ["TELEGRAM_CHAT_ID"],
                              f"⏰ bodyguard: deadline passed for {p['title']} — "
                              f"unstar when you're done\n{p['url']}")
    if pings:
        event_log.log("alert", channel="telegram", trigger="bodyguard", pings=len(pings))
    return len(pings)
