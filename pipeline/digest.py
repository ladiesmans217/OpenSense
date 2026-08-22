"""Delivery: the digest text + Telegram send. A decision arrives; a dashboard doesn't.

Sections, in priority order: ⭐ starred (changes + closing) → ✨ new matches →
⏰ closing this week → top matches, with per-kind counts in the header.
"""
from __future__ import annotations

import os

import requests

from .normalize import days_left
from . import stars as watchlist


def _line(item: dict, extra: str = "") -> str:
    dl = days_left(item.get("deadline"))
    when = ""
    if dl is not None:
        when = " · closes today!" if dl == 0 else (f" · closes in {dl}d" if dl > 0 else "")
    return f"• {item['title']} — {item['org']}{when}{extra}"


def _url(item: dict) -> str:
    return f"  {item['url']}" if item.get("url") else ""


def render(ranked: list[dict], delta: dict, profile: dict,
           signal: dict | None = None) -> str:
    s = delta["summary"]
    by_id = {l["id"]: l for l in ranked}
    kinds: dict[str, int] = {}
    for l in ranked:
        kinds[l["kind"]] = kinds.get(l["kind"], 0) + 1
    kind_counts = " · ".join(f"{v} {k}" for k, v in sorted(kinds.items()))

    out = [
        "📡 OpenSense radar",
        f"{s['total_live']} live listings ({kind_counts})",
        f"{s['new']} new · {s['closing_this_week']} close this week · "
        f"{s.get('starred_changed', 0)} starred changes",
    ]
    if signal:
        from .trends import render_signal
        out.append(render_signal(signal))
    out.append("")

    starred = {i for i in watchlist.starred_ids() if i in by_id}
    if starred:
        changed = [c for c in delta.get("changed", []) if c["id"] in starred]
        closing = [c for c in delta.get("closing_this_week", []) if c["id"] in starred]
        if changed or closing:
            out.append("⭐ STARRED")
            for c in changed:
                item = by_id[c["id"]]
                out.append(_line(item, f" · was {c['was'].get('deadline') or '—'} → "
                                  f"{c['now'].get('deadline') or '—'}"))
            for c in closing:
                out.append(_line(by_id[c["id"]]))
            out.append("")

    new_matched = [l for l in delta.get("new", [])
                   if l.get("match", 0) >= profile.get("min_match_score", 1)]
    if new_matched:
        out.append("✨ NEW")
        for item in new_matched[:8]:
            out.append(_line(item, f" · match {item['match']}"))
            out.append(_url(item))
        out.append("")

    if delta.get("closing_this_week"):
        out.append("⏰ CLOSING THIS WEEK")
        for c in delta["closing_this_week"][:6]:
            star = " ⭐" if c["id"] in starred else ""
            out.append(f"• {c['title']} ({c['days_left']}d){star}")
        out.append("")

    top = [l for l in ranked
           if l["match"] >= profile.get("min_match_score", 1)][:profile.get("top_n_digest", 10)]
    if not top:
        top = ranked[:5]
    out.append("🎯 TOP MATCHES")
    for item in top:
        out.append(_line(item, f" · match {item['match']}"))
        out.append(_url(item))
    return "\n".join(out)


def send_telegram(text: str) -> str:
    """Send via Telegram if configured; otherwise print. Returns the channel used."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not (token and chat_id):
        print("\n--- digest (TELEGRAM_* not set, printing only) ---\n" + text)
        return "stdout"
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    ).raise_for_status()
    return "telegram"
