#!/usr/bin/env python3
"""Reads headlines.json and sends a daily digest email via Gmail.

The email leads with an AI-written morning briefing — a coherent narrative
synthesized from the day's headlines + snippets via Gemini — followed by the
full per-outlet link list. If the briefing can't be generated (no API key,
quota, network), the email falls back to the link list alone.
"""
import html as html_lib
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Allow importing sibling modules (fetch_headlines) when run as a script.
sys.path.insert(0, str(Path(__file__).parent))

REGION_ORDER = ["Gulf", "Levant", "Israel", "Pan-Arab"]

# One briefing per day, so the better flash model is well within the free tier.
GEMINI_MODEL = "gemini-2.5-flash"
REVIEW_WORDS = "350-500"

# Major international feeds that ground the briefing in today's WORLD news, so
# it covers the global order rather than only the MENA outlets in headlines.json.
WORLD_FEEDS = [
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("France 24", "https://www.france24.com/en/rss"),
    ("Deutsche Welle", "https://rss.dw.com/rdf/rss-en-world"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Google News World",
     "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
]
WORLD_PER_FEED = 8   # newest items to take from each world feed


def load_headlines() -> dict:
    path = Path(__file__).parent.parent / "headlines.json"
    return json.loads(path.read_text(encoding="utf-8"))


def format_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
        return d.strftime("%-d %b")
    except Exception:
        return ""


def _review_to_html(text: str) -> str:
    """Convert the model's plain-text briefing (paragraphs, **bold** lead-ins)
    into safe email HTML paragraphs."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out = []
    for p in paras:
        safe = html_lib.escape(p)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
        safe = safe.replace("\n", "<br>")
        out.append(
            '<p style="margin:0 0 12px;font-size:14px;line-height:1.7;'
            f'color:#3D3B42">{safe}</p>'
        )
    return "".join(out)


def fetch_world_headlines() -> list:
    """Pull today's top stories from major international feeds so the briefing
    reflects the global news cycle, not just the MENA outlets. Returns a list of
    '[World · Outlet] Title — summary' strings; tolerant of any feed failing."""
    try:
        import requests
        from fetch_headlines import fresh_items, parse_feed
    except Exception as exc:
        print(f"World-feed helpers unavailable ({exc}) — briefing skips world feeds")
        return []

    session = requests.Session()
    lines, seen = [], set()
    for name, url in WORLD_FEEDS:
        items = parse_feed(session, url, None) or []
        for it in fresh_items(items, name)[:WORLD_PER_FEED]:
            title = (it.get("title") or "").strip()
            key = title.lower()
            if not title or key in seen:
                continue
            seen.add(key)
            entry = f"[World · {name}] {title}"
            if it.get("description"):
                entry += f" — {it['description']}"
            lines.append(entry)
    print(f"Collected {len(lines)} world headlines from {len(WORLD_FEEDS)} feeds")
    return lines


def build_review(data: dict) -> str:
    """Synthesize a coherent GLOBAL morning briefing — the day's biggest world
    developments, with MENA as one part of the picture — grounded in today's
    international + regional headlines via Gemini. Returns formatted HTML, or ''
    if unavailable (the email then falls back to the link list only)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set — email will use the link list only")
        return ""

    world_lines = fetch_world_headlines()

    regions = data.get("regions", {})
    mena_lines = []
    for region in REGION_ORDER:
        for outlet in regions.get(region, []):
            for h in outlet.get("headlines", []):
                title = (h.get("title") or "").strip()
                if not title:
                    continue
                snip = (h.get("snippet") or "").strip()
                entry = f"[{region} · {outlet.get('source', '')}] {title}"
                if snip:
                    entry += f" — {snip}"
                mena_lines.append(entry)

    if not world_lines and not mena_lines:
        return ""

    try:
        from google import genai
    except ImportError:
        print("google-genai not installed — email will use the link list only")
        return ""

    prompt = (
        "You are the editor of a daily world-affairs intelligence briefing. Below "
        "are today's headlines (many with short summaries) from major international "
        "news outlets, followed by headlines from Middle East & North Africa "
        "outlets.\n\n"
        "Write a cohesive GLOBAL morning briefing for a well-informed reader:\n"
        "- Lead with the single biggest development shaping the world order today, "
        "in 1-2 sentences.\n"
        "- Then 5-7 short paragraphs covering the day's most consequential global "
        "stories: great-power politics (US, China, Russia/Ukraine, Europe), wars "
        "and security, the global economy and markets, and other major world "
        "events.\n"
        "- Treat the Middle East as ONE part of the global picture, not the focus "
        "— include MENA stories only when they rank among the day's most important "
        "worldwide.\n"
        "- Synthesize across outlets rather than relisting headlines; note where "
        "framing diverges when relevant.\n"
        "- Stay factual and grounded STRICTLY in the material provided; never "
        "invent facts, figures, or attributions.\n"
        "- Begin each paragraph with a short bold lead-in in **double asterisks** "
        "(e.g. **Ukraine war:**).\n"
        f"- Aim for {REVIEW_WORDS} words. Return plain text only — no headings, no "
        "bullet lists.\n\n"
        "WORLD HEADLINES:\n" + "\n".join(world_lines) +
        "\n\nMIDDLE EAST & NORTH AFRICA HEADLINES:\n" + "\n".join(mena_lines)
    )

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = (resp.text or "").strip()
    except Exception as exc:
        print(f"Briefing generation failed ({exc}) — using the link list only")
        return ""

    if not text:
        return ""
    print(f"Generated world briefing ({len(text.split())} words)")
    return _review_to_html(text)


def build_html(data: dict, review_html: str = "") -> str:
    updated = data.get("updated", "")
    try:
        updated_label = datetime.fromisoformat(updated).strftime(
            "%A, %-d %B %Y, %H:%M UTC"
        )
    except Exception:
        updated_label = updated

    rows = ""
    regions = data.get("regions", {})
    for region in REGION_ORDER:
        outlets = regions.get(region, [])
        if not outlets:
            continue
        rows += f"""
        <tr>
          <td colspan="2" style="padding:18px 0 6px;font-family:Georgia,serif;
              font-size:17px;font-weight:bold;color:#18171A;
              border-bottom:2px solid #18171A;">
            {region}
          </td>
        </tr>"""
        for outlet in outlets:
            headlines = outlet.get("headlines", [])
            if not headlines:
                continue
            items = "".join(
                f'<li style="margin-bottom:6px">'
                f'<a href="{h["url"]}" style="color:#1A3B6B;text-decoration:none;'
                f'font-size:13px;line-height:1.5">{h["title"]}</a>'
                f'</li>'
                for h in headlines
            )
            rows += f"""
        <tr>
          <td style="padding:10px 0 6px;vertical-align:top;width:130px">
            <div style="font-size:12px;font-weight:600;color:#18171A">{outlet["source"]}</div>
            <div style="font-size:11px;color:#8A8690">{outlet["country"]}</div>
            <a href="{outlet["url"]}" style="font-size:11px;color:#8A8690">Open site →</a>
          </td>
          <td style="padding:10px 0 6px;vertical-align:top">
            <ul style="margin:0;padding-left:16px;list-style:disc">{items}</ul>
          </td>
        </tr>"""

    review_block = ""
    if review_html:
        review_block = f"""
    <tr>
      <td style="padding:24px 28px 8px">
        <div style="font-family:Georgia,serif;font-size:12px;font-weight:bold;
            text-transform:uppercase;letter-spacing:2px;color:#9A7B2E;
            margin-bottom:14px">Today's World Briefing</div>
        {review_html}
      </td>
    </tr>
    <tr>
      <td style="padding:6px 28px 0">
        <div style="border-top:1px solid #DDD9D0"></div>
      </td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F7F4EE;font-family:'Source Sans 3',
    Arial,sans-serif;color:#18171A">
  <table width="100%" cellpadding="0" cellspacing="0"
      style="max-width:680px;margin:0 auto;background:#fff;
             border:1px solid #DDD9D0">
    <tr>
      <td style="background:#18171A;padding:20px 28px;text-align:center">
        <div style="font-size:10px;letter-spacing:3px;text-transform:uppercase;
            color:rgba(255,255,255,.5);margin-bottom:6px">
          Regional Intelligence Desk · Daily Edition
        </div>
        <div style="font-family:Georgia,serif;font-size:30px;font-weight:bold;
            color:#fff">
          MENA Morning Briefing
        </div>
        <div style="font-size:11px;color:rgba(255,255,255,.4);margin-top:6px">
          {updated_label}
        </div>
      </td>
    </tr>
    {review_block}
    <tr>
      <td style="padding:20px 28px 4px">
        <div style="font-family:Georgia,serif;font-size:12px;font-weight:bold;
            text-transform:uppercase;letter-spacing:2px;color:#9A7B2E">
          Headlines by Source
        </div>
      </td>
    </tr>
    <tr>
      <td style="padding:0 28px 20px">
        <table width="100%" cellpadding="0" cellspacing="0">
          {rows}
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:14px 28px;border-top:2px double #18171A;
          text-align:center;font-size:11px;color:#8A8690">
        View full newsstand at
        <a href="https://roiebe23.github.io/mena-newsstand/"
            style="color:#1A3B6B">roiebe23.github.io/mena-newsstand</a>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send(html: str, subject: str) -> None:
    email_from = os.environ["EMAIL_FROM"]
    email_to = os.environ["EMAIL_TO"]
    password = os.environ["EMAIL_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"MENA Briefing <{email_from}>"
    msg["To"] = email_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(email_from, password)
        smtp.sendmail(email_from, email_to, msg.as_string())
    print(f"Email sent to {email_to}")


def main():
    data = load_headlines()
    review_html = build_review(data)
    html = build_html(data, review_html)
    try:
        date_label = datetime.fromisoformat(
            data.get("updated", "")
        ).strftime("%-d %b %Y")
    except Exception:
        date_label = datetime.now(timezone.utc).strftime("%-d %b %Y")
    subject = f"MENA Morning Briefing — {date_label}"
    send(html, subject)


if __name__ == "__main__":
    main()
