"""Entity resolution: the same opportunity posted on three sources is one listing.

Pass 1 — exact key (normalized title + org) merged field-wise.
Pass 2 — fuzzy title match, guarded: only merges when kind matches AND the two rows share
an org, a deadline, or a URL. The guard matters — "Software Engineer Intern" exists at
every company simultaneously; identical titles at different orgs are different listings.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.88


def _key(listing: dict) -> str:
    stop = re.compile(
        r"\b(intern(ship)?|junior|sr|senior|2026|remote|hybrid|bangalore|bengaluru|india)\b")
    title = stop.sub("", listing["title"].lower())
    title = re.sub(r"[^a-z0-9 ]", "", title).strip()
    return f"{title}|{listing['org'].lower()}|{listing.get('kind', '')}"


def _similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= FUZZY_THRESHOLD


def _merge(old: dict, new: dict) -> dict:
    """Keep earliest first_seen, best (earliest) deadline, fill blanks, union sources."""
    merged = dict(old)
    merged["first_seen"] = min(old["first_seen"], new["first_seen"])
    for field in ("url", "stipend", "location", "posted_at"):
        if not merged.get(field) and new.get(field):
            merged[field] = new[field]
    if new.get("deadline") and (not merged.get("deadline")
                                or new["deadline"] < merged["deadline"]):
        merged["deadline"] = new["deadline"]
    srcs = {old["source"], new["source"]}
    if len(srcs) > 1:
        merged["source"] = ", ".join(sorted(srcs))     # cross-source corroboration
    merged["tags"] = sorted(set(old.get("tags", [])) | set(new.get("tags", [])))
    return merged


def dedup(listings: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for item in listings:
        k = _key(item)
        by_key[k] = _merge(by_key[k], item) if k in by_key else item

    merged_any = True
    while merged_any:                                       # pass 2: fuzzy chains, guarded
        merged_any = False
        keys = list(by_key)
        for i, ka in enumerate(keys):
            if ka not in by_key:
                continue
            for kb in keys[i + 1:]:
                if kb not in by_key:
                    continue
                a, b = by_key[ka], by_key[kb]
                if a.get("kind") != b.get("kind"):
                    continue
                corroborated = (
                    a["org"].lower() == b["org"].lower()
                    or (bool(a.get("deadline")) and a["deadline"] == b.get("deadline"))
                    or (bool(a.get("url")) and a["url"] == b.get("url"))
                )
                if corroborated and _similar(a["title"], b["title"]):
                    by_key[ka] = _merge(a, b)
                    del by_key[kb]
                    merged_any = True
    return list(by_key.values())
