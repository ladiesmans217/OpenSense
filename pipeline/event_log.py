"""Append-only event log — the spine of OpenSense.

Every observable step (run start, collector trigger, row counts, failures, heals, alerts,
run end) is appended here, never updated in place. The dashboard, the delta engine, and the
demo video all read from this single event stream — the same design idea as DeepSeek
Harness's session log: if it reached the product, it must be reconstructable from the log.

Storage: SQLite (queryable) + data/events.jsonl (mirror: diffable, git-friendly, and what
the dashboard fetches).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "events.db"
JSONL = DATA / "events.jsonl"

KINDS = {
    "run_start", "source_trigger", "source_result", "source_fail",
    "normalize", "dedup", "delta", "heal", "enrich", "alert", "run_end",
    "source_op", "bot", "profile_update",
}

_schema = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    source TEXT,
    status TEXT,
    detail TEXT
);
"""


def _connect() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute(_schema)
    return conn


def log(kind: str, *, source: str | None = None, status: str = "ok", **detail) -> dict:
    """Append one event. Returns the event dict (also written to the JSONL mirror)."""
    if kind not in KINDS:
        raise ValueError(f"unknown event kind: {kind}")
    event = {
        "ts": round(time.time(), 3),
        "kind": kind,
        "source": source,
        "status": status,
        "detail": detail,
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO events (ts, kind, source, status, detail) VALUES (?,?,?,?,?)",
            (event["ts"], kind, source, status, json.dumps(detail, default=str)),
        )
    with JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")
    return event


def recent(limit: int = 200) -> list[dict]:
    """Newest-first events for the dashboard timeline."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, kind, source, status, detail FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"ts": r[0], "kind": r[1], "source": r[2], "status": r[3],
         "detail": json.loads(r[4] or "{}")}
        for r in rows
    ]


def last_run_summary() -> dict:
    """Cheap stats for the dashboard header cards."""
    events = recent(500)
    triggers = [e for e in events if e["kind"] == "source_trigger"]
    fails = [e for e in events if e["kind"] == "source_fail"]
    heals = [e for e in events if e["kind"] == "heal"]
    return {
        "sources_triggered": len(triggers),
        "source_failures": len(fails),
        "heals": len(heals),
        "last_event_ts": events[0]["ts"] if events else None,
    }
