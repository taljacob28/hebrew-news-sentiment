"""
Final data preparation for analysis and visualization.

Reads articles_clean.csv (already cleaned and enriched),
applies final filters, drops irrelevant columns, normalizes names,
derives intensity and divergence fields, and produces
articles_final.csv and entities_final.csv.

These are the canonical datasets used by:
- analysis.ipynb (Python exploratory analysis)
- Tableau Public dashboards

Updates in this version:
- Adds sentiment_intensity (pos_score - neg_score), range -1 to +1
- Adds headline_intensity over the headline-only classification
- Adds sentiment_divergence (body intensity - headline intensity)
- Removes the day/month swap workaround (the rebuilt DB has correct dates)
- Outlier filter set to 2025-01-01 to keep a wide forward-looking window
"""

import json
import logging
from pathlib import Path

import pandas as pd

from config import DATA_DIR

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "ynet": "Ynet",
    "walla": "Walla",
    "globes": "Globes",
    "jpost": "Jerusalem Post",
    "c14": "Channel 14",
}

SOURCE_LEAN = {
    "ynet": "Center-Left",
    "walla": "Left",
    "globes": "Center",
    "jpost": "Center-Right",
    "c14": "Right",
}

# Articles before this date are filtered as outliers.
# Wide threshold: anything before 2025 is implausible for the
# ongoing data collection window.
MIN_VALID_DATE = "2025-01-01"


def hour_to_bucket(h):
    """Map hour-of-day to news cycle bucket."""
    if pd.isna(h):
        return "Unknown"
    h = int(h)
    if 5 <= h <= 11:
        return "Morning"
    if 12 <= h <= 16:
        return "Afternoon"
    if 17 <= h <= 20:
        return "Evening"
    return "Night"


def derive_intensity_fields(df):
    """
    Add sentiment_intensity, headline_intensity, and sentiment_divergence.

    intensity = pos_score - neg_score, range -1 (pure negative) to +1 (pure positive).
    divergence = body_intensity - headline_intensity:
      > 0 -> body more positive than headline (softening)
      < 0 -> body more negative than headline (clickbait amplification)
      ~ 0 -> consistent framing across headline and body
    """
    if "sentiment_pos_score" in df.columns and "sentiment_neg_score" in df.columns:
        df["sentiment_intensity"] = (
            df["sentiment_pos_score"].fillna(0) - df["sentiment_neg_score"].fillna(0)
        )
    if "headline_sentiment_pos_score" in df.columns and "headline_sentiment_neg_score" in df.columns:
        df["headline_intensity"] = (
            df["headline_sentiment_pos_score"].fillna(0)
            - df["headline_sentiment_neg_score"].fillna(0)
        )
    if "sentiment_intensity" in df.columns and "headline_intensity" in df.columns:
        df["sentiment_divergence"] = df["sentiment_intensity"] - df["headline_intensity"]
    return df


