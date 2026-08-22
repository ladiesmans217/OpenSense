"""Trends: weekly signal, daily series, source health scores."""
from datetime import datetime, timedelta, timezone

from pipeline.trends import (daily_series, health_scores, render_signal,
                             weekly_signal)


def _l(days_ago: int, kind: str = "job", source: str = "src", first: str | None = None):
    # stamp from the UTC calendar date exactly days_ago back — deterministic
    # regardless of the local clock (India is UTC+5:30; around midnight the
    # local and UTC dates diverge)
    seen = first or ((datetime.now(timezone.utc).date() - timedelta(days=days_ago))
                     .isoformat() + "T12:00:00Z")
    return {"id": f"{days_ago}{kind}{source}", "title": "t", "kind": kind,
            "source": source, "first_seen": seen}


# ── weekly signal ────────────────────────────────────────────────────────────

def test_weekly_signal_counts_and_pct():
    listings = ([_l(1)] * 5 + [_l(3, "scholarship")] * 3      # this week: 8
                + [_l(10)] * 4)                                # last week: 4
    s = weekly_signal(listings)
    assert s["total"] == 8 and s["prev"] == 4
    assert s["pct"] == 100                                     # +100%
    assert s["by_kind"] == {"job": 5, "scholarship": 3}
    assert s["sources"] >= 1


def test_weekly_signal_divide_by_zero_gives_none():
    s = weekly_signal([_l(2)])
    assert s["prev"] == 0 and s["pct"] is None
    assert "first comparable week" in render_signal(s)


def test_weekly_signal_empty():
    s = weekly_signal([])
    assert s["total"] == 0 and s["pct"] is None
    assert "no new listings" in render_signal(s)


def test_render_signal_rich_and_ascii():
    s = {"total": 38, "prev": 26, "pct": 46, "by_kind": {"internship": 12},
         "sources": 6}
    rich = render_signal(s)
    plain = render_signal(s, rich=False)
    assert "📈" in rich and "↑46%" in rich and "12 internship" in rich
    assert "📈" not in plain and "↑" not in plain and "+46%" in plain
    assert "38 new" in rich and "6 sources" in plain


def test_render_signal_down_and_flat():
    assert "↓10%" in render_signal({"total": 9, "prev": 10, "pct": -10,
                                    "by_kind": {}, "sources": 1})
    assert "flat" in render_signal({"total": 5, "prev": 5, "pct": 0,
                                    "by_kind": {}, "sources": 1})


# ── daily series ─────────────────────────────────────────────────────────────

def test_daily_series_buckets_and_zero_fill():
    series = daily_series([_l(0), _l(0, "hackathon"), _l(2)], days=5)
    assert len(series["dates"]) == 5
    assert series["dates"][-1] == datetime.now(timezone.utc).date().isoformat()
    assert series["new_per_day"][-1] == 2        # today: two listings
    assert series["new_per_day"][-3] == 1        # two days ago
    assert sum(series["new_per_day"]) == 3
    assert series["by_kind"]["hackathon"][-1] == 1


def test_daily_series_ignores_garbage_timestamps():
    series = daily_series([{"kind": "job", "first_seen": "not-a-date"}], days=3)
    assert sum(series["new_per_day"]) == 0


# ── health scores ────────────────────────────────────────────────────────────

def _ev(kind, source):
    return {"kind": kind, "source": source, "status": "ok", "detail": {}}


def test_health_scores_rate_icon_runs():
    events = ([_ev("source_result", "good")] * 19 + [_ev("source_fail", "good")]
              + [_ev("source_result", "ok-src")] * 20
              + [_ev("source_fail", "bad-src")] * 10)
    events.reverse()                             # recent() order: newest first
    h = health_scores(events)
    assert h["good"]["rate"] == 95 and h["good"]["icon"] == "🟢"
    assert h["ok-src"]["rate"] == 100 and h["ok-src"]["icon"] == "🟢"
    assert h["bad-src"]["rate"] == 0 and h["bad-src"]["icon"] == "🔴"
    assert h["good"]["runs"] == 20


def test_health_scores_window_keeps_last_n():
    events = [_ev("source_fail", "s")] * 30 + [_ev("source_result", "s")] * 20
    events.reverse()
    h = health_scores(events, window=20)
    assert h["s"]["runs"] == 20 and h["s"]["rate"] == 100   # only last 20 count


def test_health_scores_ignores_other_kinds():
    assert health_scores([_ev("delta", "s"), {"kind": "source_result",
                                              "source": None}]) == {}
