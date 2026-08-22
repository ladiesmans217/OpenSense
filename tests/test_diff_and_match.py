"""Delta engine + matching tests (state file redirected to tmp)."""
import json

from pipeline import diff as diff_mod
from pipeline.diff import compute, save_state
from pipeline.match import rank


def listing(i, title, deadline="", stipend=""):
    return {"id": i, "title": title, "org": "Org", "kind": "job", "url": f"u{i}",
            "location": "", "stipend": stipend, "deadline": deadline, "posted_at": "",
            "tags": [], "source": "s", "collector_id": "c",
            "first_seen": "2026-08-22T00:00:00Z", "last_seen": "2026-08-22T00:00:00Z"}


def test_delta_new_removed_changed(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    monkeypatch.setattr(diff_mod, "STATE", state)
    save_state([listing("a", "A"), listing("b", "B", stipend="₹50k")])

    d = compute([listing("a", "A"), listing("b", "B", stipend="₹60k"),
                 listing("c", "C")])
    s = d["summary"]
    assert s["new"] == 1 and s["removed"] == 0 and s["changed"] == 1
    assert d["new"][0]["id"] == "c"
    assert d["changed"][0]["was"]["stipend"] == "₹50k"
    assert d["changed"][0]["now"]["stipend"] == "₹60k"

    # same sequence run.py uses: compute the delta, then persist the new snapshot
    save_state([listing("a", "A"), listing("b", "B", stipend="₹60k"),
                listing("c", "C")])
    d2 = compute([listing("a", "A")])
    assert d2["summary"]["removed"] == 2


def test_first_seen_survives_across_runs(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    monkeypatch.setattr(diff_mod, "STATE", state)
    old = listing("a", "A")
    old["first_seen"] = "2026-08-01T00:00:00Z"
    save_state([old])
    compute([listing("a", "A")])          # diff preserves provenance in-place
    persisted = json.loads(state.read_text())["listings"][0]
    assert persisted["first_seen"] == "2026-08-01T00:00:00Z"


def test_rank_scores_profile_hits():
    profile = {"skills": ["python"], "roles": ["intern"], "locations": ["remote"],
               "interests": [], "min_match_score": 1}
    hits = listing("1", "Python Intern (Remote)")
    miss = listing("2", "Graphic Designer")
    for l in (hits, miss):
        l["tags"], l["kind"] = [], "job"
    ranked = rank([miss, hits], profile)
    assert ranked[0]["id"] == "1" and ranked[0]["match"] >= 3
    assert ranked[1]["match"] == 0
