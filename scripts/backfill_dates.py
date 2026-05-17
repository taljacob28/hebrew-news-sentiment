"""
Backfill missing publish dates for articles already in the database.

For every article where published_at is NULL but a URL exists, the script
fetches the page HTML and tries to extract a date from JSON-LD structured data
or standard meta tags. Successful matches are written back to the database.

Run with:
    python scripts/backfill_dates.py
    python scripts/backfill_dates.py --dry-run     (preview without writing)
    python scripts/backfill_dates.py --limit 20    (try the first 20 only)
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import USER_AGENT, REQUEST_TIMEOUT
from src.database import ArticleRecord, get_db

logger = logging.getLogger(__name__)


META_SELECTORS = [
    ('meta[property="article:published_time"]', "content"),
    ('meta[name="publish-date"]', "content"),
    ('meta[itemprop="datePublished"]', "content"),
    ("time[datetime]", "datetime"),
]


def extract_date(soup):
    """Same logic as the updated archive_scrapers._extract_date_from_meta."""
    for selector, attr in META_SELECTORS:
        tag = soup.select_one(selector)
        if tag and tag.get(attr):
            try:
                return date_parser.parse(tag[attr])
            except (ValueError, TypeError):
                continue

    for script in soup.select('script[type="application/ld+json"]'):
        text = script.string or script.get_text() or ""
        for key in ("datePublished", "dateCreated", "uploadDate"):
            match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', text)
            if match:
                try:
                    return date_parser.parse(match.group(1))
                except (ValueError, TypeError):
                    continue
    return None


def fetch_date(session, url):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        soup = BeautifulSoup(resp.content, "lxml")
        dt = extract_date(soup)
        if dt is None:
            return None, "no date found"
        # Strip timezone to match how the rest of the pipeline stores datetimes
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt, "ok"
    except Exception as e:
        return None, f"error: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be updated without writing.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process only the first N articles. 0 means all.")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Seconds to wait between requests.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    db = get_db()
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Accept-Language": "he,en;q=0.9",
    })

    with db.session() as sess:
        query = sess.query(ArticleRecord).filter(ArticleRecord.published_at.is_(None))
        total = query.count()
        if args.limit:
            query = query.limit(args.limit)
        records = query.all()

        logger.info(f"Articles with NULL published_at: {total}")
        logger.info(f"Processing: {len(records)}")
        if args.dry_run:
            logger.info("DRY RUN, no writes will happen.")

        updated = 0
        failed = 0
        per_source = {}

        for i, rec in enumerate(records, start=1):
            dt, status = fetch_date(session, rec.url)
            src = rec.source
            per_source.setdefault(src, {"ok": 0, "fail": 0})
            if dt:
                per_source[src]["ok"] += 1
                updated += 1
                if not args.dry_run:
                    rec.published_at = dt
                if i % 10 == 0 or i == len(records):
                    logger.info(f"[{i}/{len(records)}] {src}: {dt.date()} ({status})")
            else:
                per_source[src]["fail"] += 1
                failed += 1
                logger.info(f"[{i}/{len(records)}] {src}: SKIP ({status}) - {rec.url[:80]}")

            time.sleep(args.delay)

        if not args.dry_run:
            sess.commit()

    print("\n" + "=" * 60)
    print(f"DONE. Updated: {updated} | Failed: {failed} | Total tried: {len(records)}")
    print("Per source:")
    for src, c in sorted(per_source.items()):
        print(f"  {src:18s}  ok={c['ok']:>4}  fail={c['fail']:>4}")
    if args.dry_run:
        print("\nDry run, no changes written. Remove --dry-run to commit.")


if __name__ == "__main__":
    main()
