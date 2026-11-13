#!/usr/bin/env python3
"""
Refreshes the dashboard's data files. Standard library only, no pip installs.

  data/worldbank.json  <- World Bank API (free, no key)
  data/news.json       <- Google News RSS + DR1 WordPress API (free, no key)

data/monthly.json is NOT touched here. The Dominican Republic doesn't offer an
API for its monthly MITUR numbers, so you update that file by hand.

If a source fails, the old file is kept. A bad network day never wipes your data.
"""
import datetime
import email.utils
import html
import json
import pathlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
HEADERS = {"User-Agent": "dr-tourism-dashboard/1.0 (GitHub Actions)"}

# ---------- World Bank ----------
COUNTRIES = {
    "DOM": "Dominican Republic",
    "JAM": "Jamaica",
    "BHS": "Bahamas",
    "CUB": "Cuba",
    "MEX": "Mexico",
    "CRI": "Costa Rica",
    "PAN": "Panama",
    "ABW": "Aruba",
}
INDICATORS = {
    "ST.INT.ARVL": "International arrivals",
    "ST.INT.RCPT.CD": "Tourism receipts (US$)",
    "ST.INT.RCPT.XP.ZS": "Tourism receipts (% of exports)",
}


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def update_worldbank():
    codes = ";".join(COUNTRIES)
    this_year = datetime.date.today().year
    out = {}
    for ind in INDICATORS:
        url = (
            f"https://api.worldbank.org/v2/country/{codes}/indicator/{ind}"
            f"?format=json&per_page=2000&date=2010:{this_year}"
        )
        payload = json.loads(fetch(url))
        rows = payload[1] if len(payload) > 1 and payload[1] else []
        series = {}
        for row in rows:
            if row["value"] is None:
                continue
            iso = row["countryiso3code"]
            series.setdefault(iso, {})[row["date"]] = row["value"]
        out[ind] = series
        print(f"  World Bank {ind}: {sum(len(v) for v in series.values())} data points")

    if not any(out.values()):
        raise RuntimeError("World Bank returned no data")

    result = {
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "countries": COUNTRIES,
        "indicators": INDICATORS,
        "data": out,
    }
    (DATA / "worldbank.json").write_text(json.dumps(result, indent=1))


# ---------- News / press releases ----------
OFFICIAL_DOMAINS = (
    "mitur.gob.do",
    "presidencia.gob.do",
    "bancentral.gov.do",
    "gob.do",
)

GOOGLE_QUERIES = [
    # (query, language, region, edition)
    ("Dominican Republic tourism arrivals", "en-US", "US", "US:en"),
    ("Puerto Plata tourism OR cruise OR airport", "en-US", "US", "US:en"),
    ("Mitur llegada de visitantes", "es-419", "DO", "DO:es-419"),
    ("Puerto Plata turismo", "es-419", "DO", "DO:es-419"),
    ("site:mitur.gob.do OR site:presidencia.gob.do turismo", "es-419", "DO", "DO:es-419"),
]


def parse_google_rss(query, hl, gl, ceid):
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
    root = ET.fromstring(fetch(url))
    lang = "es" if hl.startswith("es") else "en"
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate")
        src_el = item.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        src_url = src_el.get("url", "") if src_el is not None else ""
        # Google appends " - Publisher" to titles; strip it since we show source separately
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        try:
            when = email.utils.parsedate_to_datetime(pub).astimezone(datetime.timezone.utc)
        except Exception:
            continue
        official = any(d in src_url for d in OFFICIAL_DOMAINS)
        items.append(
            {
                "title": title,
                "url": link,
                "source": source or "Google News",
                "date": when.isoformat(timespec="seconds"),
                "lang": lang,
                "official": official,
            }
        )
    return items


def parse_dr1():
    url = (
        "https://dr1.com/news/wp-json/wp/v2/posts"
        "?search=tourism&per_page=15&_fields=date_gmt,link,title"
    )
    posts = json.loads(fetch(url))
    items = []
    for p in posts:
        when = datetime.datetime.fromisoformat(p["date_gmt"]).replace(tzinfo=datetime.timezone.utc)
        items.append(
            {
                "title": html.unescape(p["title"]["rendered"]),
                "url": p["link"],
                "source": "DR1",
                "date": when.isoformat(timespec="seconds"),
                "lang": "en",
                "official": False,
            }
        )
    return items


def update_news():
    items = []
    for q, hl, gl, ceid in GOOGLE_QUERIES:
        try:
            got = parse_google_rss(q, hl, gl, ceid)
            print(f"  Google News '{q[:40]}': {len(got)} items")
            items += got
        except Exception as exc:
            print(f"  Google News '{q[:40]}' failed: {exc}")
    try:
        got = parse_dr1()
        print(f"  DR1: {len(got)} items")
        items += got
    except Exception as exc:
        print(f"  DR1 failed: {exc}")

    if not items:
        raise RuntimeError("No news items from any source")

    # de-duplicate by lowercase title, newest first
    seen, unique = set(), []
    for it in sorted(items, key=lambda x: x["date"], reverse=True):
        key = it["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)

    result = {
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "items": unique[:60],
    }
    (DATA / "news.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))


def main():
    DATA.mkdir(exist_ok=True)
    for name, fn in (("World Bank", update_worldbank), ("News", update_news)):
        print(f"{name}...")
        try:
            fn()
        except Exception as exc:
            print(f"  {name} FAILED, keeping previous file: {exc}")


if __name__ == "__main__":
    main()
