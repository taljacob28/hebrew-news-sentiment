"""
SQLite storage for scraped articles and their sentiment scores.

Schema is intentionally flat: one row per article, with all metadata and
classification results denormalized for easy querying from Streamlit and
direct CSV export to Tableau.

Sentiment columns (eight total covering both passes):
  sentiment_label, sentiment_score, sentiment_neg_score,
  sentiment_neu_score, sentiment_pos_score, sentiment_model
    -> classification on combined headline + snippet text
  headline_sentiment_label, headline_sentiment_score, headline_sentiment_neg_score,
  headline_sentiment_neu_score, headline_sentiment_pos_score, headline_sentiment_model
    -> classification on the headline alone
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DB_PATH

logger = logging.getLogger(__name__)

Base = declarative_base()


class ArticleRecord(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hash = Column(String(32), unique=True, nullable=False, index=True)

    source = Column(String(64), nullable=False, index=True)
    language = Column(String(8), nullable=False)
    url = Column(String(1024), nullable=False)
    headline = Column(Text, nullable=False)
    snippet = Column(Text)
    published_at = Column(DateTime, index=True)
    topic = Column(String(32), nullable=False, index=True)

    # Sentiment over combined headline + snippet
    sentiment_label = Column(String(16), index=True)
    sentiment_score = Column(Float)
    sentiment_neg_score = Column(Float)
    sentiment_neu_score = Column(Float)
    sentiment_pos_score = Column(Float)
    sentiment_model = Column(String(128))

    # Sentiment over headline only (for divergence analysis)
    headline_sentiment_label = Column(String(16), index=True)
    headline_sentiment_score = Column(Float)
    headline_sentiment_neg_score = Column(Float)
    headline_sentiment_neu_score = Column(Float)
    headline_sentiment_pos_score = Column(Float)
    headline_sentiment_model = Column(String(128))

    # Emotion, entities, topic (from Claude API)
    emotion_label = Column(String(32), index=True)
    emotion_intensity = Column(Float)
    entities_json = Column(Text)
    topic_label = Column(String(128), index=True)
    topic_master = Column(String(64), index=True)
    topic_confidence = Column(Float)

    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Centralized list of optional fields the save layer should forward from
# the input dict if present. Keeps save_article tidy and easy to extend.
OPTIONAL_FIELDS = [
    "sentiment_label", "sentiment_score",
    "sentiment_neg_score", "sentiment_neu_score", "sentiment_pos_score",
    "sentiment_model",
    "headline_sentiment_label", "headline_sentiment_score",
    "headline_sentiment_neg_score", "headline_sentiment_neu_score",
    "headline_sentiment_pos_score", "headline_sentiment_model",
    "emotion_label", "emotion_intensity",
    "entities_json",
    "topic_label", "topic_master", "topic_confidence",
]


class Database:
    """Wrapper around SQLAlchemy session management with project-specific helpers."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, future=True)
        Base.metadata.create_all(self.engine)
        logger.info(f"Database ready at {self.db_path}")

    @contextmanager
    def session(self):
        """Context manager for safe session handling."""
        sess = self.SessionLocal()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def article_exists(self, article_hash: str) -> bool:
        """Check if an article with this hash is already stored."""
        with self.session() as sess:
            result = sess.execute(
                select(ArticleRecord.id).where(ArticleRecord.hash == article_hash)
            ).scalar_one_or_none()
            return result is not None

    def save_article(self, article_dict: dict) -> bool:
        """
        Insert one article. Returns True if inserted, False if duplicate.
        Expects a flat dict with all ArticleRecord fields.
        """
        article_hash = article_dict["hash"]
        if self.article_exists(article_hash):
            return False

        # Convert ISO date string back to datetime if present
        published_at = article_dict.get("published_at")
        if isinstance(published_at, str):
            from dateutil import parser as date_parser
            try:
                published_at = date_parser.parse(published_at)
            except (ValueError, TypeError):
                published_at = None

        # Required fields
        record_kwargs = dict(
            hash=article_hash,
            source=article_dict["source"],
            language=article_dict["language"],
            url=article_dict["url"],
            headline=article_dict["headline"],
            snippet=article_dict.get("snippet", ""),
            published_at=published_at,
            topic=article_dict["topic"],
        )

        # Optional fields forwarded if present in the input dict
        for field in OPTIONAL_FIELDS:
            if field in article_dict:
                record_kwargs[field] = article_dict[field]

        record = ArticleRecord(**record_kwargs)

        with self.session() as sess:
            sess.add(record)
        return True

    def save_many(self, articles: List[dict]) -> dict:
        """Bulk save with duplicate handling. Returns counts."""
        inserted = 0
        skipped = 0
        for art in articles:
            if self.save_article(art):
                inserted += 1
            else:
                skipped += 1
        return {"inserted": inserted, "skipped": skipped}

    def fetch_all_as_dataframe(self):
        """Load all articles into a Pandas DataFrame for analytics."""
        import pandas as pd
        with self.engine.connect() as conn:
            return pd.read_sql_table("articles", conn, parse_dates=["published_at", "scraped_at"])

    def count(self) -> int:
        """Total article count."""
        with self.session() as sess:
            return sess.query(ArticleRecord).count()

    def count_by_source(self) -> dict:
        """Article counts per source."""
        with self.session() as sess:
            from sqlalchemy import func
            rows = sess.query(
                ArticleRecord.source, func.count(ArticleRecord.id)
            ).group_by(ArticleRecord.source).all()
            return dict(rows)


# Module-level singleton
_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = get_db()
    print(f"Total articles: {db.count()}")
    print(f"By source: {db.count_by_source()}")
