"""
Diagnostic for missing publish dates in Walla and Channel 14 articles.

Fetches a few sample URLs and reports every plausible date location in the HTML.
Run with:
    python scripts/diagnose_dates.py
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import USER_AGENT, REQUEST_TIMEOUT


SAMPLE_URLS = {
    "Walla": [
        "https://news.walla.co.il/item/3826909",
        "https://news.walla.co.il/item/3685445",
    ],
    "Channel 14": [
        "https://www.c14.co.il/article/1555285",
        "https://www.c14.co.il/article/1555228",
    ],
}

# Every date-bearing pattern we have seen on Israeli news sites
META_SELECTORS = [
    ('meta[property="article:published_time"]', "content"),
    ('meta[property="og:article:published_time"]', "content"),
    ('meta[property="article:modified_time"]', "content"),
    ('meta[name="publish-date"]', "content"),
    ('meta[name="publishdate"]', "content"),
    ('meta[name="pubdate"]', "content"),
    ('meta[name="date"]', "content"),
    ('meta[name="DC.date.issued"]', "content"),
    ('meta[name="parsely-pub-date"]', "content"),
    ('meta[itemprop="datePublished"]', "content"),
    ('meta[itemprop="dateCreated"]', "content"),
    ("time[datetime]", "datetime"),
    ("time[pubdate]", "datetime"),
]

JSON_LD_SELECTOR = 'script[type="application/ld+json"]'


def try_meta_selectors(soup):
    found = []
    for selector, attr in META_SELECTORS:
        for tag in soup.select(selector):
            val = tag.get(attr)
            if val:
                parsed = safe_parse(val)
                found.append({
                    "selector": selector,
                    "attr": attr,
                    "raw": val.strip()[:80],
                    "parsed": str(parsed) if parsed else "PARSE FAILED",
                })
    return found


def try_json_ld(soup):
    found = []
    for tag in soup.select(JSON_LD_SELECTOR):
        text = tag.string or tag.get_text() or ""
        for key in ["datePublished", "dateCreated", "dateModified", "uploadDate"]:
            m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', text)
            if m:
                raw = m.group(1)
                parsed = safe_parse(raw)
                found.append({
                    "source": "JSON-LD",
                    "key": key,
                    "raw": raw[:80],
                    "parsed": str(parsed) if parsed else "PARSE FAILED",
                })
    return found


def try_time_text(soup):
    """Look for date-looking strings inside any element with date or time in its class."""
    found = []
    candidates = soup.select('[class*="date"], [class*="time"], [class*="Date"], [class*="Time"]')
    for el in candidates[:6]:
        text = el.get_text(" ", strip=True)
        if not text or len(text) > 80:
            continue
        if re.search(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", text) or re.search(r"\d{4}-\d{2}-\d{2}", text):
            parsed = safe_parse(text)
            found.append({
                "selector": el.get("class"),
                "raw": text[:80],
                "parsed": str(parsed) if parsed else "PARSE FAILED",
            })
    return found


def safe_parse(value):
    try:
        return date_parser.parse(value, fuzzy=True)
    except (ValueError, TypeError):
        return None


def diagnose(url):
    print(f"\n{'=' * 60}")
    print(f"URL: {url}")
    print('=' * 60)
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return
        soup = BeautifulSoup(resp.content, "lxml")

        meta_hits = try_meta_selectors(soup)
        print(f"\nMETA / TIME selectors found: {len(meta_hits)}")
        for h in meta_hits:
            print(f"  ✓ {h['selector']:55s} -> {h['raw']:40s} | parsed: {h['parsed']}")

        json_hits = try_json_ld(soup)
        print(f"\nJSON-LD date fields found: {len(json_hits)}")
        for h in json_hits:
            print(f"  ✓ {h['key']:20s} -> {h['raw']:40s} | parsed: {h['parsed']}")

        text_hits = try_time_text(soup)
        print(f"\nDate-looking text in date/time class elements: {len(text_hits)}")
        for h in text_hits:
            print(f"  ✓ class={h['selector']} -> {h['raw']:40s} | parsed: {h['parsed']}")

        if not meta_hits and not json_hits and not text_hits:
            print("\n  ⚠ Nothing useful. Dumping first 800 chars of <head> for inspection:")
            head = soup.find("head")
            if head:
                print(str(head)[:800])

    except Exception as e:
        print(f"  ERROR: {e}")


if __name__ == "__main__":
    for source, urls in SAMPLE_URLS.items():
        print(f"\n\n{'#' * 60}")
        print(f"# {source}")
        print(f"{'#' * 60}")
        for u in urls:
            diagnose(u)
