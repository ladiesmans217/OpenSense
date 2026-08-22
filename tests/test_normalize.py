"""Normalization tests — fixtures are the real collector payloads (data/run-*.json)."""
import json
from pathlib import Path

import pytest

from pipeline.normalize import _flatten, normalize_rows, parse_deadline

DATA = Path(__file__).resolve().parent.parent / "data"
ZOHOO_CFG = {
    "name": "zoho-careers", "kind": "internship", "collector_id": "c_test",
    "field_map": {"title": "job_title", "url": "job_url", "location": "location"},
}


# ── parse_deadline: the wild formats real pages use ──────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("2026-09-15", "2026-09-15"),
    ("2026-09-15T23:59:59Z", "2026-09-15"),
    ("15 September 2026", "2026-09-15"),
    ("15 Sep", f"2026-09-15"[:4] + "-09-15"),
    ("August 30, 8:00 PM London time", "2026-08-30"),
    ("Sept 3rd 2026", "2026-09-03"),
    ("", ""),
    ("rolling basis", ""),
    (None, ""),
])
def test_parse_deadline(raw, expected):
    assert parse_deadline(raw) == expected


# ── _flatten: nested + mixed long-tail shapes ────────────────────────────────

def test_flatten_expands_nested_records():
    rows = [{"hackathons": [{"title": "A", "url": "u1"}, {"title": "B", "url": "u2"}],
             "product_page_url": "p"}]
    flat = _flatten(rows)
    assert len(flat) == 2
    assert {r["title"] for r in flat} == {"A", "B"}
    assert all(r["product_page_url"] == "p" for r in flat)   # parent scalars inherited


def test_flatten_skips_strings_in_mixed_lists():
    rows = [{"events": [{"title": "A"}, "noise-string"]}]
    flat = _flatten(rows)
    assert len(flat) == 1 and flat[0]["title"] == "A"


def test_flatten_passthrough_plain_rows():
    rows = [{"job_title": "X", "job_url": "y"}]
    assert _flatten(rows) == rows


# ── gates: noise, concatenation, personal data ───────────────────────────────

def test_noise_gate_drops_privacy_and_terms():
    rows = [{"job_title": "Privacy Policy", "job_url": "https://x.com/privacy"},
            {"job_title": "Terms of Service", "job_url": "https://x.com/terms"},
            {"job_title": "Real Role", "job_url": "https://x.com/jobs/1"}]
    out = normalize_rows(ZOHOO_CFG, rows)
    assert [l["title"] for l in out] == ["Real Role"]


def test_quality_gate_drops_concatenated_rows():
    rows = [{"job_title": "Engineer " * 30, "job_url": "https://x.com/1"}]
    assert normalize_rows(ZOHOO_CFG, rows) == []


def test_personal_fields_stripped():
    rows = [{"job_title": "Role", "job_url": "u", "recruiter": "Bob",
             "contact_email": "bob@x.com"}]
    listing = normalize_rows(ZOHOO_CFG, rows)[0]
    assert "recruiter" not in listing and "email" not in listing


# ── real production fixtures ─────────────────────────────────────────────────

@pytest.mark.parametrize("run_file", ["run-zoho.json", "run-razorpay.json", "run-devfolio.json"])
def test_real_payloads_normalize(run_file):
    rows = json.loads((DATA / run_file).read_text("utf-8"))
    out = normalize_rows(ZOHOO_CFG, rows)
    assert len(out) > 0
    assert all(l["title"] and l["source"] == "zoho-careers" for l in out)


def test_real_devfolio_flattens():
    rows = json.loads((DATA / "run-devfolio.json").read_text("utf-8"))
    cfg = {"name": "devfolio-hackathons", "kind": "hackathon", "collector_id": "c",
           "field_map": {"title": "title", "url": "url"}}
    out = normalize_rows(cfg, rows)
    assert len(out) >= 25                       # 28 raw wrapped records, minus any gated
    assert all(l["kind"] == "hackathon" for l in out)
