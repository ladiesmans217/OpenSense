"""Normalize heterogeneous collector outputs into the OpenSense unified schema.

This is where '100 different layouts' become one dataset. Per-source field maps live in
config/sources.yaml; this module applies them, cleans text, parses deadlines, and stamps
provenance — every row remembers which source and collector produced it (lineage).
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone

UNIFIED_KEYS = ["id", "title", "org", "kind", "url", "location", "stipend",
                "deadline", "posted_at", "tags", "source", "collector_id",
                "first_seen", "last_seen"]

_MONTHS = {m.lower()[:3]: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


_NOISE = re.compile(
    r"(privacy|terms|cookie|code of conduct|contact|about|login|sign up|careers at|"
    r"press|blog$)", re.I)


def parse_deadline(raw: str | None) -> str:
    """Best-effort ISO date from the wild formats real listing pages use."""
    raw = _clean(raw)
    if not raw:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})[\s\-/]([A-Za-z]{3,})[\s\-/]?(\d{2,4})?", raw)
    if m:
        day, mon, year = m.group(1), _MONTHS.get(m.group(2)[:3].lower()), m.group(3)
        if mon:
            year = int(year) if year else date.today().year
            if year < 100:
                year += 2000
            return f"{year:04d}-{mon:02d}-{int(day):02d}"
    m = re.match(r"([A-Za-z]{3,})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?", raw)
    if m:
        mon, day, year = _MONTHS.get(m.group(1)[:3].lower()), m.group(2), m.group(3)
        if mon:
            year = int(year) if year else date.today().year
            if year < 100:
                year += 2000
            return f"{year:04d}-{mon:02d}-{int(day):02d}"
    return ""


def days_left(deadline_iso: str) -> int | None:
    if not deadline_iso:
        return None
    try:
        return (date.fromisoformat(deadline_iso) - date.today()).days
    except ValueError:
        return None


def listing_id(title: str, org: str, url: str) -> str:
    return hashlib.sha1(f"{title.lower()}|{org.lower()}|{url}".encode()).hexdigest()[:12]


_ALIASES = {
    "title": ("title", "name", "role", "job_title", "job_name", "position"),
    "url": ("url", "link", "job_url", "listing_url", "apply_url"),
    "location": ("location", "job_location", "place", "city"),
    "deadline": ("deadline", "last_date", "application_deadline", "apply_by", "due_date"),
    "stipend": ("stipend", "salary", "compensation", "stipend_range"),
    "posted_at": ("posted_at", "date", "published_at", "posted_on"),
    "org": ("org", "company", "organization", "company_name"),
    "tags": ("tags", "skills", "category"),
}


def _pick(field: str, field_map: dict, lower: dict) -> str | list | None:
    """field_map first (per-source, from real collector output), then alias fallbacks."""
    for key in (field_map.get(field), *_ALIASES.get(field, ())):
        if key and key.lower() in lower:
            return lower[key.lower()]
    return None


_KIND_PATTERNS = [
    ("hackathon", re.compile(r"hackathon|hack fest|ideathon|buildathon", re.I)),
    ("scholarship", re.compile(r"scholarship|fellowship|grant|stipend program|financial aid", re.I)),
    ("bounty", re.compile(r"competition|challenge|bounty|contest|prize pool|datathon|case study", re.I)),
    ("event", re.compile(r"meetup|conference|workshop|webinar|summit|tech talk", re.I)),
    ("internship", re.compile(r"\bintern(ship)?s?\b|trainee|apprentice|summer 20\d\d|winter 20\d\d", re.I)),
    ("job", re.compile(r"\bengineer\b|\bdeveloper\b|\bmanager\b|\banalyst\b|\bdesigner\b|"
                       r"\bscientist\b|\barchitect\b|\bspecialist\b|\bconsultant\b|\blead\b|"
                       r"\bsenior\b|\bstaff\b|\bhead of\b", re.I)),
]


def classify_kind(title: str, default: str = "event") -> str:
    """Per-listing kind from the title (aggregators mix kinds on one page);
    the source-level kind is only the fallback."""
    for kind, pattern in _KIND_PATTERNS:
        if pattern.search(title or ""):
            return kind
    return default


def _flatten(rows: list[dict]) -> list[dict]:
    """Long-tail reality: some collectors return rows that wrap a LIST of records
    (e.g. devfolio: one row per page-section with a `hackathons` array inside).
    Expand each wrapped record into its own row, inheriting the parent's scalars."""
    out: list[dict] = []
    for row in rows:
        nested = [(k, v) for k, v in row.items()
                  if isinstance(v, list) and v and isinstance(v[0], dict)]
        if not nested:
            out.append(row)
            continue
        base = {k: v for k, v in row.items()
                if not isinstance(v, (list, dict)) or k == "input"}
        for _key, records in nested:
            for record in records:
                if isinstance(record, dict):
                    out.append({**base, **record})
    return out


def normalize_rows(source_cfg: dict, rows: list[dict]) -> list[dict]:
    fmap = source_cfg.get("field_map") or {}
    rows = _flatten(rows)
    org = source_cfg["name"].replace("-", " ").replace("careers", "").strip()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    out: list[dict] = []

    for row in rows:
        lower = {str(k).lower(): v for k, v in row.items()}
        title = _clean(_pick("title", fmap, lower))
        url = _clean(_pick("url", fmap, lower)) or source_cfg.get("seed_url", "")
        if not title or _NOISE.search(title) or _NOISE.search(url):
            continue          # noise (privacy/terms/etc.) or a row without a title
        if len(title) > 120:
            continue          # quality gate: concatenated multi-listing rows (see freshworks)
        # personal data stays out at extraction time (recruiter names etc.)
        for personal in ("recruiter", "contact_email", "hr_name", "email"):
            lower.pop(personal, None)
        deadline = parse_deadline(_clean(_pick("deadline", fmap, lower)))
        tags_raw = _pick("tags", fmap, lower)
        tags = [t.strip() for t in str(tags_raw or "").split(",") if t.strip()]
        out.append({
            "id": listing_id(title, org, url),
            "title": title,
            "org": _clean(_pick("org", fmap, lower)) or org.title(),
            "kind": classify_kind(title, source_cfg.get("kind", "event")),
            "url": url,
            "location": _clean(_pick("location", fmap, lower)).replace("\n", " "),
            "stipend": _clean(_pick("stipend", fmap, lower)),
            "deadline": deadline,
            "posted_at": _clean(_pick("posted_at", fmap, lower)),
            "tags": tags,
            "source": source_cfg["name"],
            "collector_id": source_cfg.get("collector_id") or "",
            "first_seen": now,
            "last_seen": now,
        })
    return out
