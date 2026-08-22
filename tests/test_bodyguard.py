"""Deadline bodyguard: window edges, daily dedupe, the one-time passed notice."""
from datetime import date, timedelta

from pipeline.bodyguard import WINDOW_DAYS, due, plan_messages

TODAY = date.today()


def _dl(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _l(lid, days, starred, title="x"):
    return {"id": lid, "title": title, "org": "org", "url": "https://x.io/" + lid,
            "deadline": _dl(days)}


def test_due_window_edges():
    listings = [_l("a", 0, True), _l("b", 3, True), _l("c", 4, True),
                _l("d", -1, True), _l("e", 1, False)]
    ids = [d["id"] for d in due(listings, {"a", "b", "c", "d"})]
    assert ids == ["a", "b"]                        # 0 and 3 in; 4, past, unstarred out


def test_due_sorted_soonest_first():
    listings = [_l("late", 3, True), _l("soon", 1, True)]
    assert [d["days_left"] for d in due(listings, {"late", "soon"})] == [1, 3]


def test_pings_once_per_day_then_again_next_day():
    listings = [_l("a", 2, True)]
    starred = {"a"}
    d = due(listings, starred)
    today = TODAY.isoformat()
    p1, _, s1 = plan_messages(d, listings, starred, {}, today)
    assert len(p1) == 1 and p1[0]["id"] == "a"
    p2, _, s2 = plan_messages(d, listings, starred, s1, today)      # same day: silent
    assert p2 == []
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    p3, _, s3 = plan_messages(d, listings, starred, s2, tomorrow)   # next day: ping
    assert len(p3) == 1


def test_passed_notice_exactly_once_and_only_if_pinged_before():
    listings = [_l("a", -1, True), _l("stale", -700, True)]
    starred = {"a", "stale"}
    # day 1: 'a' was inside the window and got pinged; 'stale' never was
    prev_state = {"a": {"last_ping": (TODAY - timedelta(days=2)).isoformat(),
                        "passed_notified": False}}
    _, passed, state = plan_messages([], listings, starred, prev_state,
                                     TODAY.isoformat())
    assert [p["id"] for p in passed] == ["a"]       # stale 2019-style rows stay quiet
    _, passed2, _ = plan_messages([], listings, starred, state, TODAY.isoformat())
    assert passed2 == []                            # one notice, ever


def test_unstarred_items_drop_out_of_state():
    listings = [_l("a", 2, True)]
    _, _, state = plan_messages(due(listings, {"a"}), listings, {"a"}, {},
                                TODAY.isoformat())
    assert "a" in state
    _, _, state2 = plan_messages(due(listings, set()), listings, set(), state,
                                 TODAY.isoformat())
    assert "a" not in state2                        # no ghosts


def test_window_constant_is_three_days():
    assert WINDOW_DAYS == 3
