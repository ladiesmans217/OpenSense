"""Source onboarding: the /add ladder — deny-list → probes → create → verify →
(vet: heal → approve → re-verify) → wire into sources.yaml → git commit.

The textual YAML append/remove preserves every comment in the registry (a full
PyYAML round-trip would erase the post-mortems). Pure helpers are unit-tested;
the network/CLI steps are thin wrappers verified live.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import event_log
from .normalize import _ALIASES

ROOT = Path(__file__).resolve().parent.parent
SOURCES_YAML = ROOT / "config" / "sources.yaml"
KINDS = ("job", "internship", "hackathon", "bounty", "scholarship", "event")

# ── compliance deny-list ─────────────────────────────────────────────────────

DENY_DOMAINS = {
    "linkedin.com": "login-walled, personal data, and ToS-prohibited — hackathon rules ban it",
    "facebook.com": "login-walled + personal data — rules ban it",
    "instagram.com": "login-walled + personal data — rules ban it",
    "instahyre.com": "candidate login-wall — listings not publicly browsable",
    "handshake.com": "student-account login-wall",
    "flexjobs.com": "paid subscription wall",
}
DENY_TLDS = (".gov", ".gov.in", ".nic.in", ".gov.uk", ".mil")
PREBUILT_HINTS = {
    "amazon": "covered by Bright Data's pre-built Amazon scrapers — use those, not a custom build",
    "indeed": "pre-built coverage exists — rules require the long tail",
    "glassdoor": "pre-built coverage exists — rules require the long tail",
    "walmart": "pre-built coverage exists — rules require the long tail",
}


def deny_reason(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "that doesn't look like a URL"
    for domain, reason in DENY_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return f"{domain}: {reason}"
    for tld in DENY_TLDS:
        if host.endswith(tld):
            return f"government domain ({host}) — hackathon rules ban scraping .gov sites"
    for hint, reason in PREBUILT_HINTS.items():
        if hint in host:
            return f"{host}: {reason}"
    return None


# ── pre-flight probes ────────────────────────────────────────────────────────

_LOGIN_MARKERS = re.compile(
    r"sign\s?in\s?to\s?(view|see|continue)|log\s?in\s?to\s?(view|continue|apply)|"
    r"create\s+an\s+account\s+to|403\s+forbidden|access\s+denied", re.I)


def probe(url: str, timeout: int = 15) -> tuple[str, str]:
    """Cheap aliveness + login-wall probe. Returns (verdict, note):
    verdict ∈ ok | dead | login_walled."""
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
    except requests.RequestException as exc:
        return "dead", f"unreachable: {str(exc)[:80]}"
    if r.status_code >= 400:
        return "dead", f"HTTP {r.status_code}"
    text = r.text[:20000]
    if len(text) < 500 and _LOGIN_MARKERS.search(text):
        return "login_walled", "content hidden behind a login prompt"
    if _LOGIN_MARKERS.search(text[:3000]) and "intern" not in text.lower():
        return "login_walled", "login markers with no public listing content"
    return "ok", f"HTTP {r.status_code}, {len(r.text) // 1024}KB"


# ── field-map inference ──────────────────────────────────────────────────────

def infer_field_map(rows: list[dict]) -> dict:
    """Map unified fields → actual collector keys by scoring against the alias
    table (exact > suffix/prefix > substring). Unmapped fields fall back to
    normalize's alias chain at run time."""
    keys = [k.lower() for k in (rows[0] if rows else {})]
    field_map: dict = {}
    for field, aliases in _ALIASES.items():
        best, best_score = None, 0
        for key in keys:
            if key == field:
                best, best_score = key, 100
                break
            for alias in aliases:
                alias = alias.lower()
                if key == alias:
                    best, best_score = key, max(best_score, 90)
                elif key.endswith("_" + alias) or key.startswith(alias + "_"):
                    if best_score < 70:
                        best, best_score = key, 70
                elif alias in key and best_score < 50:
                    best, best_score = key, 50
        if best and best_score >= 50:
            field_map[field] = best
    return field_map


# ── YAML text operations (comment-preserving) ────────────────────────────────

def _slug(url_or_name: str) -> str:
    host = urlparse(url_or_name).hostname or url_or_name
    return re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")


