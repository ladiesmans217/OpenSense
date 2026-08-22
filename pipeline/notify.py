"""Delivery surfaces: Telegram raw sender, categorized HTML digest, PDF, email.

Used by both the pipeline (digest/alerts — runs anywhere, CI included) and the
bot (verdicts). Senders are env-driven: SMTP (Gmail app password) or Resend.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

import requests

from .normalize import days_left

KIND_ORDER = ["internship", "job", "hackathon", "bounty", "scholarship", "event"]


def send_telegram_message(chat_id: str | int, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not (token and chat_id):
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4000],
              "disable_web_page_preview": True},
        timeout=30,
    ).raise_for_status()


# ── HTML digest ──────────────────────────────────────────────────────────────

def _esc(v) -> str:
    return (str(v or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html_digest(ranked: list[dict], delta: dict,
                       signal: dict | None = None) -> str:
    s = delta.get("summary", {})
    by_kind: dict[str, list[dict]] = {}
    for item in ranked:
        by_kind.setdefault(item.get("kind", "event"), []).append(item)

    sections = []
    for kind in KIND_ORDER:
        items = by_kind.get(kind, [])
        if not items:
            continue
        rows = "".join(
            f"<tr><td>{_esc(l['title'][:70])}</td><td>{_esc(l['org'])}</td>"
            f"<td>{_esc(l.get('deadline') or '—')}</td>"
            f"<td>{l.get('match', 0)}</td>"
            f"<td><a href='{_esc(l['url'])}'>open</a></td></tr>"
            for l in items[:15])
        sections.append(
            f"<h2 style='color:#1a5fb4'>{kind}s ({len(items)})</h2>"
            f"<table style='border-collapse:collapse;width:100%;font-size:13px'>"
            f"<tr style='text-align:left;color:#666'>"
            f"<th>listing</th><th>org</th><th>deadline</th><th>match</th><th></th></tr>"
            f"{rows}</table>")

    closing = delta.get("closing_this_week") or []
    closing_html = "".join(
        f"<li>{_esc(c['title'])} — <b>{c['days_left']}d</b></li>" for c in closing[:10])

    from .trends import render_signal
    trend_html = (f"<div style='background:#e8f4ec;border-left:3px solid #3ecf8e;"
                  f"padding:8px 12px;margin:10px 0'>{_esc(render_signal(signal))}"
                  f"</div>") if signal else ""

    return f"""<div style='font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:720px;margin:auto'>
<h1 style='margin:0'>📡 OpenSense radar</h1>
<p style='color:#666'>{s.get('total_live', 0)} live listings · {s.get('new', 0)} new ·
{len(closing)} close this week</p>
{trend_html}
{f"<div style='background:#fff4e5;border-left:3px solid #e78a2e;padding:8px 12px'><b>Closing this week</b><ul>{closing_html}</ul></div>" if closing_html else ''}
{''.join(sections)}
<p style='color:#999;font-size:11px'>every number traceable to its collector run — see the dashboard timeline</p>
</div>"""


# ── PDF (reportlab one-pager) ────────────────────────────────────────────────

def build_pdf(ranked: list[dict], delta: dict, signal: dict | None = None) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="OpenSense digest")
    styles = getSampleStyleSheet()
    s = delta.get("summary", {})
    story = [
        Paragraph("📡 OpenSense radar", styles["Title"]),
        Paragraph(f"{s.get('total_live', 0)} live · {s.get('new', 0)} new · "
                  f"{len(delta.get('closing_this_week') or [])} closing this week",
                  styles["Normal"]),
    ]
    if signal:
        from .trends import render_signal
        story.append(Paragraph(render_signal(signal, rich=False),  # ASCII: core fonts
                               styles["Normal"]))
    story.append(Spacer(1, 12))
    data = [["listing", "kind", "deadline", "m"]]
    for l in ranked[:20]:
        data.append([l["title"][:52], l.get("kind", ""), l.get("deadline") or "—",
                     str(l.get("match", 0))])
    story.append(Table(data, colWidths=[290, 70, 70, 25],
                       style=[("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                              ("FONTSIZE", (0, 0), (-1, -1), 8),
                              ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                              ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                               [colors.white, colors.HexColor("#f4f6fa")])]))
    doc.build(story)
    return buf.getvalue()


# ── email ────────────────────────────────────────────────────────────────────

def send_email(subject: str, html: str, pdf: bytes | None = None) -> str:
    """Send via Resend API or SMTP (Gmail app password). Returns the channel."""
    to_addr = os.environ.get("EMAIL_TO", "")
    if not to_addr:
        return "skipped (EMAIL_TO not set)"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("EMAIL_FROM", "opensense@resend.dev")
    msg["To"] = to_addr
    msg.set_content("Open the HTML view for the full digest.")
    msg.add_alternative(html, subtype="html")
    if pdf:
        msg.add_attachment(pdf, maintype="application", subtype="pdf",
                           filename="opensense-digest.pdf")

    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        import base64
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}"},
            json={"from": msg["From"], "to": [to_addr], "subject": subject,
                  "html": html},
            timeout=30,
        ).raise_for_status()
        return "resend"
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    with smtplib.SMTP_SSL(smtp_host, 465, timeout=30) as server:
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.send_message(msg)
    return "smtp"
