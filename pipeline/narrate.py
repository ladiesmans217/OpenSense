"""Optional LLM narration for the digest — env-driven, OFF by default.

The rules-based digest stays primary and complete on its own (clean AI
disclosure). When NARRATE_API_KEY is set, we additionally ask an
OpenAI-compatible model for 2-3 lines of "what changed and why you care",
clearly labeled as AI narration. Any failure returns None — silently.
"""
from __future__ import annotations

import os

import requests

from .trends import render_signal

MODEL_DEFAULT = "gpt-4o-mini"
BASE_URL_DEFAULT = "https://api.openai.com/v1"


def build_prompt(signal: dict, top_new: list[dict]) -> str:
    lines = [render_signal(signal), "", "new listings this run (sample):"]
    for l in top_new:
        lines.append(f"- {l.get('title', '')} @ {l.get('org', '')} "
                     f"[{l.get('kind', '')}]")
    return "\n".join(lines) + (
        "\n\nWrite 2-3 short lines (plain text, no markdown, no emoji) telling "
        "an Indian college student what changed this week across these "
        "opportunity sources and why they should care. Be concrete; only cite "
        "kinds and numbers present in the data above.")


def narrate(signal: dict, top_new: list[dict]) -> str | None:
    """None unless configured AND the call succeeds — the digest never waits."""
    key = os.environ.get("NARRATE_API_KEY", "")
    if not key:
        return None
    base = os.environ.get("NARRATE_BASE_URL", BASE_URL_DEFAULT).rstrip("/")
    try:
        r = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": os.environ.get("NARRATE_MODEL", MODEL_DEFAULT),
                  "messages": [{"role": "user", "content": build_prompt(signal, top_new)}],
                  "max_tokens": 160, "temperature": 0.4},
            timeout=15)
        r.raise_for_status()
        text = str(r.json()["choices"][0]["message"]["content"]).strip()
        return text[:600] or None
    except Exception:
        return None