def source_block_text(name: str, kind: str, url: str, collector_id: str,
                      field_map: dict) -> str:
    fm = ", ".join(f"{k}: {v}" for k, v in sorted(field_map.items())) or \
        "{title: title, url: url}"
    return (f"\n  # added via control plane {event_ts()}\n"
            f"  - name: {name}\n"
            f"    kind: {kind}\n"
            f"    type: discovery\n"
            f"    seed_url: {url}\n"
            f"    collector_id: {collector_id}\n"
            f"    field_map: {{{fm}}}\n"
            f"    verify_not_prebuilt: true\n")


def event_ts() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def append_source(name: str, kind: str, url: str, collector_id: str,
                  field_map: dict) -> None:
    block = source_block_text(name, kind, url, collector_id, field_map)
    text = SOURCES_YAML.read_text("utf-8")
    if re.search(rf"^  - name: {re.escape(name)}$", text, re.M):
        raise ValueError(f"source '{name}' already exists")
    SOURCES_YAML.write_text(text.rstrip("\n") + "\n" + block, "utf-8")


def disable_source(name: str) -> bool:
    """Flip a source block to enabled: false (textual, comment-preserving)."""
    text = SOURCES_YAML.read_text("utf-8")
    pattern = re.compile(
        rf"(^  - name: {re.escape(name)}\n(?:    .*\n)*?)    (collector_id: .*\n)",
        re.M)
    if not pattern.search(text):
        return False
    text = pattern.sub(r"\1    enabled: false   # benched via control plane\n    \2",
                       text, count=1)
    SOURCES_YAML.write_text(text, "utf-8")
    return True


def git_commit(message: str) -> str:
    """Best-effort commit (and push if a remote exists). Returns a note."""
    try:
        subprocess.run(["git", "add", "config/sources.yaml", "data/watches.json"],
                       cwd=ROOT, capture_output=True, text=True)
        c = subprocess.run(["git", "commit", "-m", message], cwd=ROOT,
                           capture_output=True, text=True)
        if c.returncode != 0:
            return "committed nothing (no changes or no repo)"
        p = subprocess.run(["git", "push"], cwd=ROOT, capture_output=True, text=True)
        return "pushed" if p.returncode == 0 else "committed locally (no push access)"
    except OSError:
        return "no git available — config saved on disk only"


# ── growth backlog: /suggest offers these, the radar proposes its own expansion

BACKLOG = [
    {"name": "outreachy", "url": "https://www.outreachy.org/apply/", "kind": "internship",
     "note": "OSS internships, plain HTML — should be easy"},
    {"name": "gsoc", "url": "https://summerofcode.withgoogle.com/programs", "kind": "internship",
     "note": "the classic OSS internship"},
    {"name": "cutshort", "url": "https://cutshort.io/categories", "kind": "job",
     "note": "India tech hiring, JS-heavy"},
    {"name": "naukri", "url": "https://www.naukri.com/it-jobs", "kind": "job",
     "note": "the biggest Indian job board"},
    {"name": "wellfound", "url": "https://wellfound.com/jobs", "kind": "job",
     "note": "startup jobs — login-wall risk"},
    {"name": "shiksha", "url": "https://www.shiksha.com/scholarship/", "kind": "scholarship",
     "note": "India scholarships"},
    {"name": "collegedunia", "url": "https://collegedunia.com/scholarships", "kind": "scholarship",
     "note": "India scholarships"},
    {"name": "dorahacks", "url": "https://dorahacks.io/hackathon", "kind": "hackathon",
     "note": "web3 hackathons"},
    {"name": "challengerocket", "url": "https://challengerocket.com/", "kind": "bounty",
     "note": "challenges & competitions"},
    {"name": "allevents", "url": "https://allevents.in/india/bangalore/technology", "kind": "event",
     "note": "tech events listings"},
]


def existing_names() -> set[str]:
    """Names already present in the registry (enabled or benched)."""
    text = SOURCES_YAML.read_text("utf-8")
    return set(re.findall(r"^  - name: (.+)$", text, re.M))


