"""Watchlist: listings the user starred (from the dashboard, phone included).

Plain JSON at data/stars.json — id → starred_at. The digest puts starred
changes and starred deadlines above everything else.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STARS = ROOT / "data" / "stars.json"


def load() -> dict[str, str]:
    if STARS.exists():
        return json.loads(STARS.read_text("utf-8"))
    return {}


def save(stars: dict[str, str]) -> None:
    STARS.parent.mkdir(exist_ok=True)
    STARS.write_text(json.dumps(stars, indent=1), "utf-8")


def toggle(listing_id: str) -> bool:
    """Star/unstar. Returns the new state (True = starred)."""
    stars = load()
    if listing_id in stars:
        del stars[listing_id]
        starred = False
    else:
        stars[listing_id] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        starred = True
    save(stars)
    return starred


def starred_ids() -> set[str]:
    return set(load())