def prepare_articles():
    exports_dir = DATA_DIR / "exports"
    input_path = exports_dir / "articles_clean.csv"

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    print(f"Loaded {len(df)} articles from {input_path.name}")

    columns_to_drop = ["topic_group", "hash"]
    for col in columns_to_drop:
        if col in df.columns:
            df = df.drop(columns=[col])

    df["source_label"] = df["source"].map(SOURCE_LABELS).fillna(df["source"])
    df["source_lean"] = df["source"].map(SOURCE_LEAN).fillna("Unknown")

    initial_count = len(df)
    df = df[df["is_duplicate"] == False].copy()
    duplicates_removed = initial_count - len(df)
    print(f"Removed {duplicates_removed} duplicate articles")

    initial_count = len(df)
    df = df[df["has_quality_snippet"] == True].copy()
    low_quality_removed = initial_count - len(df)
    print(f"Removed {low_quality_removed} articles with short snippets")

    # Parse dates straight from the DB (no swap workaround needed for the rebuilt DB)
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    # Filter outlier dates (but KEEP rows with missing dates, NaT < anything is False
    # so they would otherwise be silently dropped here).
    initial_count = len(df)
    date_mask = df["published_at"].isna() | (df["published_at"] >= MIN_VALID_DATE)
    df = df[date_mask].copy()
    outliers_removed = initial_count - len(df)
    missing_dates = df["published_at"].isna().sum()
    print(f"Removed {outliers_removed} articles dated before {MIN_VALID_DATE}")
    print(f"Kept {missing_dates} articles with missing dates (will not appear in time-series views)")

    # Derive date-based fields
    df["date"] = df["published_at"].dt.date
    df["week"] = df["published_at"].dt.isocalendar().week
    df["hour"] = df["published_at"].dt.hour
    df["time_of_day"] = df["hour"].apply(hour_to_bucket)

    # Derive intensity fields from the raw probability scores
    df = derive_intensity_fields(df)

    df["sentiment_label"] = df["sentiment_label"].str.title()
    df["emotion_label_clean"] = df["emotion_label_clean"].str.title()
    if "headline_sentiment_label" in df.columns:
        df["headline_sentiment_label"] = df["headline_sentiment_label"].str.title()
    df["language"] = df["language"].map({"he": "Hebrew", "en": "English"}).fillna(df["language"])
    df["topic"] = df["topic"].map({
        "politics": "Politics",
        "security": "Security",
        "both": "Politics + Security"
    }).fillna(df["topic"])

    output_path = exports_dir / "articles_final.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nArticles final: {output_path.name} ({len(df)} rows)")

    # Quick sanity log on the new derived fields
    if "sentiment_intensity" in df.columns:
        print(f"  Sentiment intensity: mean={df['sentiment_intensity'].mean():.3f}, "
              f"min={df['sentiment_intensity'].min():.3f}, "
              f"max={df['sentiment_intensity'].max():.3f}")
    if "sentiment_divergence" in df.columns:
        print(f"  Sentiment divergence: mean={df['sentiment_divergence'].mean():.3f}, "
              f"min={df['sentiment_divergence'].min():.3f}, "
              f"max={df['sentiment_divergence'].max():.3f}")

    return df


def prepare_entities(articles_df):
    exports_dir = DATA_DIR / "exports"
    input_path = exports_dir / "entities_clean.csv"

    if not input_path.exists():
        print("No entities_clean.csv found, skipping")
        return

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    print(f"\nLoaded {len(df)} entity mentions from {input_path.name}")

    df["entity_type"] = df["entity_type"].str.title()
    df["source_label"] = df["source"].map(SOURCE_LABELS).fillna(df["source"])
    df["source_lean"] = df["source"].map(SOURCE_LEAN).fillna("Unknown")
    df["sentiment_label"] = df["sentiment_label"].str.title()
    if "headline_sentiment_label" in df.columns:
        df["headline_sentiment_label"] = df["headline_sentiment_label"].str.title()
    df["language"] = df["language"].map({"he": "Hebrew", "en": "English"}).fillna(df["language"])

    # Filter entities to match the filtered articles
    valid_ids = set(articles_df["id"].unique())
    initial_count = len(df)
    df = df[df["article_id"].isin(valid_ids)].copy()
    removed = initial_count - len(df)
    print(f"Removed {removed} entities tied to filtered articles")

    # Canonicalize entity_type using mode per entity_name.
    initial_types = df["entity_type"].copy()
    canonical_type = df.groupby("entity_name")["entity_type"].agg(
        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]
    )
    df["entity_type"] = df["entity_name"].map(canonical_type)
    changed = (initial_types != df["entity_type"]).sum()
    print(f"Canonicalized entity_type for {changed} rows (mode per entity_name)")

    # Parse dates directly (no swap)
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df["date"] = df["published_at"].dt.date

    # Derive intensity fields per entity row, propagated from the article-level
    # probability scores that data_clean.py inserted into the entities table.
    df = derive_intensity_fields(df)

    output_path = exports_dir / "entities_final.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Entities final: {output_path.name} ({len(df)} rows, {df['entity_name'].nunique()} unique)")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    print("=" * 60)
    print("FINAL DATA PREPARATION")
    print("=" * 60)

    articles = prepare_articles()
    prepare_entities(articles)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print("\nReady for analysis.ipynb and Tableau")


if __name__ == "__main__":
    main()