"""
Core analytical metrics for the Israeli Media Framing Tracker.

Three primary metrics power the tool.

1. Adversarial Coverage Score
   Mean sentiment intensity across a group of articles. Range: -1 (fully adversarial)
   to +1 (fully sympathetic). In practice Israeli news skews toward zero and below,
   which is why we call this an "adversarial" score rather than a generic "sentiment"
   one. The metric itself is symmetric; the name reflects the empirical distribution
   in this domain.

   adversarial_score = mean(pos_score - neg_score) over the group's articles
   (sentiment_intensity is precomputed in the source data).

2. Polarization Index
   Spread of Adversarial Scores across groups (either media sources or political leans).
   A high value means the same entity or topic is framed very differently by different
   camps. Reported as both max-min spread and standard deviation across group means.

3. Emotion Fingerprint
   Normalized distribution of dominant emotion labels per group. Enables visual
   comparison of how different outlets emotionally code the same coverage.

All functions accept a DataFrame and return either a DataFrame or a dict.
No I/O, no plotting. Pure analytics so the same code powers the Streamlit app
and any notebooks.
"""

from typing import Iterable

import pandas as pd

INTENSITY_COL = "sentiment_intensity"
EMOTION_COL = "emotion_label_clean"


# Four-bucket emotion taxonomy used by the radar charts.
# Hostile  - attack or disapproval framing aimed at an actor.
# Anxious  - worry or distress framing aimed at a situation.
# Hopeful  - forward-looking positive framing.
# Neutral  - observational, factual, or simply unexpected.
EMOTION_REGISTERS = {
    "anger": "Hostile",
    "disgust": "Hostile",
    "contempt": "Hostile",
    "disappointment": "Hostile",
    "fear": "Anxious",
    "sadness": "Anxious",
    "anxiety": "Anxious",
    "tension": "Anxious",
    "tension/anxiety": "Anxious",
    "concern": "Anxious",
    "anticipation": "Hopeful",
    "joy": "Hopeful",
    "pride": "Hopeful",
    "relief": "Hopeful",
    "neutral": "Neutral",
    "surprise": "Neutral",
}

REGISTER_ORDER = ["Hostile", "Anxious", "Hopeful", "Neutral"]


def emotion_register(emotion) -> str:
    """Map one raw emotion label to its register. Unknown labels return 'Other'."""
    if not isinstance(emotion, str):
        return "Other"
    return EMOTION_REGISTERS.get(emotion.lower(), "Other")


def register_fingerprint(df: pd.DataFrame, group_by: str) -> pd.DataFrame:
    """
    Cross-tab of group vs the four emotion registers, normalized by row.
    Rows are groups. Columns are register percentages (0..1) summing to 1.
    Columns are forced to the canonical order so radar axes stay consistent
    across entity or topic selections.
    """
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["register"] = work[EMOTION_COL].apply(emotion_register)
    ct = pd.crosstab(work[group_by], work["register"], normalize="index")
    ordered = [r for r in REGISTER_ORDER if r in ct.columns]
    others = [c for c in ct.columns if c not in REGISTER_ORDER]
    return ct[ordered + others]


def adversarial_score(df: pd.DataFrame, group_by: str) -> pd.DataFrame:
    """
    Compute mean Adversarial Coverage Score per group.

    Returns a DataFrame with columns: <group_by>, adversarial_score, article_count, std.
    Groups with zero articles are dropped.
    """
    if df.empty:
        return pd.DataFrame(columns=[group_by, "adversarial_score", "article_count", "std"])

    agg = (
        df.groupby(group_by, observed=True)
        .agg(
            adversarial_score=(INTENSITY_COL, "mean"),
            article_count=(INTENSITY_COL, "count"),
            std=(INTENSITY_COL, "std"),
        )
        .reset_index()
    )
    return agg.loc[agg["article_count"] > 0].reset_index(drop=True)


def polarization_index(df: pd.DataFrame, group_by: str, min_group_size: int = 2) -> dict:
    """
    Quantify how polarized framing is across groups.

    polarization = max(group_mean) - min(group_mean)
    std_across_groups = std of group means

    Groups with fewer than `min_group_size` articles are excluded so a single
    outlier article cannot dominate the spread.
    """
    if df.empty:
        return _empty_polarization()

    counts = df.groupby(group_by, observed=True)[INTENSITY_COL].count()
    valid_groups = counts[counts >= min_group_size].index
    valid = df.loc[df[group_by].isin(valid_groups)]
    if valid.empty:
        return _empty_polarization()

    means = valid.groupby(group_by, observed=True)[INTENSITY_COL].mean().dropna()
    if len(means) < 2:
        return _empty_polarization(n_groups=len(means))

    return {
        "polarization": float(means.max() - means.min()),
        "std_across_groups": float(means.std(ddof=0)),
        "n_groups": int(len(means)),
        "max_group": str(means.idxmax()),
        "max_value": float(means.max()),
        "min_group": str(means.idxmin()),
        "min_value": float(means.min()),
        "group_means": means.to_dict(),
    }


