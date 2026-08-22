"""Deadline enrichment: the Discovery + PDP pattern.

Listing cards rarely show deadlines; detail pages do. Each run picks a few
deadline-less listings (newest first), batch-triggers the detail (PDP) collector
with their URLs, and merges the parsed deadline back into the unified rows —
which the delta engine then reports as a deadline change.

State in data/enriched.json remembers attempted ids so persistent failures
don't burn credits every run.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from . import event_log
from .brightdata import BrightData
from .normalize import parse_deadline

ROOT = Path(__file__).resolve().parent.parent
ENRICHED = ROOT / "data" / "enriched.json"
PER_RUN_CAP = 5
ALIASES = ("application_deadline", "application deadline", "deadline",
           "registration_end_date", "registration end date", "last_date", "end_date")


def _load_state() -> dict:
    if ENRICHED.exists():
        return json.loads(ENRICHED.read_text("utf-8"))
    return {"attempted": {}, "filled": {}}


def _save_state(state: dict) -> None:
    ENRICHED.parent.mkdir(exist_ok=True)
    ENRICHED.write_text(json.dumps(state, indent=1), "utf-8")


def parse_relative_deadline(text: str) -> str:
    """Devfolio-style countdowns render relative deadlines. Two formats in the wild:
    'Applications close in 12 days 4 hours' and the compact '5d:6h:22m'.
    Convert to an estimated ISO date (today + N days)."""
    text = text or ""
    m = re.search(r"(\d+)\s*d(?::|\b)", text) or re.search(
        r"(?:close[sd]?\s*in|ends?\s*in|in)\s+(\d+)\s*day", text, re.I)
    if m:
        return (date.today() + timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\s*h(?::|\b)", text) or re.search(
        r"(?:close[sd]?\s*in|ends?\s*in|in)\s+(\d+)\s*hour", text, re.I)
    if m:
        return (date.today() + timedelta(hours=int(m.group(1)))).isoformat()
    return ""


def _pick_deadline(row: dict) -> str:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in ALIASES:
        if alias in lower:
            raw = str(lower[alias])
            parsed = parse_deadline(raw) or parse_relative_deadline(raw)
            if parsed:
                return parsed
    # countdown text sometimes lives in a sibling field — scan the whole row
    for value in lower.values():
        if isinstance(value, str):
            relative = parse_relative_deadline(value)
            if relative:
                return relative
    return ""


_PATHWAY = re.compile(r"intern\w*|ppo|pre[- ]?placement|\bjobs?\b|hired|hiring|"
                      r"interview|offer\s+letter|employment", re.I)


def _pathway_flag(row: dict) -> bool:
    """Prizes/description say winning leads to a job or internship."""
    return any(isinstance(v, str) and _PATHWAY.search(v) for v in row.values())


def enrich(listings: list[dict], cfg: dict) -> int:
    """Fill missing deadlines via the detail collector. Returns count enriched."""
    collector_id = cfg.get("collector_id")
    if not collector_id:
        return 0
    state = _load_state()

    candidates = [
        l for l in listings
        if not l.get("deadline")
        and l.get("kind") in cfg.get("kinds", ["hackathon", "bounty", "event"])
        and l.get("url", "").startswith("http")
        and any(p in l["url"] for p in cfg.get("url_patterns", [""]))  # detail-collector scope
        and state["attempted"].get(l["id"], 0) < 2
    ]
    candidates.sort(key=lambda l: l["first_seen"], reverse=True)
    candidates = candidates[:PER_RUN_CAP]
    if not candidates:
        return 0

    event_log.log("enrich", status="started", targets=len(candidates))
    filled = 0
    try:
        rows = BrightData().run(collector_id, inputs=[l["url"] for l in candidates])
    except Exception as exc:
        event_log.log("enrich", status="fail", error=str(exc))
        print(f"[enrich] detail collector failed: {exc}")
        return 0

    by_input_url = {}
    for row in rows:
        input_url = ((row.get("input") or {}).get("url")
                     if isinstance(row.get("input"), dict) else None)
        if input_url:
            by_input_url[input_url] = row

    for listing in candidates:
        state["attempted"][listing["id"]] = state["attempted"].get(listing["id"], 0) + 1
        row = by_input_url.get(listing["url"])
        deadline = _pick_deadline(row) if row else ""
        if deadline:
            listing["deadline"] = deadline
            state["filled"][listing["id"]] = deadline
            filled += 1
            print(f"[enrich] {listing['title'][:40]} → deadline {deadline}")
        if row and _pathway_flag(row):
            listing["pathway"] = True       # win this → job/internship offer

    _save_state(state)
    event_log.log("enrich", status="done", targets=len(candidates), filled=filled)
    return filled
