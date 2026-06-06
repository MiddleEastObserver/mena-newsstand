#!/usr/bin/env python3
"""Reads headlines.json and sends a daily digest email via Gmail."""
import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

REGION_ORDER = ["Gulf", "Levant", "Israel", "Pan-Arab"]


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


def build_html(data: dict) -> str:
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
    <tr>
      <td style="padding:20px 28px">
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
    html = build_html(data)
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