def _empty_polarization(n_groups: int = 0) -> dict:
    return {
        "polarization": float("nan"),
        "std_across_groups": float("nan"),
        "n_groups": n_groups,
        "max_group": None,
        "max_value": float("nan"),
        "min_group": None,
        "min_value": float("nan"),
        "group_means": {},
    }


def emotion_fingerprint(df: pd.DataFrame, group_by: str) -> pd.DataFrame:
    """
    Cross-tab of group vs emotion, normalized by row.
    Rows are groups. Columns are emotion percentages (0 to 1) summing to 1 per row.
    """
    if df.empty:
        return pd.DataFrame()
    return pd.crosstab(df[group_by], df[EMOTION_COL], normalize="index")


def entity_adversarial_by_source(entities_df: pd.DataFrame, entity_name: str) -> pd.DataFrame:
    """Adversarial Score per source for a specific entity."""
    sub = entities_df.loc[entities_df["entity_name"] == entity_name]
    return adversarial_score(sub, group_by="source_label")


def entity_polarization(
    entities_df: pd.DataFrame,
    entity_name: str,
    min_group_size: int = 2,
) -> dict:
    """Polarization Index for an entity across media sources."""
    sub = entities_df.loc[entities_df["entity_name"] == entity_name]
    result = polarization_index(sub, group_by="source_label", min_group_size=min_group_size)
    result["entity_name"] = entity_name
    result["total_mentions"] = int(len(sub))
    return result


def topic_adversarial_by_lean(articles_df: pd.DataFrame, topic: str) -> pd.DataFrame:
    """Adversarial Score per political lean for a specific topic."""
    sub = articles_df.loc[articles_df["topic_master"] == topic]
    return adversarial_score(sub, group_by="source_lean")


def topic_polarization(
    articles_df: pd.DataFrame,
    topic: str,
    min_group_size: int = 2,
) -> dict:
    """Polarization Index for a topic across political leans."""
    sub = articles_df.loc[articles_df["topic_master"] == topic]
    result = polarization_index(sub, group_by="source_lean", min_group_size=min_group_size)
    result["topic"] = topic
    result["total_articles"] = int(len(sub))
    return result


def rank_entities_by_polarization(
    entities_df: pd.DataFrame,
    entity_list: Iterable[str],
    min_group_size: int = 2,
    min_sources: int = 3,
) -> pd.DataFrame:
    """
    Rank entities from most polarizing to least.

    Entities covered by fewer than `min_sources` sources are excluded by default
    to avoid inflating the index based on thin coverage. Set min_sources=0 to disable.
    """
    rows = []
    for name in entity_list:
        p = entity_polarization(entities_df, name, min_group_size=min_group_size)
        if p["n_groups"] < min_sources:
            continue
        rows.append({
            "entity_name": name,
            "total_mentions": p["total_mentions"],
            "polarization": p["polarization"],
            "max_source": p["max_group"],
            "max_value": p["max_value"],
            "min_source": p["min_group"],
            "min_value": p["min_value"],
            "n_sources_covering": p["n_groups"],
        })
    return (
        pd.DataFrame(rows)
        .sort_values("polarization", ascending=False, na_position="last")
        .reset_index(drop=True)
    )


def rank_topics_by_polarization(
    articles_df: pd.DataFrame,
    min_articles: int = 10,
    min_group_size: int = 2,
    min_leans: int = 3,
) -> pd.DataFrame:
    """Same as rank_entities_by_polarization but for topics across political leans."""
    topics = articles_df["topic_master"].value_counts()
    topics = topics[topics >= min_articles].index.tolist()

    rows = []
    for t in topics:
        p = topic_polarization(articles_df, t, min_group_size=min_group_size)
        if p["n_groups"] < min_leans:
            continue
        rows.append({
            "topic": t,
            "total_articles": p["total_articles"],
            "polarization": p["polarization"],
            "max_lean": p["max_group"],
            "max_value": p["max_value"],
            "min_lean": p["min_group"],
            "min_value": p["min_value"],
            "n_leans_covering": p["n_groups"],
        })
    return (
        pd.DataFrame(rows)
        .sort_values("polarization", ascending=False, na_position="last")
        .reset_index(drop=True)
    )


def source_volume_over_time(articles_df: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """Article volume per source over time. Returns a long DataFrame for plotting."""
    if articles_df.empty or articles_df["date"].isna().all():
        return pd.DataFrame(columns=["date", "source_label", "article_count"])
    df = articles_df.dropna(subset=["date"]).copy()
    df["date_bin"] = df["date"].dt.to_period(freq).dt.to_timestamp()
    return (
        df.groupby(["date_bin", "source_label"], observed=True)
        .size()
        .reset_index(name="article_count")
        .rename(columns={"date_bin": "date"})
    )
