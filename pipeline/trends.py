"""Trends & health: making the cross-source dataset say something.

Pure functions over the listings (first_seen timestamps) and the event log —
no network, no side effects. weekly_signal/render_signal feed the digest trend
line, health_scores feeds /sources and /status, daily_series feeds the
dashboard sparkline. This is the alt-data pitch made literal: we're the only
ones holding this cross-source time-series.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def _today() -> date:
    """UTC today — first_seen stamps are UTC, so buckets must be too."""
    return datetime.now(timezone.utc).date()


def _seen_date(listing: dict) -> date | None:
    iso = str(listing.get("first_seen") or "")
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def daily_series(listings: list[dict], days: int = 14) -> dict:
    """New listings per day (and per kind) for the last `days` days."""
    today = _today()
    dates = [(today - timedelta(days=i)) for i in range(days - 1, -1, -1)]
    by_date = {d: 0 for d in dates}
    by_kind: dict[str, dict[date, int]] = {}
    for l in listings:
        d = _seen_date(l)
        if d in by_date:
            by_date[d] += 1
            by_kind.setdefault(l.get("kind", "event"), {d2: 0 for d2 in dates})[d] += 1
    return {
        "dates": [d.isoformat() for d in dates],
        "new_per_day": [by_date[d] for d in dates],
        "by_kind": {k: [v[d] for d in dates] for k, v in by_kind.items()},
    }


def weekly_signal(listings: list[dict]) -> dict:
    """This week's new listings vs last week's, per kind. The comparison the
    aggregators can't make because they only ever see one site."""
    today = _today()
    this = {(today - timedelta(days=i)) for i in range(7)}
    prev = {(today - timedelta(days=i)) for i in range(7, 14)}

    n_this = n_prev = 0
    kinds: dict[str, int] = {}
    sources: set[str] = set()
    for l in listings:
        d = _seen_date(l)
        if d in this:
            n_this += 1
            kinds[l.get("kind", "event")] = kinds.get(l.get("kind", "event"), 0) + 1
            sources.add(str(l.get("source", "")).split(",")[0])
        elif d in prev:
            n_prev += 1

    pct = None if n_prev == 0 else round((n_this - n_prev) / n_prev * 100)
    return {"total": n_this, "prev": n_prev, "pct": pct,
            "by_kind": kinds, "sources": len(sources)}


def render_signal(s: dict | None, rich: bool = True) -> str:
    """One human line. rich=True for Telegram/email (emoji + arrows);
    rich=False stays ASCII — reportlab's core fonts are Latin-1 only."""
    if not s or not s.get("total"):
        return ("📉 no new listings this week — the long tail went quiet" if rich
                else "no new listings this week")
    pct = s.get("pct")
    if pct is None:
        cmp_ = "first comparable week"
    elif rich:
        cmp_ = (f"↑{pct}% vs last week" if pct > 0 else
                f"↓{abs(pct)}% vs last week" if pct < 0 else "flat vs last week")
    else:
        cmp_ = f"{pct:+d}% vs last week" if pct else "flat vs last week"
    kinds = " · ".join(f"{v} {k}" for k, v in
                       sorted(s.get("by_kind", {}).items(), key=lambda p: -p[1])[:3])
    head = "📈 this week" if rich else "this week"
    line = f"{head}: +{s['total']} new ({cmp_})"
    if kinds:
        line += f" — {kinds}"
    line += f" · {s.get('sources', 0)} sources contributing"
    return line


def health_scores(events: list[dict], window: int = 20) -> dict[str, dict]:
    """Per-source success rate over its last `window` collector runs
    (source_result vs source_fail events). 🟢 ≥90 · 🟡 ≥60 · 🔴 below."""
    attempts: dict[str, list[bool]] = {}
    for e in reversed(events):          # recent() is newest-first; score chronologically
        if e.get("kind") not in ("source_result", "source_fail") or not e.get("source"):
            continue
        attempts.setdefault(e["source"], []).append(e["kind"] == "source_result")
    out: dict[str, dict] = {}
    for source, runs in attempts.items():
        runs = runs[-window:]
        rate = round(100 * sum(runs) / len(runs))
        icon = "🟢" if rate >= 90 else ("🟡" if rate >= 60 else "🔴")
        out[source] = {"rate": rate, "runs": len(runs), "icon": icon}
    return out


def dashboard_payload(listings: list[dict], events: list[dict]) -> dict:
    """Everything the dashboard's trend card + sparkline needs, one call."""
    signal = weekly_signal(listings)
    return {"daily": daily_series(listings), "weekly": signal,
            "signal": render_signal(signal), "health": health_scores(events)}
