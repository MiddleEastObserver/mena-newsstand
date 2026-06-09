#!/usr/bin/env python3
"""One-off diagnostic: for each paper still missing a cover, fetch its page on
alternative front-page sites and EXTRACT the real cover-image URL from the HTML
(og:image meta + cover <img> tags). Runs on the GitHub Actions runner, where
these sites answer. Read the 'FOUND' lines in the log, then bake the discovered
URL pattern into fetch_frontpages.py. Safe to delete afterwards.
"""
import re
from datetime import datetime, timezone

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 25

# paper -> candidate page URLs on sites that have dedicated per-paper pages.
# frontpages.com slugs confirmed to exist: arab-news, le-monde, financial-times.
PAPERS = {
    "Asharq Al-Awsat": [
        "https://www.frontpages.com/asharq-al-awsat/",
        "https://www.frontpages.com/asharq-al-awsat-english/",
    ],
    "Al-Ahram": [
        "https://www.frontpages.com/al-ahram/",
        "https://www.frontpages.com/al-ahram-egypt/",
    ],
    "Al-Quds Al-Arabi": [
        "https://www.frontpages.com/al-quds-al-arabi/",
        "https://www.frontpages.com/al-quds/",
    ],
    "Arab News": [
        "https://www.frontpages.com/arab-news/",
    ],
    "Al-Anba": [
        "https://www.frontpages.com/al-anba/",
        "https://www.frontpages.com/alanba/",
    ],
    "An-Nahar": [
        "https://www.frontpages.com/an-nahar/",
        "https://www.frontpages.com/annahar/",
    ],
    "Tehran Times": [
        "https://www.frontpages.com/tehran-times/",
    ],
    "Financial Times": [
        "https://www.frontpages.com/financial-times/",
    ],
    "Le Monde": [
        "https://www.frontpages.com/le-monde/",
    ],
}

OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.I)
OG_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.I)
# <img ...> whose src/data-src looks like a front-page cover (jpg/jpeg/png/webp)
IMG_RE = re.compile(
    r'<img[^>]+(?:src|data-src)=["\']([^"\']+\.(?:jpe?g|png|webp)[^"\']*)["\']',
    re.I)


def fetch(session, url):
    headers = {"User-Agent": UA,
               "Accept": "text/html,application/xhtml+xml,*/*"}
    try:
        r = session.get(url, headers=headers, timeout=TIMEOUT,
                        allow_redirects=True)
    except Exception as exc:
        return None, f"ERR {exc}"
    return r, f"{r.status_code} {r.headers.get('Content-Type','?')} {len(r.text)}B"


def find_covers(html):
    found = []
    for rx in (OG_RE, OG_RE2):
        found += rx.findall(html)
    imgs = IMG_RE.findall(html)
    # Heuristic: covers usually have 'cover', 'front', 'page', a date, or live on
    # an image CDN. Surface the most cover-like first, but show all candidates.
    def score(u):
        u_l = u.lower()
        s = 0
        for kw in ("cover", "front", "frontpage", "page", "newspaper", "thumb"):
            if kw in u_l:
                s += 2
        if re.search(r"/20\d\d[/-]?\d\d", u_l):  # a date in the path
            s += 3
        if any(c in u_l for c in ("kiosko", "freedomforum", "cloudfront",
                                  "amazonaws", "frontpages")):
            s += 1
        return -s
    imgs = sorted(set(imgs), key=score)
    return found, imgs[:8]


def main():
    session = requests.Session()
    today = datetime.now(timezone.utc).date()
    print(f"Probe date: {today}\n")
    for name, urls in PAPERS.items():
        print(f"=== {name} ===")
        hit = False
        for url in urls:
            r, status = fetch(session, url)
            print(f"  GET {url} -> {status}")
            if not r or r.status_code != 200 or "html" not in \
                    r.headers.get("Content-Type", ""):
                continue
            og, imgs = find_covers(r.text)
            for u in og:
                print(f"      FOUND og:image -> {u}")
                hit = True
            for u in imgs:
                print(f"      img candidate -> {u}")
            if og or imgs:
                hit = True
                break
        if not hit:
            print("      (no cover image found)")
        print()


if __name__ == "__main__":
    main()
