"""
Data loading and preprocessing for the Israeli Media Framing Tracker.

All loaders return clean, quality-filtered DataFrames ready for analysis.
The rest of the app should never touch raw CSV files directly.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "exports"
ARTICLES_PATH = DATA_DIR / "articles_final.csv"
ENTITIES_PATH = DATA_DIR / "entities_final.csv"

MIN_ENTITY_MENTIONS = 10
SOURCE_ORDER = ["Walla", "Ynet", "Globes", "Jerusalem Post", "Channel 14"]
LEAN_ORDER = ["Left", "Center-Left", "Center", "Center-Right", "Right"]
EMOTION_ORDER = [
    "Anger", "Fear", "Sadness", "Disgust",
    "Anticipation", "Surprise",
    "Joy", "Pride", "Neutral",
]


def load_articles() -> pd.DataFrame:
    """Load article-level data, apply quality filters, return clean DataFrame."""
    df = pd.read_csv(ARTICLES_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    mask = (
        df["has_quality_snippet"].astype(bool)
        & df["has_full_analysis"].astype(bool)
        & ~df["is_duplicate"].astype(bool)
    )
    df = df.loc[mask].reset_index(drop=True)

    df["source_label"] = pd.Categorical(df["source_label"], categories=SOURCE_ORDER, ordered=True)
    df["source_lean"] = pd.Categorical(df["source_lean"], categories=LEAN_ORDER, ordered=True)
    return df


def load_entities() -> pd.DataFrame:
    """Load entity-level data, apply quality filters, return clean DataFrame."""
    df = pd.read_csv(ENTITIES_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    mask = (
        df["has_quality_snippet"].astype(bool)
        & ~df["is_duplicate"].astype(bool)
    )
    df = df.loc[mask].reset_index(drop=True)

    df["source_label"] = pd.Categorical(df["source_label"], categories=SOURCE_ORDER, ordered=True)
    df["source_lean"] = pd.Categorical(df["source_lean"], categories=LEAN_ORDER, ordered=True)
    return df


def top_entities(entities_df: pd.DataFrame, min_mentions: int = MIN_ENTITY_MENTIONS) -> pd.DataFrame:
    """
    Return entities mentioned at least `min_mentions` times,
    with mention count and dominant entity type.
    """
    counts = entities_df["entity_name"].value_counts()
    top = counts[counts >= min_mentions].rename_axis("entity_name").reset_index(name="mention_count")

    type_mode = (
        entities_df.groupby("entity_name")["entity_type"]
        .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "Unknown")
    )
    top["entity_type"] = top["entity_name"].map(type_mode)
    return top


def entity_mentions(entities_df: pd.DataFrame, entity_name: str) -> pd.DataFrame:
    """Return all mentions of a specific entity."""
    return entities_df.loc[entities_df["entity_name"] == entity_name].copy()


def topic_articles(articles_df: pd.DataFrame, topic: str) -> pd.DataFrame:
    """Return all articles whose topic_master matches the given topic."""
    return articles_df.loc[articles_df["topic_master"] == topic].copy()
