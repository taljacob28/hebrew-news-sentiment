"""
Run Claude analysis on all existing articles in the database.

This script processes articles that haven't been analyzed yet (no emotion_label)
and updates them with emotion, entity, and topic information.
"""

import logging
import time
from sqlalchemy import select, update

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from src.database import get_db, ArticleRecord
from src.claude_analyzer import get_analyzer

logger = logging.getLogger(__name__)


def get_unanalyzed_articles(db):
    """Fetch articles that haven't been analyzed by Claude yet."""
    with db.session() as sess:
        articles = sess.execute(
            select(ArticleRecord).where(ArticleRecord.emotion_label.is_(None))
        ).scalars().all()
        return [{
            "id": a.id,
            "hash": a.hash,
            "headline": a.headline,
            "snippet": a.snippet or "",
        } for a in articles]


def update_article_analysis(db, article_id, analysis_dict):
    """Update a single article with Claude's analysis."""
    with db.session() as sess:
        sess.execute(
            update(ArticleRecord)
            .where(ArticleRecord.id == article_id)
            .values(**analysis_dict)
        )


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    
    db = get_db()
    analyzer = get_analyzer()
    
    articles = get_unanalyzed_articles(db)
    total = len(articles)
    logger.info(f"Found {total} unanalyzed articles")
    
    if total == 0:
        print("All articles already analyzed.")
        return
    
    import sys
    auto_mode = "--auto" in sys.argv
    
    print(f"\nAbout to analyze {total} articles via Claude API.")
    print(f"Estimated cost: ~${total * 0.002:.2f}")
    
    if not auto_mode:
        confirm = input("Continue? (yes/no): ")
        if confirm.lower() not in ("yes", "y"):
            print("Cancelled.")
            return
    else:
        print("Auto mode: proceeding without confirmation")
    
    started = time.time()
    success_count = 0
    error_count = 0
    
    for i, article in enumerate(articles, 1):
        try:
            analysis = analyzer.analyze(article["headline"], article["snippet"])
            if analysis:
                update_article_analysis(db, article["id"], analysis.to_dict())
                success_count += 1
            else:
                error_count += 1
            
            if i % 10 == 0 or i == total:
                elapsed = time.time() - started
                rate = i / elapsed
                remaining = (total - i) / rate if rate > 0 else 0
                logger.info(f"Progress: {i}/{total} ({success_count} ok, {error_count} failed) - "
                            f"~{remaining:.0f}s remaining")
            
            time.sleep(0.3)
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error on article {article['id']}: {e}")
            error_count += 1
    
    elapsed = time.time() - started
    print(f"\n=== Done ===")
    print(f"Analyzed: {success_count}/{total}")
    print(f"Failed: {error_count}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Rate: {success_count/elapsed:.1f} articles/sec")


if __name__ == "__main__":
    main()