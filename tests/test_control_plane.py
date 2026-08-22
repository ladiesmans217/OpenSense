"""Control-plane tests: deny-list, field-map inference, YAML text ops, notify."""
import json

import pytest
import yaml

from pipeline.bot import Bot, load_watches, save_watches
from pipeline.notify import render_html_digest
from pipeline.source_ops import (DENY_DOMAINS, append_source, deny_reason,
                                 disable_source, infer_field_map,
                                 source_block_text)


# ── deny-list: compliance is a feature ───────────────────────────────────────

def test_linkedin_denied_with_reason():
    reason = deny_reason("https://www.linkedin.com/jobs")
    assert reason and "login-walled" in reason


def test_government_denied():
    assert "government" in deny_reason("https://scholarships.gov.in/")
    assert "government" in deny_reason("https://x.gov.uk/something")


def test_prebuilt_majors_flagged():
    assert "pre-built" in deny_reason("https://www.amazon.in/jobs")


def test_normal_site_passes():
    assert deny_reason("https://hasgeek.com/") is None


# ── field-map inference against real captured shapes ─────────────────────────

def test_infer_from_internshala_keys():
    rows = [{"internship_title": "x", "company_name": "y", "internship_url": "z",
             "location": "l", "stipend": "s", "apply_by": "d"}]
    fm = infer_field_map(rows)
    assert fm.get("title") == "internship_title"
    assert fm.get("org") == "company_name"
    assert fm.get("url") == "internship_url"
    assert fm.get("deadline") == "apply_by"


def test_infer_from_plain_keys():
    fm = infer_field_map([{"title": "a", "url": "b"}])
    assert fm == {"title": "title", "url": "url"}


def test_infer_empty_rows():
    assert infer_field_map([]) == {}


# ── YAML text ops preserve comments and round-trip ───────────────────────────

def test_source_block_is_valid_yaml(tmp_path, monkeypatch):
    from pipeline import source_ops
    monkeypatch.setattr(source_ops, "SOURCES_YAML", tmp_path / "sources.yaml")
    (tmp_path / "sources.yaml").write_text(
        "sources:\n  # a precious post-mortem comment\n  - name: old\n    kind: job\n",
        encoding="utf-8")
    append_source("new-site-jobs", "job", "https://new.site/jobs", "c_test123",
                  {"title": "job_title", "url": "job_url"})
    text = (tmp_path / "sources.yaml").read_text("utf-8")
    assert "a precious post-mortem comment" in text      # comments preserved
    parsed = yaml.safe_load(text)
    names = [s["name"] for s in parsed["sources"]]
    assert names == ["old", "new-site-jobs"]
    new = parsed["sources"][1]
    assert new["collector_id"] == "c_test123" and new["kind"] == "job"


def test_disable_source_flips_enabled(tmp_path, monkeypatch):
    from pipeline import source_ops
    monkeypatch.setattr(source_ops, "SOURCES_YAML", tmp_path / "sources.yaml")
    (tmp_path / "sources.yaml").write_text(
        "sources:\n" + source_block_text("victim-jobs", "job", "https://v.io/j", "c_v",
                                         {"title": "t"}), encoding="utf-8")
    assert disable_source("victim-jobs") is True
    parsed = yaml.safe_load((tmp_path / "sources.yaml").read_text("utf-8"))
    assert parsed["sources"][0]["enabled"] is False
    assert parsed["sources"][0]["collector_id"] == "c_v"  # history kept


def test_append_rejects_duplicates(tmp_path, monkeypatch):
    from pipeline import source_ops
    monkeypatch.setattr(source_ops, "SOURCES_YAML", tmp_path / "sources.yaml")
    (tmp_path / "sources.yaml").write_text("sources:\n", encoding="utf-8")
    append_source("dup", "job", "https://d.io", "c_d", {})
    with pytest.raises(ValueError):
        append_source("dup", "job", "https://d.io", "c_d2", {})


# ── notify ───────────────────────────────────────────────────────────────────

def _listing(**kw):
    base = {"id": "1", "title": "Python Intern", "org": "Acme", "kind": "internship",
            "url": "https://x.io/1", "location": "", "stipend": "", "deadline": "",
            "posted_at": "", "tags": [], "source": "s", "collector_id": "c",
            "first_seen": "t", "last_seen": "t", "match": 3}
    base.update(kw)
    return base


def test_html_digest_sections_and_escaping():
    html = render_html_digest(
        [_listing(title="<script>x</script>"), _listing(kind="hackathon", title="HackX")],
        {"summary": {"total_live": 2, "new": 2}, "closing_this_week": []})
    assert "internships (1)" in html and "hackathons (1)" in html
    assert "<script>" not in html and "&lt;script&gt;" in html   # escaped


def test_watch_roundtrip(tmp_path, monkeypatch):
    import pipeline.bot as bot_mod
    monkeypatch.setattr(bot_mod, "WATCHES", tmp_path / "watches.json")
    save_watches([{"chat_id": 42, "keyword": "gsoc"}])
    assert load_watches() == [{"chat_id": 42, "keyword": "gsoc"}]


# ── bot command parsing ──────────────────────────────────────────────────────

def _bot():
    return Bot(token="x", admin_ids={7})


