"""Supplementary API/RSS feed sources.

Public APIs and RSS are explicitly permitted by the hackathon rules; the CORE of
the project stays Scraper Studio collectors — these feeds widen coverage through
the same normalize → dedup → diff path, and every fetch is event-logged with
transport=api so the timeline stays honest about where data comes from.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import requests

from . import event_log

UA = {"User-Agent": "OpenSense/1.0 (hackathon radar)"}
_TIMEOUT = 30

# YouTube channels → public RSS feeds (channel IDs resolved live 2026-08-22)
YOUTUBE_CHANNELS = {
    "youtube-kunal": "UCBGOUQHNNtNGcGzVq5rIXjw",
    "youtube-apnacollege": "UCBwmMxybNva6P_5VmxjzwqA",
    "youtube-codewithharry": "UCeVMnSShP_Iviwkknt83cww",
    "youtube-striver": "UCJskGeByzRRSvmOyZOz61ig",
}
_OPPORTUNITY_WORDS = re.compile(
    r"intern|hackathon|scholarship|competition|fellowship|hiring|job|placement|"
    r"bootcamp|program|apply|open\b", re.I)


def _get(url: str):
    r = requests.get(url, headers=UA, timeout=_TIMEOUT)
    r.raise_for_status()
    return r


# ── JSON job APIs ────────────────────────────────────────────────────────────

def remoteok() -> list[dict]:
    rows = [r for r in _get("https://remoteok.com/api").json() if isinstance(r, dict)]
    return [{"title": r.get("position"), "org": r.get("company"),
             "url": r.get("url"), "location": r.get("location") or "remote",
             "tags": r.get("tags", [])[:5]} for r in rows if r.get("position")]


def remotive() -> list[dict]:
    data = _get("https://remotive.com/api/remote-jobs").json().get("jobs", [])
    return [{"title": j.get("title"), "org": j.get("company_name"),
             "url": j.get("url"), "location": j.get("candidate_required_location") or "remote",
             "kind_hint": "job"} for j in data[:80]]


def workingnomads() -> list[dict]:
    data = _get("https://www.workingnomads.com/api/exposed_jobs/").json()
    return [{"title": j.get("title"), "org": (j.get("company_name") or "").strip(),
             "url": j.get("url"), "location": j.get("location") or "remote"}
            for j in data[:80] if j.get("title")]


# ── RSS ──────────────────────────────────────────────────────────────────────

def wwr_rss() -> list[dict]:
    xml = _get("https://weworkremotely.com/categories/remote-programming-jobs.rss").text
    root = ET.fromstring(xml)
    rows = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        # WWR titles are "Company: Role (Region)"
        org, _, role = title.partition(":")
        rows.append({"title": role.strip() or title, "org": org.strip(),
                     "url": item.findtext("link"), "location": "remote"})
    return rows


def youtube_channel(name: str, channel_id: str, limit: int = 15) -> list[dict]:
    feed = _get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}").text
    root = ET.fromstring(feed)
    rows = []
    for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        if not _OPPORTUNITY_WORDS.search(title):
            continue                       # only opportunity-relevant announcements
        rows.append({
            "title": title,
            "org": name.replace("youtube-", "").replace("-", " ").title(),
            "url": entry.findtext("{http://www.w3.org/2005/Atom}link"),
            "posted_at": (entry.findtext("{http://www.w3.org/2005/Atom}published") or "")[:10],
        })
        if len(rows) >= limit:
            break
    return rows


FEEDS = {
    "remoteok": remoteok,
    "remotive": remotive,
    "workingnomads": workingnomads,
    "wwr-programming": wwr_rss,
}


def fetch_all(include_youtube: bool = True) -> dict[str, list[dict]]:
    """Run every feed; per-feed failures quarantine individually."""
    results: dict[str, list[dict]] = {}
    jobs = dict(FEEDS)
    if include_youtube:
        for name, cid in YOUTUBE_CHANNELS.items():
            jobs[name] = (lambda c=cid: youtube_channel(name, c))
    for name, fn in jobs.items():
        try:
            rows = fn()
            results[name] = rows
            event_log.log("source_result", source=f"api:{name}", transport="api",
                          raw_rows=len(rows), normalized=len(rows))
        except Exception as exc:
            event_log.log("source_fail", source=f"api:{name}", transport="api",
                          status="fail", error=str(exc))
    return results
