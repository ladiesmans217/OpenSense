"""Narration: prompt building + env-gated behaviour. No network in tests."""
import pipeline.narrate as narrate_mod
from pipeline.narrate import build_prompt, narrate

SIGNAL = {"total": 12, "prev": 8, "pct": 50, "by_kind": {"internship": 7},
          "sources": 4}


def test_build_prompt_contains_data_and_instructions():
    prompt = build_prompt(SIGNAL, [{"title": "ML Intern", "org": "IISc",
                                    "kind": "internship"}])
    assert "12 new" in prompt and "ML Intern @ IISc [internship]" in prompt
    assert "2-3 short lines" in prompt and "only cite" in prompt


def test_narrate_off_without_key(monkeypatch):
    monkeypatch.delenv("NARRATE_API_KEY", raising=False)
    assert narrate(SIGNAL, []) is None


def test_narrate_silent_on_any_failure(monkeypatch):
    monkeypatch.setenv("NARRATE_API_KEY", "sk-test")
    monkeypatch.setattr(narrate_mod.requests, "post",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert narrate(SIGNAL, []) is None


def test_narrate_returns_text_when_configured(monkeypatch):
    monkeypatch.setenv("NARRATE_API_KEY", "sk-test")
    monkeypatch.setenv("NARRATE_MODEL", "mini-test")

    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": " hi \n"}}]}
    sent = {}
    monkeypatch.setattr(narrate_mod.requests, "post",
                        lambda url, **k: sent.update(url=url, **k) or R())
    assert narrate(SIGNAL, []) == "hi"
    assert sent["url"].endswith("/chat/completions")
    assert sent["json"]["model"] == "mini-test"
