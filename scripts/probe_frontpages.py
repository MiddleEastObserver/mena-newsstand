#!/usr/bin/env python3
"""
WHAT THIS SCRIPT DOES (plain English)
======================================
This is a one-off TESTER. Run it from GitHub Actions (not locally) so it can
reach CDN endpoints that block residential/sandbox IPs.

It tries a big list of well-known US, European, and MENA papers and checks
which ones actually return a real front-page image.

Sources we probe:
  - Freedom Forum  ("ff")        best for US papers
  - Kiosko         ("kiosko")    best for European papers
  - PressReader    ("pr")        best for MENA/Gulf papers

For MENA papers the CIDs in the candidate list are educated guesses. If all
guesses miss, run the built-in CID discovery scanner (--discover flag) which
probes a range of PressReader CIDs concurrently and prints every CID that
returns a real image — then bake the winners into CANDIDATES.

Results are written to state/probe_results.json.
"""
import concurrent.futures
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 25
MIN_BYTES = 12000

today = datetime.now(timezone.utc).date()
DATES = [today, today - timedelta(days=1)]

# Each candidate lists the id/name/loc/lang we'd use on the site, plus the
# source(s) to try. A source is either:
#   ("ff", "CODE")              Freedom Forum
#   ("kiosko", "geo", "slug")   Kiosko
#   ("pr", "CID")               PressReader CDN (CID = numeric publication id)
# Multiple sources / spellings are tried in order; first hit wins.
CANDIDATES = [
    # ——— United States (Freedom Forum) ———
    {"id": "usa_today", "name": "USA Today", "loc": "USA", "lang": "en",
     "site": "https://www.usatoday.com", "src": [("ff", "USAT")]},
    {"id": "washington_post", "name": "The Washington Post", "loc": "USA", "lang": "en",
     "site": "https://www.washingtonpost.com", "src": [("ff", "DC_WP")]},
    {"id": "la_times", "name": "Los Angeles Times", "loc": "USA", "lang": "en",
     "site": "https://www.latimes.com", "src": [("ff", "CA_LAT")]},
    {"id": "chicago_tribune", "name": "Chicago Tribune", "loc": "USA", "lang": "en",
     "site": "https://www.chicagotribune.com", "src": [("ff", "IL_CT")]},
    {"id": "boston_globe", "name": "The Boston Globe", "loc": "USA", "lang": "en",
     "site": "https://www.bostonglobe.com", "src": [("ff", "MA_BG")]},
    {"id": "ny_post", "name": "New York Post", "loc": "USA", "lang": "en",
     "site": "https://nypost.com", "src": [("ff", "NY_NYP")]},
    {"id": "newsday", "name": "Newsday", "loc": "USA", "lang": "en",
     "site": "https://www.newsday.com", "src": [("ff", "NY_ND")]},
    {"id": "denver_post", "name": "The Denver Post", "loc": "USA", "lang": "en",
     "site": "https://www.denverpost.com", "src": [("ff", "CO_DP")]},
    {"id": "sf_chronicle", "name": "San Francisco Chronicle", "loc": "USA", "lang": "en",
     "site": "https://www.sfchronicle.com", "src": [("ff", "CA_SFC")]},
    {"id": "houston_chronicle", "name": "Houston Chronicle", "loc": "USA", "lang": "en",
     "site": "https://www.houstonchronicle.com", "src": [("ff", "TX_HC")]},
    {"id": "dallas_news", "name": "The Dallas Morning News", "loc": "USA", "lang": "en",
     "site": "https://www.dallasnews.com", "src": [("ff", "TX_DMN")]},
    {"id": "star_tribune", "name": "Star Tribune", "loc": "USA", "lang": "en",
     "site": "https://www.startribune.com", "src": [("ff", "MN_ST")]},
    {"id": "philly_inquirer", "name": "The Philadelphia Inquirer", "loc": "USA", "lang": "en",
     "site": "https://www.inquirer.com", "src": [("ff", "PA_PI")]},
    {"id": "seattle_times", "name": "The Seattle Times", "loc": "USA", "lang": "en",
     "site": "https://www.seattletimes.com", "src": [("ff", "WA_ST")]},
    {"id": "ajc", "name": "Atlanta Journal-Constitution", "loc": "USA", "lang": "en",
     "site": "https://www.ajc.com", "src": [("ff", "GA_AJC")]},
    {"id": "miami_herald", "name": "Miami Herald", "loc": "USA", "lang": "en",
     "site": "https://www.miamiherald.com", "src": [("ff", "FL_MH")]},
    {"id": "arizona_republic", "name": "The Arizona Republic", "loc": "USA", "lang": "en",
     "site": "https://www.azcentral.com", "src": [("ff", "AZ_AR")]},
    {"id": "washington_times", "name": "The Washington Times", "loc": "USA", "lang": "en",
     "site": "https://www.washingtontimes.com", "src": [("ff", "DC_WT")]},

    # ——— United Kingdom (Kiosko) ———
    {"id": "the_times", "name": "The Times", "loc": "UK", "lang": "en",
     "site": "https://www.thetimes.co.uk", "src": [("kiosko", "uk", "the_times")]},
    {"id": "telegraph", "name": "The Daily Telegraph", "loc": "UK", "lang": "en",
     "site": "https://www.telegraph.co.uk",
     "src": [("kiosko", "uk", "the_daily_telegraph"), ("kiosko", "uk", "telegraph")]},
    {"id": "the_independent", "name": "The Independent", "loc": "UK", "lang": "en",
     "site": "https://www.independent.co.uk",
     "src": [("kiosko", "uk", "the_independent"), ("kiosko", "uk", "independent")]},
    {"id": "i_paper", "name": "The i Paper", "loc": "UK", "lang": "en",
     "site": "https://inews.co.uk",
     "src": [("kiosko", "uk", "i"), ("kiosko", "uk", "inews"), ("kiosko", "uk", "the_i")]},
    {"id": "daily_mail", "name": "Daily Mail", "loc": "UK", "lang": "en",
     "site": "https://www.dailymail.co.uk", "src": [("kiosko", "uk", "daily_mail")]},
    {"id": "metro_uk", "name": "Metro", "loc": "UK", "lang": "en",
     "site": "https://metro.co.uk", "src": [("kiosko", "uk", "metro")]},
    {"id": "guardian", "name": "The Guardian", "loc": "UK", "lang": "en",
     "site": "https://www.theguardian.com", "src": [("kiosko", "uk", "guardian")]},

    # ——— France (Kiosko) ———
    {"id": "le_monde", "name": "Le Monde", "loc": "France", "lang": "fr",
     "site": "https://www.lemonde.fr", "src": [("kiosko", "fr", "le_monde")]},
    {"id": "le_figaro", "name": "Le Figaro", "loc": "France", "lang": "fr",
     "site": "https://www.lefigaro.fr", "src": [("kiosko", "fr", "le_figaro")]},
    {"id": "liberation", "name": "Libération", "loc": "France", "lang": "fr",
     "site": "https://www.liberation.fr", "src": [("kiosko", "fr", "liberation")]},
    {"id": "les_echos", "name": "Les Échos", "loc": "France", "lang": "fr",
     "site": "https://www.lesechos.fr", "src": [("kiosko", "fr", "les_echos")]},
    {"id": "le_parisien", "name": "Le Parisien", "loc": "France", "lang": "fr",
     "site": "https://www.leparisien.fr",
     "src": [("kiosko", "fr", "le_parisien"), ("kiosko", "fr", "aujourd_hui_en_france")]},
    {"id": "la_croix", "name": "La Croix", "loc": "France", "lang": "fr",
     "site": "https://www.la-croix.com", "src": [("kiosko", "fr", "la_croix")]},
    {"id": "l_equipe", "name": "L'Équipe", "loc": "France", "lang": "fr",
     "site": "https://www.lequipe.fr",
     "src": [("kiosko", "fr", "l_equipe"), ("kiosko", "fr", "lequipe")]},

    # ——— Spain (Kiosko) ———
    {"id": "el_pais", "name": "El País", "loc": "Spain", "lang": "es",
     "site": "https://elpais.com", "src": [("kiosko", "es", "el_pais")]},
    {"id": "el_mundo", "name": "El Mundo", "loc": "Spain", "lang": "es",
     "site": "https://www.elmundo.es", "src": [("kiosko", "es", "el_mundo")]},
    {"id": "abc_es", "name": "ABC", "loc": "Spain", "lang": "es",
     "site": "https://www.abc.es", "src": [("kiosko", "es", "abc")]},
    {"id": "la_vanguardia", "name": "La Vanguardia", "loc": "Spain", "lang": "es",
     "site": "https://www.lavanguardia.com", "src": [("kiosko", "es", "la_vanguardia")]},
    {"id": "el_periodico", "name": "El Periódico", "loc": "Spain", "lang": "es",
     "site": "https://www.elperiodico.com", "src": [("kiosko", "es", "el_periodico")]},
    {"id": "marca", "name": "Marca", "loc": "Spain", "lang": "es",
     "site": "https://www.marca.com", "src": [("kiosko", "es", "marca")]},
    {"id": "as_es", "name": "Diario AS", "loc": "Spain", "lang": "es",
     "site": "https://as.com",
     "src": [("kiosko", "es", "diario_as"), ("kiosko", "es", "as")]},

    # ——— Italy (Kiosko) ———
    {"id": "corriere", "name": "Corriere della Sera", "loc": "Italy", "lang": "it",
     "site": "https://www.corriere.it", "src": [("kiosko", "it", "corriere_della_sera")]},
    {"id": "repubblica", "name": "La Repubblica", "loc": "Italy", "lang": "it",
     "site": "https://www.repubblica.it", "src": [("kiosko", "it", "la_repubblica")]},
    {"id": "la_stampa", "name": "La Stampa", "loc": "Italy", "lang": "it",
     "site": "https://www.lastampa.it", "src": [("kiosko", "it", "la_stampa")]},
    {"id": "il_sole", "name": "Il Sole 24 Ore", "loc": "Italy", "lang": "it",
     "site": "https://www.ilsole24ore.com", "src": [("kiosko", "it", "il_sole_24_ore")]},
    {"id": "gazzetta", "name": "La Gazzetta dello Sport", "loc": "Italy", "lang": "it",
     "site": "https://www.gazzetta.it", "src": [("kiosko", "it", "la_gazzetta_dello_sport")]},

    # ——— Germany (Kiosko) ———
    {"id": "die_welt", "name": "Die Welt", "loc": "Germany", "lang": "de",
     "site": "https://www.welt.de", "src": [("kiosko", "de", "die_welt")]},
    {"id": "faz", "name": "Frankfurter Allgemeine", "loc": "Germany", "lang": "de",
     "site": "https://www.faz.net",
     "src": [("kiosko", "de", "frankfurter_allgemeine"), ("kiosko", "de", "faz")]},
    {"id": "sueddeutsche", "name": "Süddeutsche Zeitung", "loc": "Germany", "lang": "de",
     "site": "https://www.sueddeutsche.de",
     "src": [("kiosko", "de", "sueddeutsche_zeitung"), ("kiosko", "de", "sueddeutsche")]},
    {"id": "bild", "name": "Bild", "loc": "Germany", "lang": "de",
     "site": "https://www.bild.de", "src": [("kiosko", "de", "bild")]},
    {"id": "handelsblatt", "name": "Handelsblatt", "loc": "Germany", "lang": "de",
     "site": "https://www.handelsblatt.com", "src": [("kiosko", "de", "handelsblatt")]},
    {"id": "tagesspiegel", "name": "Der Tagesspiegel", "loc": "Germany", "lang": "de",
     "site": "https://www.tagesspiegel.de", "src": [("kiosko", "de", "der_tagesspiegel")]},

    # ——— Middle East / MENA (PressReader CDN) ———
    # CIDs below are best-guess estimates. If these all fail, run with --discover
    # to scan PressReader CID ranges and find the actual values.
    {"id": "gulf_news", "name": "Gulf News", "loc": "UAE", "lang": "en",
     "site": "https://gulfnews.com",
     "src": [("pr", "5285"), ("pr", "4669"), ("pr", "7568"), ("pr", "1125")]},
    {"id": "khaleej_times", "name": "Khaleej Times", "loc": "UAE", "lang": "en",
     "site": "https://www.khaleejtimes.com",
     "src": [("pr", "5286"), ("pr", "4670"), ("pr", "7569")]},
    {"id": "the_national_pr", "name": "The National", "loc": "UAE", "lang": "en",
     "site": "https://www.thenationalnews.com",
     "src": [("pr", "7000"), ("pr", "6500"), ("pr", "5287")]},
    {"id": "gulf_today", "name": "Gulf Today", "loc": "UAE", "lang": "en",
     "site": "https://www.gulftoday.ae",
     "src": [("pr", "8200"), ("pr", "7800"), ("pr", "5288")]},
    {"id": "arab_news", "name": "Arab News", "loc": "Saudi Arabia", "lang": "en",
     "site": "https://www.arabnews.com",
     "src": [("pr", "5846"), ("pr", "4671"), ("pr", "3502"), ("pr", "6700")]},
    {"id": "saudi_gazette", "name": "Saudi Gazette", "loc": "Saudi Arabia", "lang": "en",
     "site": "https://saudigazette.com.sa",
     "src": [("pr", "5847"), ("pr", "6501"), ("pr", "7800")]},
    {"id": "asharq_al_awsat", "name": "Asharq Al-Awsat", "loc": "Pan-Arab", "lang": "ar",
     "site": "https://english.aawsat.com",
     "src": [("pr", "6672"), ("pr", "5848"), ("pr", "4672")]},
    {"id": "the_peninsula", "name": "The Peninsula", "loc": "Qatar", "lang": "en",
     "site": "https://www.thepeninsulaqatar.com",
     "src": [("pr", "7536"), ("pr", "6000"), ("pr", "5849")]},
    {"id": "gulf_times", "name": "Gulf Times", "loc": "Qatar", "lang": "en",
     "site": "https://www.gulf-times.com",
     "src": [("pr", "5850"), ("pr", "4673"), ("pr", "7537")]},
    {"id": "oman_observer", "name": "Oman Observer", "loc": "Oman", "lang": "en",
     "site": "https://www.omanobserver.om",
     "src": [("pr", "5851"), ("pr", "6502"), ("pr", "7538")]},
    {"id": "times_of_oman", "name": "Times of Oman", "loc": "Oman", "lang": "en",
     "site": "https://timesofoman.com",
     "src": [("pr", "5852"), ("pr", "4674"), ("pr", "7539")]},
    {"id": "arab_times", "name": "Arab Times", "loc": "Kuwait", "lang": "en",
     "site": "https://www.arabtimesonline.com",
     "src": [("pr", "5853"), ("pr", "4675"), ("pr", "7540")]},
    {"id": "kuwait_times", "name": "Kuwait Times", "loc": "Kuwait", "lang": "en",
     "site": "https://kuwaittimes.com",
     "src": [("pr", "5854"), ("pr", "4676"), ("pr", "7541")]},
    {"id": "jordan_times", "name": "Jordan Times", "loc": "Jordan", "lang": "en",
     "site": "https://jordantimes.com",
     "src": [("pr", "5855"), ("pr", "4677"), ("pr", "7542")]},
    {"id": "daily_star_leb", "name": "The Daily Star", "loc": "Lebanon", "lang": "en",
     "site": "https://www.dailystar.com.lb",
     "src": [("pr", "5856"), ("pr", "4678"), ("pr", "7543")]},
    {"id": "haaretz_pr", "name": "Haaretz (English)", "loc": "Israel", "lang": "en",
     "site": "https://www.haaretz.com",
     "src": [("pr", "7256"), ("pr", "5857"), ("pr", "3503")]},
    {"id": "jerusalem_post", "name": "Jerusalem Post", "loc": "Israel", "lang": "en",
     "site": "https://www.jpost.com",
     "src": [("pr", "6195"), ("pr", "5858"), ("pr", "3504")]},
]


