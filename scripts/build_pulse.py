#!/usr/bin/env python3
"""Builds pulse.json — a media word-cloud from the current headlines.

Runs every refresh (cheap, no API). Counts how many headlines mention each
meaningful term across all titles + snippets, filters stopwords, and records
the matching headlines so the site can show "what's being talked about" and let
a reader click a term to see every headline that mentions it.

Output (pulse.json):
  { "updated": "<ISO>",
    "total_headlines": <int>,
    "terms": [ { "term": "gaza", "count": 12,
                 "headlines": [ {title,url,source,region}, … ] }, … ] }

This is the frequency-only "Pulse"; sentiment / over-time trends can layer on
later using the front-page archive infrastructure.
"""
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT     = Path(__file__).parent.parent
HL_PATH  = ROOT / "headlines.json"
OUT_PATH = ROOT / "pulse.json"

MIN_LEN          = 4    # ignore very short tokens
MAX_TERMS        = 60   # cap the cloud size
MAX_HL_PER_TERM  = 20   # cap stored headlines per term

WORD_RE = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")

# Common English words + news filler that would otherwise dominate the cloud.
STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "had",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his", "how",
    "may", "new", "now", "old", "see", "two", "way", "who", "boy", "did", "its",
    "let", "put", "say", "she", "too", "use", "that", "this", "with", "from",
    "they", "will", "have", "been", "were", "said", "says", "what", "when",
    "where", "which", "their", "there", "would", "could", "should", "about",
    "after", "again", "amid", "among", "over", "into", "more", "than", "then",
    "them", "these", "those", "such", "some", "only", "also", "just", "very",
    "most", "much", "many", "make", "made", "made", "take", "takes", "took",
    "report", "reports", "reported", "according", "news", "latest", "update",
    "updates", "live", "video", "watch", "read", "story", "stories", "today",
    "year", "years", "week", "month", "time", "first", "last", "next", "back",
    "still", "amid", "amids", "while", "during", "before", "between", "against",
    "because", "around", "another", "people", "official", "officials",
    "minister", "government", "country", "countries", "world", "national",
    "international", "former", "leader", "leaders", "president", "say", "set",
    "calls", "call", "called", "warns", "warn", "warned", "plan", "plans",
    "talks", "talk", "deal", "move", "amid", "sees", "could", "amid", "per",
    "via", "amid", "down", "near", "off", "out", "way", "top", "big", "key",
    "amid", "his", "she", "her", "its", "won", "win", "wins", "gets", "amid",
}


def load_headlines() -> dict:
    try:
        return json.loads(HL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def tokens(text: str):
    """Lowercased word tokens, keeping internal apostrophes/hyphens."""
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


# Generic outlet-name words that leak into titles/snippets but aren't topics.
EXTRA_OUTLET_WORDS = {
    "english", "daily", "press", "gazette", "herald", "online", "weekly",
    "tribune", "journal", "post", "wire", "agency", "media", "network",
}


def main():
    data = load_headlines()
    regions = data.get("regions", {})

    # Build a dynamic stopword set from the outlet names so words like "times",
    # "arabiya" or "akhbar" don't dominate the cloud as publisher artifacts.
    stop = set(STOPWORDS) | EXTRA_OUTLET_WORDS
    for outlets in regions.values():
        for outlet in outlets:
            for w in tokens(outlet.get("source", "")):
                # Add the whole token and its hyphen/apostrophe parts, so both
                # "al-akhbar" and "akhbar" are treated as publisher artifacts.
                for part in [w, *re.split(r"['’\-]", w)]:
                    if len(part) >= MIN_LEN:
                        stop.add(part)

    counts   = Counter()                 # term -> # headlines mentioning it
    term_hls = defaultdict(list)         # term -> [headline dicts]
    total    = 0

    for region, outlets in regions.items():
        for outlet in outlets:
            source = outlet.get("source", "")
            for h in outlet.get("headlines", []):
                title = (h.get("title") or "").strip()
                if not title:
                    continue
                total += 1
                blob = f"{title} {h.get('snippet', '')}"
                entry = {"title": title, "url": h.get("url", ""),
                         "source": source, "region": region}
                # Count each distinct term once per headline.
                seen = set()
                for tok in tokens(blob):
                    if (len(tok) >= MIN_LEN and tok not in stop
                            and not tok.isdigit() and tok not in seen):
                        seen.add(tok)
                        counts[tok] += 1
                        if len(term_hls[tok]) < MAX_HL_PER_TERM:
                            term_hls[tok].append(entry)

    # Keep only terms mentioned in at least two headlines — single mentions add
    # noise and rarely reflect a real "topic". (Falls back to >=1 if that empties
    # the cloud on a thin news day.)
    common = [(t, c) for t, c in counts.most_common() if c >= 2][:MAX_TERMS]
    if not common:
        common = counts.most_common(MAX_TERMS)

    terms = [{"term": t, "count": c, "headlines": term_hls[t]} for t, c in common]

    OUT_PATH.write_text(
        json.dumps(
            {"updated": datetime.now(timezone.utc).isoformat(),
             "total_headlines": total, "terms": terms},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote pulse.json — {len(terms)} terms across {total} headlines")


if __name__ == "__main__":
    main()
