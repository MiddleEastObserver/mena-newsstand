#!/usr/bin/env python3
"""One-off diagnostic: which Arabic newspaper covers can the GitHub runner
actually fetch? Tries a list of candidates on Kiosko (today + yesterday, a few
slug spellings each) and Freedom Forum, and prints which return a real image.

Run it from the Actions tab, read the log, then tell Claude which line says OK
so the winner can be baked into fetch_frontpages.py.
"""
import requests
from datetime import datetime, timedelta, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 25
MIN_BYTES = 12000

today = datetime.now(timezone.utc).date()
DATES = [today, today - timedelta(days=1)]

# Kiosko candidates: (label, geo, [slug spellings to try])
KIOSKO = [
    ("Al-Ahram (Egypt)",        "eg", ["al_ahram", "al-ahram"]),
    ("Al-Masry Al-Youm (Egypt)","eg", ["al_masry_al_youm", "almasry_alyoum"]),
    ("Al-Akhbar (Egypt)",       "eg", ["al_akhbar", "al-akhbar"]),
    ("Al-Gomhuria (Egypt)",     "eg", ["al_gomhuria", "al_gomhuriah"]),
    ("Al-Watan (Egypt)",        "eg", ["al_watan", "al-watan"]),
    ("Al-Shorouk (Egypt)",      "eg", ["al_shorouk", "ash_shorouk"]),
    ("Youm7 (Egypt)",           "eg", ["youm7", "el_youm_7"]),
    ("Al-Dustour (Egypt)",      "eg", ["al_dustour", "ad_dustour"]),
    ("Asharq Al-Awsat",         "asi",["asharq_al_awsat", "ash_sharq_al_awsat"]),
    ("Al-Quds Al-Arabi",        "uk", ["al_quds_al_arabi", "alquds_alarabi"]),
    ("An-Nahar (Lebanon)",      "asi",["an_nahar", "annahar"]),
    ("Al-Bayan (UAE)",          "asi",["al_bayan"]),
    ("Al-Ittihad (UAE)",        "asi",["al_ittihad"]),
    ("Al-Khaleej (UAE)",        "asi",["al_khaleej"]),
    ("Al-Riyadh (Saudi)",       "asi",["al_riyadh", "arriyadh"]),
    ("Okaz (Saudi)",            "asi",["okaz", "ukaz"]),
    ("Al-Jazirah (Saudi)",      "asi",["al_jazirah", "aljazirah"]),
    ("Ad-Dustour (Jordan)",     "asi",["ad_dustour_jo", "addustour"]),
]

# Freedom Forum candidates: (label, [code spellings])
FF = [
    ("Egypt / Al-Ahram",  ["EGY_AA", "EGY_AHR"]),
    ("Jordan",            ["JOR_JT", "JOR"]),
    ("Lebanon",           ["LBN_DS", "LBN"]),
    ("Saudi Arabia",      ["SAU_AW", "SAU"]),
]


def referer(u):
    if "kiosko" in u:
        return "https://en.kiosko.net/"
    return "https://www.freedomforum.org/todaysfrontpages/"


def get(session, u):
    try:
        r = session.get(u, timeout=TIMEOUT, headers={
            "User-Agent": UA, "Referer": referer(u),
            "Accept": "image/avif,image/webp,image/*,*/*"})
    except Exception as e:
        return None, f"ERR {e}"
    ct = r.headers.get("Content-Type", "")
    ok = r.status_code == 200 and ct.startswith("image/") and len(r.content) >= MIN_BYTES
    return ok, f"{r.status_code} {ct or '?'} {len(r.content)}B"


def main():
    s = requests.Session()
    print("==== KIOSKO ====")
    for label, geo, slugs in KIOSKO:
        winner = None
        for d in DATES:
            for slug in slugs:
                u = f"https://img.kiosko.net/{d:%Y/%m/%d}/{geo}/{slug}.750.jpg"
                ok, info = get(s, u)
                if ok:
                    winner = (geo, slug, d, u)
                    break
            if winner:
                break
        if winner:
            geo, slug, d, u = winner
            print(f"OK  {label:26s} -> kiosko {geo}/{slug}  ({d})  {u}")
        else:
            print(f"--  {label:26s} (last: {info})")

    print("\n==== FREEDOM FORUM ====")
    for label, codes in FF:
        winner = None
        for d in DATES:
            for code in codes:
                u = f"https://cdn.freedomforum.org/dfp/jpg{d.day}/lg/{code}.jpg"
                ok, info = get(s, u)
                if ok:
                    winner = (code, d, u)
                    break
            if winner:
                break
        if winner:
            code, d, u = winner
            print(f"OK  {label:26s} -> ff {code}  ({d})  {u}")
        else:
            print(f"--  {label:26s} (last: {info})")


if __name__ == "__main__":
    main()