def candidate_url(src, d) -> str:
    if src[0] == "ff":
        return f"https://cdn.freedomforum.org/dfp/jpg{d.day}/lg/{src[1]}.jpg"
    if src[0] == "kiosko":
        return f"https://img.kiosko.net/{d:%Y/%m/%d}/{src[1]}/{src[2]}.750.jpg"
    if src[0] == "pr":
        return f"https://i.prcdn.co/img?cid={src[1]}&date={d:%Y%m%d}&page=1&width=600"
    raise ValueError(src)


def referer(url: str) -> str:
    if "kiosko" in url:
        return "https://en.kiosko.net/"
    if "prcdn" in url:
        return "https://www.pressreader.com/"
    return "https://www.freedomforum.org/todaysfrontpages/"


def get(session: requests.Session, url: str):
    try:
        r = session.get(url, timeout=TIMEOUT, headers={
            "User-Agent": UA, "Referer": referer(url),
            "Accept": "image/avif,image/webp,image/*,*/*"})
    except Exception as e:
        return False, f"ERR {e}"
    ct = r.headers.get("Content-Type", "")
    ok = r.status_code == 200 and ct.startswith("image/") and len(r.content) >= MIN_BYTES
    return ok, f"{r.status_code} {ct or '?'} {len(r.content)}B"


