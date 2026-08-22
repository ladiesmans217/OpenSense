"""No-login personalization: prompt parsing + profile application.

The dashboard stores the user's profile in localStorage forever (until they edit
it in the Personalize tab) and optionally POSTs it to /api/profile so the next
pipeline run's digest uses it. parse_goal() turns free text ("2nd year, only
internships", "competitions that lead to jobs") into structured adjustments —
deterministic, explainable rules first; an LLM hook can refine later but is
never required.
"""
from __future__ import annotations

import re

VALID_KINDS = {"job", "internship", "hackathon", "bounty", "scholarship", "event"}

_KIND_WORDS = {
    "job": re.compile(r"\bjobs?\b|full[- ]?time|placement|hiring|roles?\b", re.I),
    "internship": re.compile(r"intern(ship)?s?\b|trainee", re.I),
    "hackathon": re.compile(r"hackathons?\b|hackfest", re.I),
    "bounty": re.compile(r"competitions?\b|challenges?\b|bounties\b|contests?\b", re.I),
    "scholarship": re.compile(r"scholarships?\b|fellowships?\b|grants?\b|funding", re.I),
    "event": re.compile(r"\bevents?\b|meetups?\b|conferences?\b|workshops?\b", re.I),
}
_STUDENT_YEAR = re.compile(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|final)\s+year\b", re.I)
_YEAR_NUM = re.compile(r"\byear\s*(1|2|3|4)\b|\b(1st|2nd|3rd|4th)\s+year", re.I)
_PATHWAY = re.compile(r"leads?\s+to\s+(jobs?|intern)|get\s+(hired|a\s+job)|ppo|placement", re.I)
_REMOTE = re.compile(r"\bremote\b|work\s+from\s+home|wfh", re.I)


def parse_goal(text: str) -> dict:
    """Free text → structured profile adjustments. Deterministic and explainable."""
    text = text or ""
    kinds = sorted({k for k, pattern in _KIND_WORDS.items() if pattern.search(text)})
    if _PATHWAY.search(text):
        # "competitions that lead to jobs" → hackathons/bounties with job outcomes
        kinds = sorted(set(kinds) | {"hackathon", "bounty"})
    profile: dict = {}
    if kinds:
        profile["kinds"] = kinds
    if _STUDENT_YEAR.search(text) or _YEAR_NUM.search(text):
        m = _YEAR_NUM.search(text)
        year = (m.group(1) or m.group(2)) if m else None
        if year:
            profile["year"] = int(year.rstrip("stndrh") or year)
        if not profile.get("kinds"):
            profile["kinds"] = ["internship", "hackathon", "bounty", "scholarship"]
        else:  # early-year students rarely want senior full-time filters alone
            profile.setdefault("kinds", [])
    if _REMOTE.search(text):
        profile["locations"] = ["remote"]
    return profile


def apply_goal(base: dict, adjustments: dict) -> dict:
    """Merge parsed goal over the saved profile (goal wins for the keys it sets)."""
    merged = dict(base)
    for key, value in adjustments.items():
        merged[key] = value
    return merged


def sanitize(profile: dict) -> dict:
    """Keep only known keys with sane types — this gets written to config/profile.yaml."""
    out: dict = {}
    if isinstance(profile.get("kinds"), list):
        out["kinds"] = [k for k in profile["kinds"] if k in VALID_KINDS]
    if isinstance(profile.get("skills"), list):
        out["skills"] = [str(s)[:40] for s in profile["skills"][:20]]
    if isinstance(profile.get("roles"), list):
        out["roles"] = [str(r)[:40] for r in profile["roles"][:20]]
    if isinstance(profile.get("locations"), list):
        out["locations"] = [str(l)[:40] for l in profile["locations"][:10]]
    if isinstance(profile.get("interests"), list):
        out["interests"] = [str(i)[:40] for i in profile["interests"][:15]]
    if isinstance(profile.get("goal"), str):
        out["goal"] = profile["goal"][:300]
    if isinstance(profile.get("min_match_score"), int):
        out["min_match_score"] = max(0, min(10, profile["min_match_score"]))
    if isinstance(profile.get("top_n_digest"), int):
        out["top_n_digest"] = max(1, min(30, profile["top_n_digest"]))
    return out