def pick_candidates(state: dict, existing: set[str], kind: str | None = None,
                    n: int = 3) -> list[tuple[int, dict]]:
    """Next backlog entries worth attempting: not attempted/skipped, not already
    a source, not deny-listed; optional kind filter. Returns (backlog_index,
    entry) — the index is the stable id used in the inline buttons."""
    out: list[tuple[int, dict]] = []
    done = set(state.get("attempted", [])) | set(state.get("skipped", []))
    for i, c in enumerate(BACKLOG):
        if c["name"] in done or c["name"] in existing:
            continue
        if kind and c["kind"] != kind:
            continue
        if deny_reason(c["url"]):
            continue                    # never offer what the deny-list would refuse
        out.append((i, c))
        if len(out) == n:
            break
    return out


# ── the /add ladder ──────────────────────────────────────────────────────────

def _bdata(*args: str, timeout: int = 1200) -> str:
    out = subprocess.run(["npx", "-p", "@brightdata/cli", "bdata", *args],
                         capture_output=True, text=True, timeout=timeout,
                         shell=False)
    return (out.stdout or "") + (out.stderr or "")


def add_source(url: str, kind: str = "job") -> tuple[str, str]:
    """Full onboarding. Returns (verdict_emoji_status, report_text)."""
    if kind not in KINDS:
        kind = "job"
    reason = deny_reason(url)
    if reason:
        event_log.log("source_op", op="add", url=url, status="denied", reason=reason)
        return "denied", f"❌ {url} — {reason}"

    verdict, note = probe(url)
    if verdict != "ok":
        event_log.log("source_op", op="add", url=url, status=verdict, reason=note)
        return verdict, f"❌ {url} — {note}"

    name = _slug(url) + ("-opportunities" if kind in ("scholarship",) else "-" + kind + "s")
    name = name.replace("--", "-")
    event_log.log("source_op", op="add", url=url, status="creating")
    try:
        out = _bdata("scraper", "create", url,
                     f"Extract the {kind} listings on this page. For each return: "
                     f"title, url, organization or company name, location, and "
                     f"deadline if shown. One row per listing.",
                     "--name", f"opensense-{_slug(url)}", "--json")
        collector_id = re.search(r'"collector_id"\s*:\s*"(c_[a-z0-9]+)"', out)
        if not collector_id:
            raise RuntimeError(f"generation failed: {out[-200:]}")
        collector_id = collector_id.group(1)
    except Exception as exc:  # creation failure (cap, AI error, timeout)
        event_log.log("source_op", op="add", url=url, status="create_failed",
                      error=str(exc)[:200])
        return "benched", f"⚠️ {url} — collector generation failed ({str(exc)[:120]}). Benched; retry later."

    rows = _verify_with_vetting(collector_id, url)
    if not rows:
        event_log.log("source_op", op="add", url=url, status="vetting_failed",
                      collector_id=collector_id)
        append_source(name, kind, url, collector_id,
                      {"title": "title", "url": "url"})
        disable_source(name)
        return "benched", (f"⚠️ {url} — created and healed twice, still no rows "
                           f"(JS-hostile page). Benched with history; the collector "
                           f"{collector_id} is kept for a future retry.")

    field_map = infer_field_map(rows)
    append_source(name, kind, url, collector_id, field_map)
    note = git_commit(f"control-plane: add source {name} ({collector_id})")
    sample = rows[0]
    sample_txt = next((str(v) for v in sample.values()
                       if isinstance(v, str) and len(v) > 3), "row ready")
    event_log.log("source_op", op="add", url=url, status="added",
                  collector_id=collector_id, rows=len(rows), git=note)
    return "added", (f"✅ {url} — added as `{name}` ({len(rows)} rows verified; "
                     f"sample: {sample_txt[:60]}). Live from the next cron run. [{note}]")


def _verify_with_vetting(collector_id: str, url: str) -> list[dict]:
    """Run → (heal → approve → run) up to twice. Returns rows or []."""
    from .brightdata import BrightData
    from .heal import prompt_for
    for attempt in range(3):
        try:
            rows = BrightData().run(collector_id, inputs=[url])
            titled = [r for r in rows if isinstance(r, dict) and
                      any(isinstance(v, str) and v for v in r.values())]
            if titled:
                return rows
            error = "run returned empty rows"
        except Exception as exc:
            error = str(exc)
        if attempt == 2:
            break
        event_log.log("source_op", op="vet", collector_id=collector_id,
                      attempt=attempt + 1, error=error[:150])
        try:
            _bdata("scraper", "heal", collector_id, prompt_for(error))
            _bdata("scraper", "approve", collector_id)
        except Exception:
            break
    return []