def _check_cid(args):
    session, cid, d = args
    url = f"https://i.prcdn.co/img?cid={cid}&date={d:%Y%m%d}&page=1&width=600"
    try:
        r = session.get(url, timeout=15, headers={
            "User-Agent": UA,
            "Referer": "https://www.pressreader.com/",
            "Accept": "image/avif,image/webp,image/*,*/*",
        })
        ct = r.headers.get("Content-Type", "")
        ok = r.status_code == 200 and ct.startswith("image/") and len(r.content) >= MIN_BYTES
        return cid, ok, r.status_code, len(r.content)
    except Exception as e:
        return cid, False, "ERR", 0


def discover_pressreader_cids(session: requests.Session) -> list:
    """Scan PressReader CID ranges for today and report every CID that returns
    a valid cover image. Runs concurrently so it finishes in a few minutes.
    CID ranges chosen to cover the most likely eras for MENA publications."""
    # Range 1: established global papers (joined PressReader early ~2005-2012)
    # Range 2: MENA/regional papers (most likely joined 2010-2020)
    # Range 3: newer additions (2018+)
    ranges = (
        list(range(1000, 2001)) +   # 1000 CIDs: early adopters
        list(range(5000, 6001)) +   # 1000 CIDs: mid-era MENA
        list(range(7000, 8001))     # 1000 CIDs: newer additions
    )
    d = today  # scan today's date only

    print(f"\n=== PressReader CID discovery scan: {len(ranges)} CIDs for {d} ===")
    hits = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        futures = {ex.submit(_check_cid, (session, cid, d)): cid for cid in ranges}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            cid, ok, status, size = future.result()
            done += 1
            if ok:
                print(f"  HIT cid={cid:5d} -> {status} {size}B")
                hits.append(cid)
            elif done % 200 == 0:
                print(f"  ... {done}/{len(ranges)} checked, {len(hits)} hits so far")

    hits.sort()
    print(f"\nDiscovery complete: {len(hits)} valid PressReader CIDs found")
    if hits:
        print(f"  CIDs: {hits}")
    else:
        print("  No hits — PressReader CDN may require auth or the ranges were wrong.")
        print("  Check i.prcdn.co accessibility from this runner first.")

    return hits


