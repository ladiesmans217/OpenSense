"""The control plane: a dependency-free Telegram long-poll bot.

`python -m pipeline bot` — receives commands from the owner's phone, runs the
source onboarding ladder, reports verdicts, manages watches, and exposes
manual heal approvals. The data plane (GitHub Actions cron) stays untouched:
this bot only writes config (sources.yaml, watches.json) and commits it.

Admin allowlist is mandatory: TELEGRAM_ADMIN_IDS=12345,67890.
"""
from __future__ import annotations

import html as html_mod
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import bodyguard, event_log, source_ops, trends
from .normalize import days_left

ROOT = Path(__file__).resolve().parent.parent
WATCHES = ROOT / "data" / "watches.json"
LATEST = ROOT / "data" / "latest.json"
SUGGEST_STATE = ROOT / "data" / "suggest.json"
API = "https://api.telegram.org/bot{token}/{method}"

_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def load_watches() -> list[dict]:
    if WATCHES.exists():
        return json.loads(WATCHES.read_text("utf-8"))
    return []


def save_watches(watches: list[dict]) -> None:
    WATCHES.parent.mkdir(exist_ok=True)
    WATCHES.write_text(json.dumps(watches, indent=1), "utf-8")


def load_suggest_state() -> dict:
    if SUGGEST_STATE.exists():
        return json.loads(SUGGEST_STATE.read_text("utf-8"))
    return {"attempted": [], "skipped": []}


def save_suggest_state(state: dict) -> None:
    SUGGEST_STATE.parent.mkdir(exist_ok=True)
    SUGGEST_STATE.write_text(json.dumps(state, indent=1), "utf-8")


# ── /find: search the live radar ────────────────────────────────────────────

KIND_ICONS = {"internship": "🧑‍💻", "job": "💼", "hackathon": "⚡", "bounty": "🏆",
              "scholarship": "🎓", "event": "📅"}


def load_latest(path: Path | None = None) -> list[dict]:
    src = path or LATEST
    if src.exists():
        return json.loads(src.read_text("utf-8")).get("listings", [])
    return []


def _term_score(term: str, listing: dict) -> int | None:
    """Where a query term hits: title 3 > org/kind 2 > location/tags 1.
    None = not found → the listing is excluded (AND semantics across terms)."""
    variants = {term} if len(term) <= 3 else {term, term.rstrip("s")}
    fields = ((listing.get("title", ""), 3), (listing.get("org", ""), 2),
              (listing.get("kind", ""), 2), (listing.get("location", ""), 1),
              (" ".join(listing.get("tags") or []), 1))
    for text, weight in fields:
        if any(v in text.lower() for v in variants):
            return weight
    return None


def find_listings(query: str, listings: list[dict], limit: int = 8) -> list[dict]:
    """All terms must match somewhere; rank by term weights + saved match score."""
    terms = [t for t in query.lower().split() if len(t) >= 2]
    if not terms:
        return []
    scored: list[tuple[int, dict]] = []
    for l in listings:
        score = 0
        for t in terms:
            s = _term_score(t, l)
            if s is None:
                score = -1
                break
            score += s
        if score >= 0:
            scored.append((score + (l.get("match") or 0), l))
    scored.sort(key=lambda p: (-p[0], p[1].get("title", "")))
    return [l for _, l in scored[:limit]]


def esc(v) -> str:
    """Escape dynamic text for Telegram HTML mode — titles/URLs can contain <>&."""
    return html_mod.escape(str(v or ""))


def trunc(v, n: int = 60) -> str:
    """Word-safe truncation with ellipsis — applied to the RAW string,
    always before esc() so we never cut an escape entity in half."""
    s = str(v or "")
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


GREETINGS = {"hi", "hii", "hiii", "hey", "hello", "yo", "sup", "hola", "namaste",
             "namaskara", "namaskaram", "vanakkam", "salaam",
             "good morning", "good afternoon", "good evening", "good night",
             "gm", "gn"}
THANKS = {"thanks", "thank you", "thankyou", "thx", "tysm", "ty", "dhanyawad",
          "shukriya", "nandri"}

