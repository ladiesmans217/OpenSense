"""/find: search the live radar from the phone."""
import json

import pipeline.bot as bot_mod
from pipeline.bot import Bot, KIND_ICONS, find_listings, load_latest


def _l(title, org="", kind="job", loc="", tags=(), match=0, url="https://x.io/1",
       deadline=""):
    return {"id": title, "title": title, "org": org, "kind": kind, "location": loc,
            "tags": list(tags), "match": match, "url": url, "deadline": deadline}


LISTINGS = [
    _l("ML Research Intern", "IISc", "internship", "Bangalore", ["machine learning"], 5),
    _l("Frontend Developer", "Acme", "job", "Remote", ["react"], 2),
    _l("ML Hackathon 2026", "Devfolio", "hackathon", "Bangalore", [], 1),
    _l("Data Analyst", "Flipkart", "job", "Bangalore", ["sql"], 3),
    _l("Backend Intern", "Razorpay", "internship", "Remote", ["python"], 4),
]


def test_find_and_semantics_and_ranking():
    hits = find_listings("ml intern bangalore", LISTINGS)
    titles = [h["title"] for h in hits]
    assert "ML Research Intern" in titles           # every term hits
    assert "Backend Intern" not in titles            # no bangalore, no ml
    assert "ML Hackathon 2026" not in titles         # no intern
    assert titles[0] == "ML Research Intern"         # strongest term hits


def test_find_singular_matches_plural_query():
    hits = find_listings("internships", LISTINGS)
    assert {h["kind"] for h in hits} == {"internship"}


def test_find_limit_and_empty():
    assert find_listings("job", LISTINGS, limit=1) and \
        len(find_listings("job", LISTINGS, limit=1)) == 1
    assert find_listings("quantum blockchain tokyo", LISTINGS) == []
    assert find_listings("", LISTINGS) == []
    assert find_listings("a  of", LISTINGS) == []    # terms under 2 chars dropped


def test_find_ranks_by_weights_then_match():
    hits = find_listings("bangalore", LISTINGS)
    # three Bangalore listings, all weight-1 location hits → match score breaks ties
    assert hits[0]["title"] == "ML Research Intern" and hits[0]["match"] == 5


# ── command-level: usage, hits, escaping ─────────────────────────────────────

def _bot_with(captured):
    bot = Bot(token="x", admin_ids={7})
    bot.send = lambda cid, text, buttons=None, rich=False: \
        captured.setdefault("t", []).append(text)
    return bot


def test_cmd_find_usage_without_query():
    captured = {}
    _bot_with(captured).cmd_find(1, "")
    assert "usage" in captured["t"][0]


def test_cmd_find_formats_and_escapes(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_mod, "LATEST", tmp_path / "latest.json")
    (tmp_path / "latest.json").write_text(json.dumps(
        {"listings": [_l("Python <Intern> @ <Org>", kind="internship",
                         deadline="2099-01-01")]}), "utf-8")
    captured = {}
    _bot_with(captured).cmd_find(1, "python")
    text = captured["t"][0]
    assert "1 hits" in text and KIND_ICONS["internship"] in text
    assert "&lt;Intern&gt;" in text and "<Intern>" not in text   # escaped
    assert "closes in" in text and "https://x.io/1" in text


def test_cmd_find_no_hits_suggests(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_mod, "LATEST", tmp_path / "latest.json")
    (tmp_path / "latest.json").write_text(json.dumps({"listings": [_l("x")]}), "utf-8")
    captured = {}
    _bot_with(captured).cmd_find(1, "quantum tokyo")
    assert "no hits" in captured["t"][0]


def test_load_latest_missing_file_is_empty():
    assert load_latest() == [] or isinstance(load_latest(), list)
