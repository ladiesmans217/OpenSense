"""Auto-heal: the pipeline repairs its own scrapers.

Reads the append-only event log to find sources on a failure streak; when a source
has failed `streak_threshold` runs in a row (no successful result between), fires a
Bright Data self-heal with a prompt derived from the latest error, then approves it.

Guardrails — all enforced from the event log, all visible on the timeline:
- one auto-heal per source per 24h
- at most `max_heals_per_run` auto-heals in a single run
- every start/request/failure logged with trigger="auto"
"""
from __future__ import annotations

import time

from . import event_log
from .brightdata import BrightData

STREAK_THRESHOLD = 2
HEAL_COOLDOWN_H = 24
MAX_HEALS_PER_RUN = 2


def failure_streak(source: str) -> int:
    """Consecutive most-recent failures for a source (stops at first success)."""
    streak = 0
    for event in event_log.recent(500):
        if event["source"] != source:
            continue
        if event["kind"] == "source_result":
            break
        if event["kind"] == "source_fail":
            streak += 1
    return streak


def healed_recently(source: str, hours: int = HEAL_COOLDOWN_H) -> bool:
    cutoff = time.time() - hours * 3600
    return any(e["kind"] == "heal" and e["source"] == source and e["ts"] >= cutoff
               for e in event_log.recent(500))


def prompt_for(error: str) -> str:
    """Derive a heal prompt from the failure mode we observed."""
    err = (error or "").lower()
    if "404" in err or "not found" in err:
        return ("The target page moved or returns 404. Find the current listing page "
                "URL for the same content and update the scraper to it, keeping the "
                "same output fields, one row per item.")
    if "timeout" in err or "not ready" in err:
        return ("The page now loads its listing content dynamically and slowly. Wait "
                "for the content to render before extracting, keeping the same output "
                "fields, one row per item.")
    if "400" in err or "missing" in err:
        return ("The trigger input is being rejected. Make the scraper accept the seed "
                "listing URL as input and extract the same fields as before.")
    return ("The scraper is failing on a page whose layout likely changed. Inspect the "
            "current page markup and fix the extraction so it returns the same fields, "
            "one row per item.")


def auto_heal(failures: dict[str, str], sources_by_name: dict[str, dict],
              max_heals: int = MAX_HEALS_PER_RUN) -> list[str]:
    """Heal sources whose streak crossed the threshold. Returns healed source names.

    `failures` maps source name → latest error, collected during this run.
    """
    healed: list[str] = []
    for name, error in failures.items():
        if len(healed) >= max_heals:
            break
        cfg = sources_by_name.get(name) or {}
        if not cfg.get("collector_id"):
            continue
        if failure_streak(name) < STREAK_THRESHOLD or healed_recently(name):
            continue
        event_log.log("heal", source=name, trigger="auto", status="started", error=error)
        try:
            output = BrightData.heal(cfg["collector_id"], prompt_for(error), approve=True)
            event_log.log("heal", source=name, trigger="auto", status="requested",
                          collector_id=cfg["collector_id"],
                          output=(output or "")[-200:])
            healed.append(name)
            print(f"[heal] {name}: auto-heal requested ({prompt_for(error)[:60]}...)")
        except Exception as exc:
            event_log.log("heal", source=name, trigger="auto", status="fail", error=str(exc))
            print(f"[heal] {name}: auto-heal failed — {exc}")
    return healed


def heal_command(source: str, prompt: str, cfg: dict) -> str:
    """Manual heal for one source (the demo flow): heal → approve → same Collector ID."""
    output = BrightData.heal(cfg["collector_id"], prompt, approve=True)
    event_log.log("heal", source=source, trigger="manual", status="requested",
                  collector_id=cfg["collector_id"], prompt=prompt[:120])
    return output