def main():
    discover = "--discover" in sys.argv

    session = requests.Session()
    results = []
    for c in CANDIDATES:
        winner = None
        last = ""
        for d in DATES:
            for src in c["src"]:
                url = candidate_url(src, d)
                ok, info = get(session, url)
                last = info
                if ok:
                    winner = (src, d, url)
                    break
            if winner:
                break

        row = {
            "id": c["id"], "name": c["name"], "loc": c["loc"], "lang": c["lang"],
            "site": c["site"], "ok": bool(winner),
        }
        if winner:
            src, d, url = winner
            row["src"] = list(src)
            row["date"] = d.isoformat()
            row["url"] = url
            print(f"OK  {c['name']:30s} -> {src}  ({d})")
        else:
            row["src"] = None
            row["last"] = last
            print(f"--  {c['name']:30s} (last: {last})")
        results.append(row)

    out = {
        "ran": datetime.now(timezone.utc).isoformat(),
        "dates_tried": [d.isoformat() for d in DATES],
        "ok_count": sum(1 for r in results if r["ok"]),
        "results": results,
    }

    if discover:
        pr_hits = discover_pressreader_cids(session)
        out["pressreader_discovery"] = {
            "ranges_scanned": "1000-2000, 5000-6000, 7000-8000",
            "date": today.isoformat(),
            "hits": pr_hits,
        }

    out_path = Path(__file__).parent.parent / "state" / "probe_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path} — {out['ok_count']}/{len(results)} reachable")


if __name__ == "__main__":
    main()
