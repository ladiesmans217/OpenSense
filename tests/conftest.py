"""Shared test fixtures.

The event log is the product's source of truth — tests must NEVER write to the
real data/events.db. (This exact leak produced 25 fake `bot auth_reject
user=999` events in the production log: the bot-dispatch tests call the real
dispatcher, which called the real logger.) Every test now gets a throwaway log.
"""
import pytest

from pipeline import event_log


@pytest.fixture(autouse=True)
def _isolated_event_log(tmp_path, monkeypatch):
    monkeypatch.setattr(event_log, "DATA", tmp_path)
    monkeypatch.setattr(event_log, "DB", tmp_path / "events.db")
    monkeypatch.setattr(event_log, "JSONL", tmp_path / "events.jsonl")
