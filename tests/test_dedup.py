"""Entity-resolution tests: the guarded fuzzy merge is the load-bearing logic."""
from pipeline.dedup import dedup


def listing(title, org, source="s1", kind="job", deadline="", url=""):
    return {"id": f"{title}-{org}", "title": title, "org": org, "kind": kind,
            "url": url, "location": "", "stipend": "", "deadline": deadline,
            "posted_at": "", "tags": [], "source": source, "collector_id": "c",
            "first_seen": "2026-08-22T00:00:00Z", "last_seen": "2026-08-22T00:00:00Z"}


def test_exact_key_merges_and_unions_sources():
    a = listing("Backend Engineer", "Zoho", source="zoho")
    b = listing("Backend Engineer", "Zoho", source="devfolio", deadline="2026-09-01")
    out = dedup([a, b])
    assert len(out) == 1
    assert out[0]["source"] == "devfolio, zoho"        # cross-source corroboration
    assert out[0]["deadline"] == "2026-09-01"           # best deadline kept


def test_same_title_different_org_does_not_merge():
    out = dedup([listing("Software Engineer Intern", "Zoho"),
                 listing("Software Engineer Intern", "Zomato")])
    assert len(out) == 2                                  # different kind of listing entirely


def test_similar_title_same_deadline_merges():
    out = dedup([listing("SDE Intern (Bangalore)", "Devfolio", kind="hackathon",
                         deadline="2026-09-10", url="u1"),
                 listing("SDE Intern Bangalore", "MLH", kind="hackathon",
                         deadline="2026-09-10", url="u2")])
    assert len(out) == 1


def test_different_kind_never_merges():
    out = dedup([listing("HackNight 2026", "Devfolio", kind="hackathon",
                         deadline="2026-09-10"),
                 listing("HackNight 2026", "Devfolio", kind="event",
                         deadline="2026-09-10")])
    assert len(out) == 2


def test_first_seen_preserved_on_merge():
    a = listing("Role", "Org", source="s1")
    a["first_seen"] = "2026-08-20T00:00:00Z"
    b = listing("Role", "Org", source="s2")
    out = dedup([a, b])
    assert out[0]["first_seen"] == "2026-08-20T00:00:00Z"
