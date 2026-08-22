"""Profile matching: rank listings against config/profile.yaml.

Deliberately rule-based and explainable — the AI-disclosure rule means every ranking
decision must be arguable in one sentence. An LLM summarizer can sit on top later, but
the score itself stays transparent.
"""
from __future__ import annotations

import yaml
from pathlib import Path

from .normalize import days_left

PROFILE = Path(__file__).resolve().parent.parent / "config" / "profile.yaml"


def load_profile() -> dict:
    return yaml.safe_load(PROFILE.read_text("utf-8")) or {}


def score(listing: dict, profile: dict) -> int:
    text = " ".join([listing.get("title", ""), listing.get("location", ""),
                     " ".join(listing.get("tags", [])), listing.get("kind", "")]).lower()
    hits = 0
    for skill in profile.get("skills", []):
        if skill.lower() in text:
            hits += 2
    for role in profile.get("roles", []):
        if role.lower() in text:
            hits += 2
    for loc in profile.get("locations", []):
        if loc.lower() in text:
            hits += 1
    for interest in profile.get("interests", []):
        if interest.lower() in text:
            hits += 1
    # pathway: hackathons/competitions whose prizes lead to jobs score up for
    # job/internship seekers ("win this → get hired")
    wants_work = any(k in ("job", "internship") for k in profile.get("kinds", [])) or not profile.get("kinds")
    if listing.get("pathway") and wants_work:
        hits += 3
    return hits


def rank(listings: list[dict], profile: dict | None = None) -> list[dict]:
    profile = profile or load_profile()
    wanted_kinds = set(profile.get("kinds") or [])
    pool = [l for l in listings if not wanted_kinds or l.get("kind") in wanted_kinds]
    ranked = sorted(
        (dict(item, match=score(item, profile)) for item in pool),
        key=lambda l: (-l["match"], days_left(l.get("deadline")) or 999),
    )
    return ranked
