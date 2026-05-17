"""
Pipeline orchestrator: scrape -> classify -> store.

Run from the command line:

    python pipeline.py --run                    # one-shot full pipeline (RSS only)
    python pipeline.py --archive --days 30      # fetch archive (last 30 days)
    python pipeline.py --stats                  # print database statistics
    python pipeline.py --export csv             # export articles to CSV (for Tableau)
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from src.scrapers import fetch_all
from src.nlp import get_classifier
from src.database import get_db
from src.config import DATA_DIR

logger = logging.getLogger(__name__)


def run_pipeline(skip_classification: bool = False, use_archive: bool = False, days_back: int = 30) -> dict:
    """Execute the full pipeline once."""
    logger.info("Starting pipeline run")
    started = datetime.utcnow()

    if use_archive:
        from archive_scrapers import fetch_archives
        logger.info(f"Fetching archive for last {days_back} days")
        articles = fetch_archives(days_back=days_back)
    else:
        articles = fetch_all()

    logger.info(f"Fetched {len(articles)} relevant articles total")

    if not articles:
        logger.warning("No articles fetched, ending pipeline")
        return {"fetched": 0, "inserted": 0, "skipped_duplicates": 0, "elapsed_seconds": 0}

    if skip_classification:
        article_dicts = [a.to_dict() for a in articles]
    else:
        classifier = get_classifier()
        article_dicts = []

        # classify_article now returns a dict with both combined-text and
        # headline-only sentiment fields (sentiment_* and headline_sentiment_*).
        for article in tqdm(articles, desc="Classifying", unit="article"):
            d = article.to_dict()
            sentiment_fields = classifier.classify_article(
                article.headline, article.snippet, article.language
            )
            if sentiment_fields:
                d.update(sentiment_fields)
            article_dicts.append(d)

    db = get_db()
    stats = db.save_many(article_dicts)
    elapsed = (datetime.utcnow() - started).total_seconds()

    result = {
        "fetched": len(articles),
        "inserted": stats["inserted"],
        "skipped_duplicates": stats["skipped"],
        "elapsed_seconds": round(elapsed, 1),
    }
    logger.info(f"Pipeline complete: {result}")
    return result


def print_stats():
    db = get_db()
    total = db.count()
    by_source = db.count_by_source()
    print(f"\n=== Database Stats ===")
    print(f"Total articles: {total}")
    print(f"\nBy source:")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count}")


def export_csv(output_path: Path = None) -> Path:
    if output_path is None:
        output_path = DATA_DIR / "exports" / "articles_latest.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    df = db.fetch_all_as_dataframe()
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"Exported {len(df)} articles -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Hebrew News Sentiment pipeline")
    parser.add_argument("--run", action="store_true", help="Run RSS pipeline once")
    parser.add_argument("--archive", action="store_true", help="Run archive pipeline (deep history)")
    parser.add_argument("--days", type=int, default=30, help="Days back for archive (default 30)")
    parser.add_argument("--skip-nlp", action="store_true", help="Skip classification (storage test)")
    parser.add_argument("--stats", action="store_true", help="Print database statistics")
    parser.add_argument("--export", type=str, choices=["csv"], help="Export data (csv for Tableau)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    if args.run:
        result = run_pipeline(skip_classification=args.skip_nlp, use_archive=False)
        print(f"\nPipeline result: {result}")

    if args.archive:
        result = run_pipeline(
            skip_classification=args.skip_nlp,
            use_archive=True,
            days_back=args.days,
        )
        print(f"\nArchive pipeline result: {result}")

    if args.stats:
        print_stats()

    if args.export == "csv":
        path = export_csv()
        print(f"\nExported to: {path}")

    if not any([args.run, args.archive, args.stats, args.export]):
        parser.print_help()


if __name__ == "__main__":
    main()
