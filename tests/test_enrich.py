"""Relative-deadline parsing (Devfolio countdowns)."""
from datetime import date, timedelta

from pipeline.enrich import parse_relative_deadline


def test_verbose_countdown_days():
    assert parse_relative_deadline("Applications close in 12 days 4 hours") == \
        (date.today() + timedelta(days=12)).isoformat()


def test_compact_countdown():
    assert parse_relative_deadline("Applications close in 5d:6h:22m") == \
        (date.today() + timedelta(days=5)).isoformat()


def test_hours_only():
    assert parse_relative_deadline("ends in 8 hours") == date.today().isoformat()


def test_no_deadline_text():
    assert parse_relative_deadline("Applications close in") == ""
    assert parse_relative_deadline("") == ""