def test_add_extracts_urls_and_kind():
    captured = {}
    bot = _bot()
    bot.send = lambda cid, text, buttons=None, rich=False: \
        captured.setdefault("text", []).append(text)
    jobs = []
    bot.pool = type("StubPool", (), {"submit": staticmethod(
        lambda fn, *a, **k: jobs.append(fn))})()   # record, don't run
    bot.cmd_add(1, "https://a.io/jobs https://b.io/hacks internships")
    ack = captured["text"][0]
    assert "2" in ack and "site(s)" in ack and "internship" in ack
    assert len(jobs) == 2                            # both sites queued


def test_add_requires_url():
    captured = {}
    bot = _bot()
    bot.send = lambda cid, text, buttons=None, rich=False: \
        captured.setdefault("t", []).append(text)
    bot.cmd_add(1, "nothing here")
    assert "usage" in captured["t"][0]


def test_non_admin_rejected():
    captured = []
    bot = _bot()
    bot.send = lambda cid, text, buttons=None: captured.append(text)
    bot.dispatch({"message": {"chat": {"id": 1}, "from": {"id": 999},
                              "text": "/status"}})
    assert any("not authorized" in t for t in captured)


def test_admin_routes_to_status():
    captured = []
    bot = _bot()
    bot.send = lambda cid, text, buttons=None, rich=False: captured.append(text)
    bot.dispatch({"message": {"chat": {"id": 1}, "from": {"id": 7},
                              "text": "/status"}})
    assert any("status" in t.lower() for t in captured)


def test_greetings_get_friendly_replies():
    captured = []
    bot = _bot()
    bot.send = lambda cid, text, buttons=None, rich=False: captured.append(text)
    for hello in ["hi", "hello!", "NAMASTE", "hey there"]:
        bot.dispatch({"message": {"chat": {"id": 1}, "from": {"id": 7}, "text": hello}})
    assert any("radar" in t or "control plane" in t for t in captured)
    assert not any("unknown command" in t for t in captured)


def test_thanks_get_warm_reply():
    captured = []
    bot = _bot()
    bot.send = lambda cid, text, buttons=None, rich=False: captured.append(text)
    bot.dispatch({"message": {"chat": {"id": 1}, "from": {"id": 7}, "text": "thanks!!"}})
    assert any("anytime" in t for t in captured)


def test_non_greeting_gibberish_still_unknown():
    captured = []
    bot = _bot()
    bot.send = lambda cid, text, buttons=None, rich=False: captured.append((text, rich))
    bot.dispatch({"message": {"chat": {"id": 1}, "from": {"id": 7}, "text": "asdfgh"}})
    text, rich = captured[0]
    assert "didn't catch that" in text
    assert rich is True and "<code>" in text      # same formatted style as /help


# ── telegram formatting: no raw dicts, HTML-escaped dynamics ─────────────────

def test_format_status_is_human_readable():
    from pipeline.bot import format_status
    text = format_status(
        {"sources_triggered": 149, "source_failures": 17, "heals": 6},
        {"detail": {"new": 82, "removed": 36, "total_live": 582,
                    "closing_this_week": 17}})
    assert "582" in text and "82 new" in text and "17 closing" in text
    assert "{" not in text and "}" not in text       # no raw dict dumps
    assert text.startswith("<b>")                    # rich formatting on


def test_format_status_handles_no_runs():
    from pipeline.bot import format_status
    text = format_status({"sources_triggered": 0, "source_failures": 0, "heals": 0}, None)
    assert "live listings" in text and "{" not in text


def test_format_sources_legend_and_escaping():
    from pipeline.bot import format_sources
    text = format_sources({"sources": [
        {"name": "normal-site", "kind": "job", "enabled": True, "collector_id": "c_1"},
        {"name": "weird<script>", "kind": "job", "enabled": False, "collector_id": "c_2"},
    ]})
    assert "🟢 live (1)" in text and "⚪️ benched (1)" in text
    assert "<script>" not in text and "weird&lt;script&gt;" in text


def test_send_rich_flag_reaches_payload():
    sent = []
    bot = _bot()
    bot.call = lambda method, payload: sent.append((method, payload)) or {}
    bot.send(1, "<b>hi</b>", rich=True)
    method, payload = sent[0]
    assert payload.get("parse_mode") == "HTML"
    bot.send(1, "plain")
    assert "parse_mode" not in sent[1][1]


# ── truncation: word-safe, before escaping, never mid-entity ─────────────────

def test_trunc_adds_ellipsis_and_is_word_safe():
    from pipeline.bot import esc, trunc
    long = "concatenated openings into one row caught by the event log in production"
    out = esc(trunc(long, 60))
    assert out.endswith("…") and len(out) <= 65
    assert not out.endswith(("ru", "c "))            # no mid-word chops


def test_trunc_then_escape_never_splits_entities():
    import re
    from pipeline.bot import esc, trunc
    nasty = "a & <b> sold for $5 > cheap; tags: <i> & stuff " * 4
    out = esc(trunc(nasty, 37))
    # invariant: every & in the escaped output opens a COMPLETE entity
    assert not re.search(r"&(?!amp;|lt;|gt;|#)", out)
    assert trunc("short", 60) == "short"


def test_heals_issue_stops_at_paren_full_text_before():
    from pipeline.bot import esc
    raw = "batch runs concatenated openings into one row (caught by event log in production)"
    shown = esc(raw.split("(")[0].rstrip())
    assert shown == "batch runs concatenated openings into one row"
    assert "(" not in shown and not shown.endswith("…")
    # long text without parens is NOT truncated at all
    free = "a very long failure explanation without any parens goes on and on and stays whole"
    assert esc(free.split("(")[0]) == free