_GREETING_REPLIES = [
    "👋 hey! I'm the OpenSense control plane — your radar takes commands here.\n"
    "/status for pipeline health · /add &lt;url&gt; [kind] to onboard a site · /help for everything",
    "📡 namaste! The radar is listening.\nTry /status, or hand me a site: /add &lt;url&gt; [kind]",
    "🦊 hello! 22+ sources, 6 self-heals and counting.\nWhat should we scan next? /help",
]
_THANKS_REPLY = "🙏 anytime — the radar never sleeps."


def _normalize_greeting(text: str) -> str:
    return re.sub(r"[^a-z ]", "", text.lower()).strip()


def format_status(summary: dict, last_run: dict | None,
                  fleet: dict | None = None) -> str:
    d = (last_run or {}).get("detail", {})
    lines = ["<b>📊 OpenSense status</b>",
             f"last run: <b>{d.get('total_live', '—')}</b> live listings · "
             f"{d.get('new', 0)} new · {d.get('removed', 0)} gone · "
             f"{d.get('closing_this_week', 0)} closing this week",
             f"recent triggers: {summary.get('sources_triggered', 0)} · "
             f"failures: {summary.get('source_failures', 0)} · "
             f"heals: {summary.get('heals', 0)}"]
    if fleet and fleet.get("total"):
        lines.append(f"fleet health: <b>{fleet['green']}/{fleet['total']}</b> sources 🟢 "
                     f"(success rate, last 20 runs each)")
    return "\n".join(lines)


def format_sources(cfg: dict, health: dict | None = None) -> str:
    sources = cfg.get("sources", [])
    live = [s for s in sources if s.get("enabled", True) and s.get("collector_id")]
    benched = [s for s in sources if s not in live]
    lines = [f"<b>🗂 sources</b> — 🟢 live ({len(live)}) · ⚪️ benched ({len(benched)})",
             ""]

    def _health(s: dict) -> str:
        h = (health or {}).get(s["name"])
        return f" · {h['icon']} {h['rate']}% · {h['runs']} runs" if h else ""

    lines += [f"🟢 {esc(s['name'])} <i>[{esc(s.get('kind', ''))}]</i>{_health(s)}"
              for s in live]
    lines += [f"⚪️ {esc(s['name'])} <i>[{esc(s.get('kind', ''))}]</i>{_health(s)}"
              for s in benched]
    return "\n".join(lines[:44])


COMMANDS = [
    ("find", "search the live radar — /find ml internship bangalore"),
    ("suggest", "the radar proposes its next sources — one tap to onboard"),
    ("add", "onboard a source site — /add <url> [kind] (auto-healed until good)"),
    ("remove", "bench a source by name or url"),
    ("status", "pipeline health at a glance"),
    ("sources", "list sources — live and benched, with health scores"),
    ("heals", "recent self-heal history"),
    ("watch", "alert me when NEW listings match a keyword"),
    ("unwatch", "remove a keyword watch"),
    ("approve", "approve a pending heal — /approve c_xxx"),
    ("reject", "reject a pending heal — /reject c_xxx"),
    ("help", "what this control plane can do"),
]


def register_commands(token: str) -> None:
    """Publish the command menu so Telegram's '/' autocomplete works."""
    requests.post(API.format(token=token, method="setMyCommands"),
                  json={"commands": [{"command": c, "description": d}
                                     for c, d in COMMANDS]}, timeout=30
                  ).raise_for_status()


HELP_TEXT = (
    "<b>📡 OpenSense control plane</b>\n"
    "<code>/find &lt;query&gt;</code> — search the live radar ('ml internship bangalore')\n"
    "<code>/suggest [kind]</code> — the radar proposes its next sources, one tap each\n"
    "<code>/add &lt;url&gt; [kind]</code> — onboard a site (auto-healed until good)\n"
    "<code>/remove &lt;name|url&gt;</code> — bench a source\n"
    "<code>/status</code> · <code>/sources</code> · <code>/heals</code>\n"
    "<code>/watch &lt;kw&gt;</code> · <code>/unwatch &lt;kw&gt;</code> — alerts on new matches\n"
    "<code>/approve c_xxx</code> · <code>/reject c_xxx</code> — heal approvals\n"
    "⭐ starred items closing soon get a daily bodyguard ping\n"
    "🟢 live · ⚪️ benched · added sources go live from the next cron run")


