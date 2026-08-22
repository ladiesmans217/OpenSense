"""Delta engine: what changed since the previous run.

This is what makes the data compound — the demo claim ("3 new since yesterday, 2 close
this week") comes from here, not from a single snapshot.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import stars as watchlist
from .normalize import days_left

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"


def _load_previous() -> dict[str, dict]:
    if STATE.exists():
        return {l["id"]: l for l in json.loads(STATE.read_text("utf-8"))["listings"]}
    return {}


def compute(current: list[dict]) -> dict:
    prev = _load_previous()
    now = {l["id"]: l for l in current}

    new_ids = [i for i in now if i not in prev]
    gone_ids = [i for i in prev if i not in now]
    changed = []
    for i, listing in now.items():
        old = prev.get(i)
        if old and (old.get("deadline") != listing.get("deadline")
                    or old.get("stipend") != listing.get("stipend")):
            changed.append({"id": i, "title": listing["title"],
                            "was": {k: old.get(k) for k in ("deadline", "stipend")},
                            "now": {k: listing.get(k) for k in ("deadline", "stipend")}})
    closing = [
        {"id": i, "title": l["title"], "deadline": l["deadline"], "days_left": days_left(l["deadline"])}
        for i, l in now.items()
        if days_left(l["deadline"]) is not None and 0 <= days_left(l["deadline"]) <= 7
    ]
    closing.sort(key=lambda x: x["days_left"] or 999)

    # preserve first_seen across runs (provenance: when OpenSense first saw each listing)
    for i, listing in now.items():
        if i in prev:
            listing["first_seen"] = prev[i]["first_seen"]

    starred = watchlist.starred_ids()
    starred_changed = [c for c in changed if c["id"] in starred]

    return {
        "summary": {"new": len(new_ids), "removed": len(gone_ids),
                    "changed": len(changed), "closing_this_week": len(closing),
                    "starred_changed": len(starred_changed),
                    "starred_live": len(starred & set(now)),
                    "total_live": len(now)},
        "new": [now[i] for i in new_ids],
        "removed": [{"id": i, "title": prev[i]["title"]} for i in gone_ids],
        "changed": changed,
        "closing_this_week": closing,
    }


def save_state(current: list[dict]) -> None:
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"listings": current}, indent=1), "utf-8")
