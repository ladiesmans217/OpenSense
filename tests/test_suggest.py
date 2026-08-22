"""/suggest: the radar proposes its own expansion, with one-tap buttons."""
import pipeline.bot as bot_mod
from pipeline.bot import Bot, load_suggest_state, save_suggest_state
from pipeline.source_ops import BACKLOG, existing_names, pick_candidates


def test_pick_candidates_basic_filtering():
    picks = pick_candidates({"attempted": [], "skipped": []}, set())
    assert len(picks) == 3
    idxs = [i for i, _ in picks]
    assert idxs == sorted(idxs)                    # backlog order preserved
    names = [c["name"] for _, c in picks]
    assert "outreachy" in names                    # safest first


def test_pick_candidates_excludes_done_and_existing():
    state = {"attempted": ["outreachy"], "skipped": ["gsoc"]}
    picks = pick_candidates(state, {"cutshort"})
    names = [c["name"] for _, c in picks]
    assert "outreachy" not in names and "gsoc" not in names and "cutshort" not in names


def test_pick_candidates_kind_filter():
    picks = pick_candidates({"attempted": [], "skipped": []}, set(), kind="scholarship")
    assert {c["kind"] for _, c in picks} == {"scholarship"}
    assert pick_candidates({"attempted": [], "skipped": []}, set(), kind="job",
                           n=99)  # all job kinds available


def test_backlog_entries_are_not_denied():
    from pipeline.source_ops import deny_reason
    for c in BACKLOG:
        assert deny_reason(c["url"]) is None, c["name"]


def test_suggest_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_mod, "SUGGEST_STATE", tmp_path / "suggest.json")
    save_suggest_state({"attempted": ["x"], "skipped": []})
    assert load_suggest_state() == {"attempted": ["x"], "skipped": []}


def _bot_with(captured):
    bot = Bot(token="x", admin_ids={7})
    bot.send = lambda cid, text, buttons=None, rich=False: \
        captured.setdefault("m", []).append((text, buttons))
    return bot


def test_cmd_suggest_sends_buttons(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_mod, "SUGGEST_STATE", tmp_path / "suggest.json")
    monkeypatch.setattr(bot_mod, "source_ops", bot_mod.source_ops)
    captured = {}
    _bot_with(captured).cmd_suggest(1, "")
    text, buttons = captured["m"][0]
    assert "to onboard" in text and "outreachy" in text
    assert len(buttons) == 3                        # one [Add, Skip] row per pick
    add_btn, skip_btn = buttons[0]
    assert add_btn["callback_data"].startswith("sg_add:")
    assert skip_btn["callback_data"] == "sg_skip:0"


def test_cmd_suggest_bad_kind():
    captured = {}
    _bot_with(captured).cmd_suggest(1, "banana")
    assert "kinds:" in captured["m"][0][0]


def test_suggest_skip_marks_and_replies(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_mod, "SUGGEST_STATE", tmp_path / "suggest.json")
    captured = {}
    _bot_with(captured)._suggest_skip(1, 0)
    assert "skipped" in captured["m"][0][0].lower()
    assert load_suggest_state()["skipped"] == [BACKLOG[0]["name"]]
    # skipped entries stop being offered
    picks = pick_candidates(load_suggest_state(), set())
    assert BACKLOG[0]["name"] not in [c["name"] for _, c in picks]


def test_suggest_add_queues_the_ladder(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_mod, "SUGGEST_STATE", tmp_path / "suggest.json")
    captured = {}
    bot = _bot_with(captured)
    jobs = []
    bot.pool = type("StubPool", (), {"submit": staticmethod(
        lambda fn, *a, **k: jobs.append(fn))})()
    monkeypatch.setattr(bot_mod.source_ops, "add_source",
                        lambda url, kind: ("added", f"✅ {url}"))
    bot._suggest_add(1, 0)
    assert load_suggest_state()["attempted"] == [BACKLOG[0]["name"]]
    assert "onboarding" in captured["m"][0][0]
    assert len(jobs) == 1
    jobs[0]()                                       # worker runs → verdict follows
    assert any("✅" in t for t, _ in captured["m"])


def test_callback_from_non_admin_rejected():
    calls, sent = [], []
    bot = Bot(token="x", admin_ids={7})
    bot.call = lambda method, payload: calls.append(method) or {}
    bot.send = lambda cid, text, buttons=None, rich=False: sent.append(text)
    bot.dispatch({"callback_query": {
        "id": "cbq1", "data": "sg_add:0",
        "from": {"id": 999},
        "message": {"chat": {"id": 1}}}})
    assert "answerCallbackQuery" in calls           # the tap is acknowledged…
    assert any("not authorized" in t for t in sent) # …but the door stays shut
    assert "onboarding" not in " ".join(sent)


def test_callback_from_admin_routes(monkeypatch):
    bot = Bot(token="x", admin_ids={7})
    bot.call = lambda method, payload: {}
    routed = []
    monkeypatch.setattr(bot, "_suggest_skip", lambda cid, idx: routed.append(idx))
    bot.dispatch({"callback_query": {
        "id": "cbq1", "data": "sg_skip:2",
        "from": {"id": 7},
        "message": {"chat": {"id": 1}}}})
    assert routed == [2]