class Bot:
    def __init__(self, token: str, admin_ids: set[int]) -> None:
        self.token = token
        self.admin_ids = admin_ids
        self.pool = ThreadPoolExecutor(max_workers=2)   # Bright Data AI-job cap is real
        self.offset = 0

    # ── telegram plumbing ────────────────────────────────────────────────────
    def call(self, method: str, payload: dict) -> dict:
        r = requests.post(API.format(token=self.token, method=method),
                          json=payload, timeout=60)
        r.raise_for_status()
        return r.json()

    def send(self, chat_id: int, text: str, buttons: list[list[dict]] | None = None,
             rich: bool = False):
        """Send a message. rich=True enables Telegram HTML formatting — the
        caller must then have escaped dynamic text via esc()."""
        payload = {"chat_id": chat_id, "text": text[:4000],
                   "disable_web_page_preview": True}
        if rich:
            payload["parse_mode"] = "HTML"
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        self.call("sendMessage", payload)

    # ── update loop ──────────────────────────────────────────────────────────
    def run(self) -> None:
        register_commands(self.token)
        print("control plane online — waiting for commands (Ctrl+C to stop)")
        while True:
            try:
                bodyguard.check()   # throttled internally; starred deadlines never slip
                updates = self.call("getUpdates", {
                    "offset": self.offset, "timeout": 50,
                    "allowed_updates": ["message", "callback_query"]}).get("result", [])
                for update in updates:
                    self.offset = update["update_id"] + 1
                    self.dispatch(update)
            except requests.RequestException as exc:
                print(f"[net] {exc}; retrying in 5s")
                time.sleep(5)
            except KeyboardInterrupt:
                print("control plane offline")
                return

    def dispatch(self, update: dict) -> None:
        if "callback_query" in update:
            query = update["callback_query"]
            user_id = (query.get("from") or {}).get("id")
            if user_id not in self.admin_ids:   # buttons are admin doors too
                self.call("answerCallbackQuery", {"callback_query_id": query["id"]})
                chat_id = (query.get("message") or {}).get("chat", {}).get("id")
                if chat_id is not None:
                    self.send(chat_id, "🔒 not authorized — ask the owner to add your id "
                                       "to TELEGRAM_ADMIN_IDS.")
                event_log.log("bot", op="auth_reject", user=str(user_id))
                return
            self.on_callback(query)
            return
        msg = update.get("message") or {}
        chat_id, text = msg.get("chat", {}).get("id"), msg.get("text") or ""
        user_id = (msg.get("from") or {}).get("id")
        if chat_id is None:
            return
        if user_id not in self.admin_ids:
            self.send(chat_id, "🔒 not authorized — ask the owner to add your id "
                               "to TELEGRAM_ADMIN_IDS.")
            event_log.log("bot", op="auth_reject", user=str(user_id))
            return
        command, _, args = text.partition(" ")
        handler = {
            "/add": self.cmd_add, "/remove": self.cmd_remove,
            "/status": self.cmd_status, "/sources": self.cmd_sources,
            "/heals": self.cmd_heals, "/watch": self.cmd_watch,
            "/unwatch": self.cmd_unwatch, "/approve": self.cmd_approve,
            "/reject": self.cmd_reject, "/find": self.cmd_find,
            "/suggest": self.cmd_suggest, "/start": self.cmd_help,
            "/help": self.cmd_help,
        }.get(command.lower())
        if handler:
            handler(chat_id, args.strip())
            return
        normalized = _normalize_greeting(text)
        words = normalized.split()
        is_greeting = normalized in GREETINGS or (
            len(words) <= 3 and words and words[0] in GREETINGS)
        if is_greeting:
            self.send(chat_id, _GREETING_REPLIES[hash(text) % len(_GREETING_REPLIES)],
                      rich=True)
        elif normalized in THANKS:
            self.send(chat_id, _THANKS_REPLY)
        else:
            self.send(chat_id, "🤔 didn't catch that — here's what I speak:\n\n"
                      + HELP_TEXT, rich=True)

    # ── commands ─────────────────────────────────────────────────────────────
    def cmd_add(self, chat_id: int, args: str):
        urls = _URL_RE.findall(args) or ([args] if "." in args else [])
        kind = next((k for k in ("internship", "job", "hackathon", "bounty",
                                 "scholarship", "event") if k in args.lower()), "job")
        if not urls:
            self.send(chat_id, "usage: <code>/add &lt;url&gt; [kind]</code> — e.g. "
                               "<code>/add https://xyz.com/jobs internships</code>", rich=True)
            return
        self.send(chat_id, f"🛠 on it — onboarding <b>{len(urls)}</b> site(s) as "
                           f"<b>{esc(kind)}</b>.\n"
                           "ladder: deny-list → probes → AI generation (~10 min) → verify → "
                           "heal-if-broken → wire → commit\n"
                           "I'll report per site.", rich=True)
        for url in urls:
            def job(u=url):
                status, report = source_ops.add_source(u, kind)
                self.send(chat_id, report)
            self.pool.submit(job)

    def cmd_remove(self, chat_id: int, args: str):
        if not args:
            self.send(chat_id, "usage: /remove <name-or-url>")
            return
        name = source_ops._slug(args) if "." in args else args
        names = source_ops.existing_names()
        if name not in names:
            # smart fallback: a unique substring match ("/remove summerofcode")
            hits = [n for n in names if name.lower() in n.lower()]
            if len(hits) == 1:
                name = hits[0]
            elif hits:
                self.send(chat_id, "ambiguous — which one?\n" + "\n".join(hits))
                return
        ok = source_ops.disable_source(name)
        note = source_ops.git_commit(f"control-plane: bench source {name}")
        self.send(chat_id, f"✅ {name} benched (collector + history kept). [{note}]"
                 if ok else f"no source named '{name}' — /sources to list")

    def cmd_status(self, chat_id: int, _=""):
        summary = event_log.last_run_summary()
        last_run = next((e for e in event_log.recent(300) if e["kind"] == "run_end"), None)
        health = trends.health_scores(event_log.recent(500))
        fleet = {"green": sum(1 for h in health.values() if h["rate"] >= 90),
                 "total": len(health)}
        self.send(chat_id, format_status(summary, last_run, fleet), rich=True)

    def cmd_sources(self, chat_id: int, _=""):
        import yaml
        cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text("utf-8"))
        health = trends.health_scores(event_log.recent(500))
        self.send(chat_id, format_sources(cfg, health), rich=True)

    def cmd_heals(self, chat_id: int, _=""):
        heals = [e for e in event_log.recent(200) if e["kind"] == "heal"][:10]
        if not heals:
            self.send(chat_id, "no heals yet")
            return
        rows = []
        for e in heals:
            when = time.strftime("%m-%d %H:%M", time.localtime(e["ts"]))
            raw = e["detail"].get("issue") or e["detail"].get("fix") or ""
            issue = esc(raw.split("(")[0].rstrip())   # full text, stop at the paren
            rows.append(f"<code>{when}</code> · {esc(e['source'])} — {issue}")
        self.send(chat_id, "<b>🔧 recent self-heals</b>\n" + "\n".join(rows), rich=True)

    def cmd_watch(self, chat_id: int, args: str):
        if not args:
            self.send(chat_id, "usage: /watch <keyword> — pings you when NEW listings match")
            return
        watches = load_watches()
        if not any(w["chat_id"] == chat_id and w["keyword"].lower() == args.lower()
                   for w in watches):
            watches.append({"chat_id": chat_id, "keyword": args.lower()})
            save_watches(watches)
            source_ops.git_commit(f"control-plane: watch '{args}'")
        self.send(chat_id, f"👀 watching '{args}' — you'll get a ping on new matches")

    def cmd_unwatch(self, chat_id: int, args: str):
        watches = [w for w in load_watches()
                   if not (w["chat_id"] == chat_id and w["keyword"] == args.lower())]
        save_watches(watches)
        self.send(chat_id, f"removed watch '{args}'")

    def cmd_approve(self, chat_id: int, args: str):
        cid = args.strip()
        if not cid.startswith("c_"):
            self.send(chat_id, "usage: /approve c_xxxxx")
            return
        out = source_ops._bdata("scraper", "approve", cid)
        event_log.log("heal", source="control-plane", trigger="phone", status="approved",
                      collector_id=cid)
        self.send(chat_id, f"✅ approved {cid} — same collector id keeps serving")

    def cmd_reject(self, chat_id: int, args: str):
        cid = args.strip()
        out = source_ops._bdata("scraper", "approve", cid, "--reject")
        self.send(chat_id, f"↩️ rejected {cid}")

    def cmd_find(self, chat_id: int, args: str):
        if not args:
            self.send(chat_id, "usage: <code>/find &lt;query&gt;</code> — e.g. "
                               "<code>/find ml internship bangalore</code>", rich=True)
            return
        listings = load_latest()
        if not listings:
            self.send(chat_id, "no radar data yet — run the pipeline first", rich=True)
            return
        hits = find_listings(args, listings)
        if not hits:
            self.send(chat_id, f"🔎 no hits for '{esc(args)}' — try a skill "
                               "('python'), a kind ('internship') or a city", rich=True)
            return
        lines = [f"🔎 <b>{len(hits)} hits</b> for '{esc(args)}' · {len(listings)} live"]
        for l in hits:
            dl = days_left(l.get("deadline"))
            when = (" · closes today!" if dl == 0 else
                    f" · closes in {dl}d" if dl and dl > 0 else "")
            icon = KIND_ICONS.get(l.get("kind"), "•")
            lines.append(f"{icon} <b>{esc(trunc(l['title'], 70))}</b> — "
                         f"{esc(trunc(l.get('org', ''), 40))}{when}")
            if l.get("url"):
                lines.append(f"  {esc(l['url'])}")
        self.send(chat_id, "\n".join(lines), rich=True)

    def cmd_suggest(self, chat_id: int, args: str):
        kind = args.strip().lower() or None
        if kind and kind not in source_ops.KINDS:
            self.send(chat_id, f"kinds: {', '.join(source_ops.KINDS)}", rich=True)
            return
        picks = source_ops.pick_candidates(load_suggest_state(),
                                           source_ops.existing_names(), kind)
        if not picks:
            self.send(chat_id, "🏁 backlog done — everything's attempted, skipped or "
                               "already live. /add &lt;url&gt; to go beyond it.", rich=True)
            return
        label = f" [{esc(kind)}]" if kind else ""
        lines = [f"💡 next {len(picks)} to onboard{label} — one tap each:"]
        buttons = []
        for i, c in picks:
            lines.append(f"• <b>{esc(c['name'])}</b> <i>[{esc(c['kind'])}]</i> — "
                         f"{esc(c['note'])}\n  {esc(c['url'])}")
            buttons.append([
                {"text": f"➕ Add {c['name']}", "callback_data": f"sg_add:{i}"},
                {"text": "⏭ Skip", "callback_data": f"sg_skip:{i}"},
            ])
        self.send(chat_id, "\n".join(lines), buttons=buttons, rich=True)

    def _suggest_skip(self, chat_id: int, idx: int):
        c = source_ops.BACKLOG[idx]
        state = load_suggest_state()
        if c["name"] not in state["skipped"]:
            state["skipped"].append(c["name"])
            save_suggest_state(state)
        self.send(chat_id, f"⏭ skipped {esc(c['name'])} — I'll stop suggesting it")

    def _suggest_add(self, chat_id: int, idx: int):
        c = source_ops.BACKLOG[idx]
        state = load_suggest_state()
        if c["name"] not in state["attempted"]:
            state["attempted"].append(c["name"])
            save_suggest_state(state)
        self.send(chat_id, f"🛠 onboarding <b>{esc(c['name'])}</b> ({esc(c['kind'])}) — "
                           "generation ~10 min, heal-if-broken, then I'll report.",
                  rich=True)

        def job():
            status, report = source_ops.add_source(c["url"], c["kind"])
            self.send(chat_id, report)
        self.pool.submit(job)

    def cmd_help(self, chat_id: int, _=""):
        self.send(chat_id, HELP_TEXT, rich=True)

    def on_callback(self, query: dict):
        data = query.get("data") or ""
        chat_id = query["message"]["chat"]["id"]
        self.call("answerCallbackQuery", {"callback_query_id": query["id"]})
        if data.startswith("approve:"):
            self.cmd_approve(chat_id, data.split(":", 1)[1])
        elif data.startswith("retry:"):
            url = data.split(":", 1)[1]
            self.cmd_add(chat_id, url)
        elif data.startswith("sg_add:"):
            self._suggest_add(chat_id, int(data.split(":", 1)[1]))
        elif data.startswith("sg_skip:"):
            self._suggest_skip(chat_id, int(data.split(":", 1)[1]))


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    admins = {int(x) for x in os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",")
              if x.strip().isdigit()}
    if not token or not admins:
        raise SystemExit("set TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_IDS (numeric ids) — see docs/SETUP.md")
    Bot(token, admins).run()


if __name__ == "__main__":
    main()
