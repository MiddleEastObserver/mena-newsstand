#!/usr/bin/env python3
"""One-off diagnostic for Al-Akhbar's e-paper cover. Discovers:
  1. the cover image URL on a known issue page (/newspaper/5796),
  2. whether /newspaper (no number) shows the *latest* issue,
  3. the latest issue number (so we can always fetch today's),
by fetching on the GitHub runner and printing og:image + <img> srcs + issue links.
Read the log, then bake the working approach into fetch_frontpages.py.
"""
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 25

URLS = [
    "https://www.al-akhbar.com/newspaper",
    "https://www.al-akhbar.com/newspaper/",
    "https://www.al-akhbar.com/newspaper/5796",
    "https://www.al-akhbar.com/",
]

OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)
OG_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.I)
IMG_RE = re.compile(
    r'(?:src|data-src)=["\']([^"\']+\.(?:jpe?g|png|webp)[^"\']*)["\']', re.I)
ISSUE_RE = re.compile(r'/newspaper/(\d+)', re.I)


def fetch(session, url):
    headers = {"User-Agent": UA,
               "Accept": "text/html,application/xhtml+xml,*/*",
               "Accept-Language": "ar,en;q=0.9",
               "Referer": "https://www.al-akhbar.com/"}
    try:
        r = session.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    except Exception as exc:
        return None, f"ERR {exc}"
    return r, f"{r.status_code} {r.headers.get('Content-Type','?')} {len(r.text)}B  (final: {r.url})"


def main():
    session = requests.Session()
    for url in URLS:
        print(f"\n=== GET {url} ===")
        r, status = fetch(session, url)
        print(f"  -> {status}")
        if not r or r.status_code != 200:
            continue
        og = [m for rx in (OG_RE, OG_RE2) for m in rx.findall(r.text)]
        for u in og:
            print(f"  og:image -> {u}")
        # Cover-ish images first (contain 'news', 'paper', 'cover', 'front', a date)
        imgs = sorted(set(IMG_RE.findall(r.text)),
                      key=lambda u: -sum(k in u.lower() for k in
                                         ("news", "paper", "cover", "front", "issue", "pdf")))
        for u in imgs[:10]:
            print(f"  img -> {u}")
        issues = sorted({int(n) for n in ISSUE_RE.findall(r.text)}, reverse=True)
        if issues:
            print(f"  issue numbers on page (top 5): {issues[:5]}")


if __name__ == "__main__":
    main()
