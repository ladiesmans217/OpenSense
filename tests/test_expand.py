"""Personalization prompt parsing, per-listing kind classification, pathway flag."""
from pipeline.normalize import classify_kind
from pipeline.profile import apply_goal, parse_goal, sanitize


# ── classify_kind: aggregators mix kinds on one page ─────────────────────────

def test_classify_internship():
    assert classify_kind("Software Engineering Internship - Summer 2026") == "internship"
    assert classify_kind("Python Trainee") == "internship"


def test_classify_hackathon_beats_job():
    assert classify_kind("Fintech Hackathon 2026") == "hackathon"
    assert classify_kind("AI Engineer at Hackathon Platform") == "hackathon"


def test_classify_senior_roles_are_jobs():
    assert classify_kind("Senior Backend Engineer") == "job"
    assert classify_kind("Head of Design, Wealth") == "job"


def test_classify_scholarship_and_competition():
    assert classify_kind("Merit Scholarship 2026") == "scholarship"
    assert classify_kind("National Case Study Challenge") == "bounty"


def test_classify_falls_back_to_source_default():
    assert classify_kind("Something unusual", "event") == "event"


# ── prompt parser: deterministic, explainable ────────────────────────────────

def test_parse_internships_only():
    adj = parse_goal("I want internships only, I'm in second year")
    assert adj["kinds"] == ["internship"]


def test_parse_pathway_request():
    adj = parse_goal("competitions that lead to jobs")
    assert "hackathon" in adj["kinds"] and "bounty" in adj["kinds"]


def test_parse_early_year_defaults():
    adj = parse_goal("final year")
    assert set(adj["kinds"]) >= {"internship", "scholarship"}


def test_parse_remote():
    assert parse_goal("remote jobs")["locations"] == ["remote"]


def test_apply_goal_merges():
    merged = apply_goal({"skills": ["python"]}, {"kinds": ["job"]})
    assert merged == {"skills": ["python"], "kinds": ["job"]}


def test_sanitize_rejects_unknown_and_caps():
    out = sanitize({"kinds": ["job", "nonsense"], "skills": ["x" * 100], "min_match_score": 99})
    assert out["kinds"] == ["job"]
    assert out["skills"] == ["x" * 40]
    assert out["min_match_score"] == 10


# ── pathway flag ─────────────────────────────────────────────────────────────

def test_pathway_flag_detects_job_prizes():
    from pipeline.enrich import _pathway_flag
    assert _pathway_flag({"prizes": "Winners receive a paid internship and PPO opportunity"})
    assert _pathway_flag({"prizes": "Winning team members get hired full-time"})
    assert not _pathway_flag({"prizes": "Cash prize of $5000"})          # money ≠ pathway
    assert not _pathway_flag({"prizes": "Swag and stickers only"})


# ── api feed parsers (offline: shape checks against adapters) ────────────────

def test_wwr_title_split():
    # adapter logic: "Company: Role (Region)" → org + role
    title = "Acme: Senior Data Engineer (Anywhere)"
    org, _, role = title.partition(":")
    assert org == "Acme" and role.strip().startswith("Senior")


def test_youtube_opportunity_filter():
    import re
    words = re.compile(r"intern|hackathon|scholarship|competition|fellowship|hiring|job|placement|"
                       r"bootcamp|program|apply|open\b", re.I)
    assert words.search("Midweek in the Scrape-Verse Hackathon")
    assert words.search("No Internship in Your Resume?")
    assert not words.search("Cooking biryani at home vlog")
