"""Bright Data client — the Collector ID is the production API.

Token resolution: BRIGHTDATA_API_TOKEN env var (CI / .env) → the local CLI's stored
credentials (~/AppData/Roaming/brightdata-cli/credentials.json on Windows,
~/.config/brightdata-cli elsewhere), so a `bdata login` on this machine just works.

Trigger flow (verified live against the API on 2026-08-22; endpoint names cross-checked
against the CLI's own source, @brightdata/cli dist/commands/scraper.js):

    POST /dca/trigger?collector=<c_...>        body: [{"url": "..."}, ...]
      → {"collection_id": "<j_...>", "start_eta": "..."}
    GET  /dca/dataset?id=<collection_id>        (poll ~every 10s)
      → 200 + JSON array of rows when ready; pending/running status until then

Heals stay in the CLI (`bdata scraper heal` / `approve`) — that's the judged flow — so
heal() shells out to it and logs the event itself.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time

import requests

API = "https://api.brightdata.com"


def _stored_cli_token() -> str:
    base = (os.environ.get("APPDATA")
            and pathlib.Path(os.environ["APPDATA"]) / "brightdata-cli"
            or pathlib.Path.home() / ".config" / "brightdata-cli")
    try:
        return json.loads((base / "credentials.json").read_text("utf-8")).get("api_key", "")
    except (OSError, ValueError):
        return ""


class BrightData:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("BRIGHTDATA_API_TOKEN", "") or _stored_cli_token()
        if not self.token:
            raise RuntimeError("no Bright Data token: set BRIGHTDATA_API_TOKEN or run `bdata login`")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        )

    # ── run a collector ────────────────────────────────────────────────────────
    def trigger(self, collector_id: str, inputs: list[str] | None = None) -> str:
        """Fire a collector run; returns the collection_id used to fetch results."""
        r = self.session.post(
            f"{API}/dca/trigger",
            params={"collector": collector_id},
            json=[{"url": u} for u in (inputs or [])],
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["collection_id"]

    def poll(self, collector_id: str, collection_id: str,
             timeout_s: int = 900, wait_s: int = 10) -> list[dict]:
        """Block until the run is ready; returns the result rows. Heavy aggregators
        (Shine's 200-row pages, Techgig) can take >10 min, so the default is generous."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            r = self.session.get(
                f"{API}/dca/dataset", params={"id": collection_id}, timeout=120)
            if r.status_code == 200:
                try:
                    payload = r.json()
                except ValueError:
                    payload = None
                if isinstance(payload, list):
                    return payload
            time.sleep(wait_s)
        raise TimeoutError(f"collector {collector_id} run {collection_id} not ready in {timeout_s}s")

    def run(self, collector_id: str, inputs: list[str] | None = None,
            timeout_s: int = 900) -> list[dict]:
        collection_id = self.trigger(collector_id, inputs)
        return self.poll(collector_id, collection_id, timeout_s=timeout_s)

    # ── heal (CLI is the judged flow) ──────────────────────────────────────────
    @staticmethod
    def heal(collector_id: str, what_broke: str,
             approve: bool = True, auto_approve_flag: bool = False) -> str:
        """Ask Scraper Studio to repair the scraper.

        approve=True        run `bdata scraper approve` after the heal (default — the
                            guarded production flow; auto-heal keeps approval explicit)
        auto_approve_flag   pass --auto-approve to the heal itself (unattended CI loop)

        Returns the CLI output. The Collector ID is preserved by design — every
        schedule and integration above it keeps working.
        """
        cmd = ["npx", "-p", "@brightdata/cli", "bdata", "scraper", "heal",
               collector_id, what_broke]
        if auto_approve_flag:
            cmd.append("--auto-approve")
        out = subprocess.run(cmd, capture_output=True, text=True, shell=os.name == "nt")
        if approve:
            subprocess.run(
                ["npx", "-p", "@brightdata/cli", "bdata", "scraper", "approve", collector_id],
                capture_output=True, text=True, shell=os.name == "nt",
            )
        return out.stdout or out.stderr
