"""
Data cleaning and enrichment script. Prepares the database for Tableau visualization.

Operations performed:
1. Normalize emotion categories (consolidate edge cases)
2. Mark articles with short snippets (quality flag)
3. Detect and flag duplicate headlines
4. Add derived features (time, length, click-bait, density flags)
5. Export cleaned CSVs ready for Tableau

The articles CSV inherits every column from the DB automatically.
The entities CSV is a manually constructed long-format table with
selected article-level fields propagated to each entity row.
"""

import json
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from database import get_db
from config import DATA_DIR

load_dotenv()
logger = logging.getLogger(__name__)


EMOTION_NORMALIZATION = {
    "frustration": "anger",
    "criticism": "disgust",
}


def normalize_emotions(df):
    """Consolidate edge-case emotion labels into standard categories."""
    df = df.copy()
    df["emotion_label_clean"] = df["emotion_label"].replace(EMOTION_NORMALIZATION)
    changed = (df["emotion_label"] != df["emotion_label_clean"]).sum()
    logger.info(f"Normalized {changed} emotion labels")
    return df


def add_quality_flags(df):
    """Add quality flags for filtering in Tableau."""
    df = df.copy()
    df["snippet_length"] = df["snippet"].fillna("").str.len()
    df["has_quality_snippet"] = df["snippet_length"] >= 50
    df["has_full_analysis"] = df["emotion_label"].notna() & df["topic_label"].notna()
    return df


def detect_duplicates(df):
    """Mark articles with duplicate headlines."""
    df = df.copy()
    df["is_duplicate"] = df["headline"].duplicated(keep="first")
    return df


def add_derived_features(df):
    """Add derived features for richer Tableau analysis."""
    df = df.copy()
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df["hour_of_day"] = df["published_at"].dt.hour
    df["day_of_week"] = df["published_at"].dt.day_name()

    def categorize_time(hour):
        if pd.isna(hour):
            return "Unknown"
        if 6 <= hour < 12:
            return "Morning"
        if 12 <= hour < 17:
            return "Afternoon"
        if 17 <= hour < 22:
            return "Evening"
        return "Night"

    df["time_period"] = df["hour_of_day"].apply(categorize_time)
    df["headline_length"] = df["headline"].fillna("").str.len()
    df["headline_word_count"] = df["headline"].fillna("").str.split().str.len()

    def count_entities(json_str):
        if not json_str or pd.isna(json_str):
            return 0
        try:
            entities = json.loads(json_str)
            return len(entities) if isinstance(entities, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0

    df["entities_count"] = df["entities_json"].apply(count_entities)
    df["has_punctuation"] = df["headline"].fillna("").str.contains(r"[!?]", regex=True)
    df["question_in_headline"] = df["headline"].fillna("").str.contains(r"\?")
    df["headline_starts_uppercase"] = df["headline"].fillna("").str.match(r"^[A-Z]{2,}")
    df["entity_density"] = df.apply(
        lambda row: row["entities_count"] / row["headline_word_count"]
        if row["headline_word_count"] and row["headline_word_count"] > 0 else 0,
        axis=1
    )
    df["is_negative_security"] = (
        (df["sentiment_label"] == "negative") &
        (df["topic"].isin(["security", "both"]))
    )

    logger.info(f"Added derived features")
    logger.info(f"  Time period distribution: {df['time_period'].value_counts().to_dict()}")
    logger.info(f"  Average entities per article: {df['entities_count'].mean():.1f}")
    logger.info(f"  Average headline length: {df['headline_length'].mean():.1f} chars")
    logger.info(f"  Click-bait articles (with !?): {df['has_punctuation'].sum()}")
    logger.info(f"  Negative security articles: {df['is_negative_security'].sum()}")
    return df


def export_clean_csvs(df):
    """Export the cleaned articles and entities CSVs."""
    exports_dir = DATA_DIR / "exports"
    exports_dir.mkdir(exist_ok=True)

    articles_path = exports_dir / "articles_clean.csv"
    df.to_csv(articles_path, index=False, encoding="utf-8-sig")
    logger.info(f"Articles exported: {articles_path} ({len(df)} rows)")

    rows = []
    for _, article in df.iterrows():
        if not article.get("entities_json"):
            continue
        try:
            entities = json.loads(article["entities_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        for ent in entities:
            if not isinstance(ent, dict) or "name" not in ent:
                continue
            rows.append({
                # Identity
                "article_id": article["id"],
                "entity_name": ent.get("name", ""),
                "entity_type": ent.get("type", ""),
                # Article context
                "source": article["source"],
                "language": article["language"],
                "topic": article["topic"],
                "topic_master": article.get("topic_master", ""),
                "topic_label": article.get("topic_label", ""),
                # Sentiment over combined text (raw probabilities + label)
                "sentiment_label": article.get("sentiment_label", ""),
                "sentiment_score": article.get("sentiment_score", 0),
                "sentiment_neg_score": article.get("sentiment_neg_score", 0),
                "sentiment_neu_score": article.get("sentiment_neu_score", 0),
                "sentiment_pos_score": article.get("sentiment_pos_score", 0),
                # Sentiment over headline only
                "headline_sentiment_label": article.get("headline_sentiment_label", ""),
                "headline_sentiment_score": article.get("headline_sentiment_score", 0),
                "headline_sentiment_neg_score": article.get("headline_sentiment_neg_score", 0),
                "headline_sentiment_neu_score": article.get("headline_sentiment_neu_score", 0),
                "headline_sentiment_pos_score": article.get("headline_sentiment_pos_score", 0),
                # Emotion (Claude)
                "emotion_label_clean": article.get("emotion_label_clean", ""),
                # Time
                "published_at": article.get("published_at", ""),
                "time_period": article.get("time_period", ""),
                "day_of_week": article.get("day_of_week", ""),
                # Quality flags
                "is_duplicate": article.get("is_duplicate", False),
                "has_quality_snippet": article.get("has_quality_snippet", False),
            })

    if rows:
        entities_df = pd.DataFrame(rows)
        entities_path = exports_dir / "entities_clean.csv"
        entities_df.to_csv(entities_path, index=False, encoding="utf-8-sig")
        logger.info(f"Entities exported: {entities_path} ({len(entities_df)} rows)")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    print("=" * 60)
    print("DATA CLEANING AND ENRICHMENT PIPELINE")
    print("=" * 60)

    db = get_db()
    df = db.fetch_all_as_dataframe()
    print(f"\nLoaded {len(df)} articles from database")

    print("\n[1/5] Normalizing emotion labels...")
    df = normalize_emotions(df)

    print("\n[2/5] Adding quality flags...")
    df = add_quality_flags(df)

    print("\n[3/5] Detecting duplicates...")
    df = detect_duplicates(df)
    duplicates_found = df["is_duplicate"].sum()
    print(f"  Marked {duplicates_found} duplicate articles")

    print("\n[4/5] Adding derived features...")
    df = add_derived_features(df)

    print("\n[5/5] Exporting clean CSVs...")
    export_clean_csvs(df)

    print("\n" + "=" * 60)
    print("CLEANING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
