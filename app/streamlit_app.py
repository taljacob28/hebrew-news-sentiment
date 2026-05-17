"""
Israeli Media Framing Tracker
A Streamlit dashboard that quantifies how five major Israeli outlets frame political
entities and topics, and where the gap between camps is wide enough to demand a
strategic response.

Run with:
    streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import data_load, metrics, viz


# ----------------------------- Page config -----------------------------

st.set_page_config(
    page_title="Israeli Media Framing Tracker",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------------- Caching -----------------------------

@st.cache_data(show_spinner="Loading data...")
def get_data():
    articles = data_load.load_articles()
    entities = data_load.load_entities()
    top = data_load.top_entities(entities, min_mentions=10)
    return articles, entities, top


articles_df, entities_df, top_entities_df = get_data()


# ----------------------------- Sidebar -----------------------------

with st.sidebar:
    st.title("📰 Media Framing Tracker")
    st.caption("How Israeli media frames political entities and topics, quantified.")

    st.markdown("---")
    st.markdown("### Dataset")
    valid_dates = articles_df["date"].dropna()
    if not valid_dates.empty:
        st.markdown(f"**Period:** {valid_dates.min().date()} to {valid_dates.max().date()}")
    st.markdown(f"**Articles:** {len(articles_df):,}")
    st.markdown(f"**Sources:** {articles_df['source_label'].nunique()}")
    st.markdown(f"**Entity mentions:** {len(entities_df):,}")
    st.markdown(f"**Tracked entities:** {len(top_entities_df)}")

    st.markdown("---")
    with st.expander("About this tool"):
        st.markdown(
            "Built as a data analyst portfolio project. Pipeline ingests RSS and "
            "HTML from Walla, Ynet, Globes, Jerusalem Post and Channel 14, classifies "
            "sentiment in Hebrew (DictaBERT) and English (RoBERTa), enriches with "
            "emotion and entity labels via Claude, and surfaces three custom metrics: "
            "Adversarial Coverage Score, Polarization Index, and Emotion Fingerprint."
        )


# ----------------------------- Header -----------------------------

st.title("Israeli Media Framing Tracker")
st.markdown(
    "**Question:** When five Israeli outlets cover the same entity or topic, "
    "how far apart are their frames, and which camp drives the gap?"
)
st.caption(
    "Portfolio analytics project. Demonstrates an end-to-end NLP pipeline, three "
    "custom metrics (Adversarial Coverage Score, Polarization Index, Emotion "
    "Fingerprint), and analyst-style storytelling on a constrained dataset. "
    "Findings here are illustrative of the methodology, not definitive claims "
    "about Israeli media discourse."
)


# ----------------------------- Tabs -----------------------------

tab_overview, tab_entity, tab_topic, tab_source, tab_method = st.tabs([
    "Overview",
    "Entity Tracker",
    "Topic Polarization",
    "Source Profile",
    "Methodology",
])


# =====================================================================
# TAB 1 - OVERVIEW
# =====================================================================
with tab_overview:
    st.subheader("Coverage at a glance")

    # Data window note - honest about the snapshot nature
    valid_dates = articles_df["date"].dropna()
    if not valid_dates.empty:
        daily_source_count = (
            articles_df.dropna(subset=["date"])
            .groupby("date")["source_label"]
            .nunique()
        )
        dense_days = daily_source_count[daily_source_count >= articles_df["source_label"].nunique()]
        n_no_date = articles_df["date"].isna().sum()
        if not dense_days.empty:
            st.caption(
                f"{len(articles_df):,} articles across {articles_df['source_label'].nunique()} outlets. "
                f"Dense same-day coverage from {dense_days.index.min().date()} to {dense_days.index.max().date()} "
                f"({len(dense_days)} days with all sources present). "
                f"{n_no_date} articles lack a parseable timestamp and are excluded from time-based views only."
            )

    # Rankings reused across KPIs and charts
    entity_ranking = metrics.rank_entities_by_polarization(
        entities_df, top_entities_df["entity_name"].tolist(), min_sources=3
    )
    topic_ranking = metrics.rank_topics_by_polarization(articles_df, min_articles=10, min_leans=3)

    # KPIs - story-bearing, not just counts
    pct_neg = (articles_df["sentiment_label"] == "Negative").mean() * 100
    net_adv = articles_df["sentiment_intensity"].mean()
    top_pol = entity_ranking.iloc[0] if not entity_ranking.empty else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Articles analyzed", f"{len(articles_df):,}")
    k2.metric("% adversarial articles", f"{pct_neg:.1f}%")
    k3.metric("Net Adversarial Score", f"{net_adv:+.2f}")
    if top_pol is not None and pd.notna(top_pol["polarization"]):
        k4.metric(
            "Top polarizing entity",
            str(top_pol["entity_name"]),
            f"Polarization {top_pol['polarization']:.2f}",
            delta_color="off",
        )
    else:
        k4.metric("Top polarizing entity", "n/a")

    st.markdown("---")

    # Row 2: corpus shape + emotional fingerprint
    c1, c2 = st.columns([2, 3])
    with c1:
        st.plotly_chart(
            viz.articles_per_source_bar(articles_df, title="Articles per source"),
            use_container_width=True,
        )
    with c2:
        fingerprint = metrics.emotion_fingerprint(articles_df, group_by="source_label")
        st.plotly_chart(
            viz.source_emotion_heatmap(fingerprint, title="Emotion mix per source"),
            use_container_width=True,
        )

    st.markdown("---")

    # Row 3: source x topic specialization, full width
    st.plotly_chart(
        viz.source_topic_heatmap(
            articles_df,
            top_n_topics=10,
            title="What each outlet covers most (% of its own coverage per topic)",
        ),
        use_container_width=True,
    )

    st.markdown("---")

    # Row 4: polarization rankings
    st.markdown("### Most polarizing entities and topics")
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(
            viz.polarization_ranking(
                entity_ranking, "entity_name", top_n=12,
                title="Entities, ranked by Polarization Index",
            ),
            use_container_width=True,
        )
    with c4:
        st.plotly_chart(
            viz.polarization_ranking(
                topic_ranking, "topic", top_n=12,
                title="Topics, ranked by Polarization Index",
            ),
            use_container_width=True,
        )


# =====================================================================
# TAB 2 - ENTITY TRACKER
# =====================================================================
with tab_entity:
    st.subheader("How is each entity framed across sources?")

    col_sel, col_min = st.columns([3, 1])
    with col_sel:
        entity_options = top_entities_df.sort_values("mention_count", ascending=False)
        labels = [f"{r.entity_name}  ({r.mention_count} mentions, {r.entity_type})"
                  for r in entity_options.itertuples()]
        idx = st.selectbox("Pick an entity", options=range(len(labels)),
                           format_func=lambda i: labels[i], index=0)
        selected_entity = entity_options.iloc[idx]["entity_name"]
    with col_min:
        min_group = st.number_input("Min mentions per source", min_value=1, max_value=10, value=2,
                                    help="Sources with fewer than this many mentions of the entity are excluded.")

    pol = metrics.entity_polarization(entities_df, selected_entity, min_group_size=int(min_group))
    by_source = metrics.entity_adversarial_by_source(entities_df, selected_entity)
    by_source = by_source.loc[by_source["article_count"] >= int(min_group)]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total mentions", f"{pol['total_mentions']}")
    k2.metric("Sources covering", f"{pol['n_groups']}")
    k3.metric("Polarization Index", f"{pol['polarization']:.2f}" if pd.notna(pol["polarization"]) else "n/a")
    most_adv = pol["min_group"] if pol["min_group"] else "n/a"
    k4.metric("Most adversarial source", most_adv,
              f"{pol['min_value']:.2f}" if pd.notna(pol["min_value"]) else "")

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            viz.adversarial_bar(by_source, group_col="source_label",
                                color_map=viz.SOURCE_COLORS,
                                title=f"Adversarial Score per source: {selected_entity}"),
            use_container_width=True,
        )
    with c2:
        ent_mentions = data_load.entity_mentions(entities_df, selected_entity)
        ent_mentions = ent_mentions.loc[
            ent_mentions["source_label"].isin(by_source["source_label"])
        ]
        fp = metrics.register_fingerprint(ent_mentions, group_by="source_label")
        st.plotly_chart(
            viz.emotion_radar(fp, color_map=viz.SOURCE_COLORS,
                              title=f"Emotion register: {selected_entity}"),
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("#### Most adversarial headlines mentioning this entity")
    ent_articles = entities_df.loc[entities_df["entity_name"] == selected_entity, "article_id"].unique()
    headlines = articles_df.loc[articles_df["id"].isin(ent_articles)].copy()
    headlines = headlines.sort_values("sentiment_intensity", ascending=True).head(8)
    if headlines.empty:
        st.info("No headlines available.")
    else:
        headlines["date_display"] = (
            headlines["date"].dt.strftime("%Y-%m-%d").fillna("-")
        )
        st.dataframe(
            headlines[["date_display", "source_label", "headline",
                       "sentiment_intensity", "emotion_label_clean"]]
            .rename(columns={
                "date_display": "Date",
                "source_label": "Source",
                "headline": "Headline",
                "sentiment_intensity": "Adversarial",
                "emotion_label_clean": "Emotion",
            }),
            hide_index=True,
            use_container_width=True,
        )


# =====================================================================
# TAB 3 - TOPIC POLARIZATION
# =====================================================================
with tab_topic:
    st.subheader("How polarized is coverage of each topic across the political spectrum?")

    topic_counts = articles_df["topic_master"].value_counts()
    topic_options = topic_counts[topic_counts >= 10].index.tolist()

    if not topic_options:
        st.info("Not enough topic coverage in the dataset.")
    else:
        labels = [f"{t}  ({topic_counts[t]} articles)" for t in topic_options]
        idx = st.selectbox("Pick a topic", options=range(len(labels)),
                           format_func=lambda i: labels[i], index=0)
        selected_topic = topic_options[idx]

        pol = metrics.topic_polarization(articles_df, selected_topic, min_group_size=2)
        by_lean = metrics.topic_adversarial_by_lean(articles_df, selected_topic)
        by_lean = by_lean.loc[by_lean["article_count"] >= 2]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total articles", f"{pol['total_articles']}")
        k2.metric("Lean groups covering", f"{pol['n_groups']}")
        k3.metric("Polarization Index", f"{pol['polarization']:.2f}" if pd.notna(pol["polarization"]) else "n/a")
        k4.metric("Most adversarial lean", pol["min_group"] or "n/a",
                  f"{pol['min_value']:.2f}" if pd.notna(pol["min_value"]) else "")

        st.markdown("---")

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                viz.topic_lean_bar(by_lean, title=f"Adversarial Score per lean: {selected_topic}"),
                use_container_width=True,
            )
        with c2:
            topic_articles = data_load.topic_articles(articles_df, selected_topic)
            fp = metrics.register_fingerprint(topic_articles, group_by="source_lean")
            st.plotly_chart(
                viz.emotion_radar(fp, color_map=viz.LEAN_COLORS,
                                  title=f"Emotion register by lean: {selected_topic}"),
                use_container_width=True,
            )

        st.markdown("---")
        st.markdown("#### All topics, ranked by polarization")
        topic_ranking = metrics.rank_topics_by_polarization(articles_df, min_articles=10, min_leans=3)
        st.dataframe(topic_ranking.round(3), hide_index=True, use_container_width=True)


# =====================================================================
# TAB 4 - SOURCE PROFILE
# =====================================================================
with tab_source:
    st.subheader("Each outlet's emotional and adversarial fingerprint")

    sources = sorted(articles_df["source_label"].dropna().astype(str).unique())
    selected_source = st.selectbox("Pick a source", sources, index=0)

    source_articles = articles_df.loc[articles_df["source_label"].astype(str) == selected_source]
    source_entities = entities_df.loc[entities_df["source_label"].astype(str) == selected_source]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Articles", f"{len(source_articles):,}")
    k2.metric("Avg Adversarial Score", f"{source_articles['sentiment_intensity'].mean():.3f}")
    pct_neg = (source_articles["sentiment_label"] == "Negative").mean() * 100
    k3.metric("% negative articles", f"{pct_neg:.1f}%")
    if not source_articles.empty and source_articles["emotion_label_clean"].notna().any():
        top_emo = source_articles["emotion_label_clean"].mode().iloc[0]
        k4.metric("Dominant emotion", top_emo)
    else:
        k4.metric("Dominant emotion", "n/a")

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        fp_source = metrics.register_fingerprint(source_articles, group_by="source_label")
        fp_market = metrics.register_fingerprint(articles_df, group_by="source_label").mean().to_frame().T
        fp_market.index = ["Market Avg"]
        if not fp_source.empty:
            combined = pd.concat([fp_source, fp_market], axis=0).fillna(0)
            st.plotly_chart(
                viz.emotion_radar(combined,
                                  color_map={selected_source: viz.SOURCE_COLORS.get(selected_source, "#1f77b4"),
                                             "Market Avg": "#999999"},
                                  title=f"{selected_source} emotion register vs market average"),
                use_container_width=True,
            )

    with c2:
        st.markdown(f"**Entities {selected_source} frames most adversarially**")
        if source_entities.empty:
            st.info("No entity data for this source.")
        else:
            agg = (
                source_entities.groupby("entity_name", observed=True)
                .agg(adversarial=("sentiment_intensity", "mean"),
                     mentions=("sentiment_intensity", "count"))
                .reset_index()
            )
            agg = agg.loc[agg["mentions"] >= 3].sort_values("adversarial").head(10)
            st.dataframe(
                agg.rename(columns={"entity_name": "Entity",
                                    "adversarial": "Adversarial Score",
                                    "mentions": "Mentions"}).round(3),
                hide_index=True,
                use_container_width=True,
            )


# =====================================================================
# TAB 5 - METHODOLOGY
# =====================================================================
with tab_method:
    st.subheader("Methodology")
    st.markdown(
        """
**Scope and intent.** This is a portfolio exercise. The goal is to demonstrate
end-to-end execution (ingestion, multilingual NLP, custom metrics, analytical UI),
deliberate methodology, and honest engagement with data limitations. The dataset
covers roughly 16 days of dense coverage in May 2026; findings are illustrative
of the methodology, not definitive claims about Israeli media discourse. A
production version would aggregate months of data, validate the metrics against
human-labeled ground truth, and weight outlets by audience reach.

**Pipeline.** RSS feeds and HTML scrapers ingest articles from five Israeli outlets daily.
Each article is filtered for politics and security keywords, classified for sentiment
(DictaBERT for Hebrew, Cardiff RoBERTa for English), and enriched via Claude API for
emotion labels and named entity extraction with English normalization.

**Adversarial Coverage Score.** For each article we compute
`sentiment_intensity = pos_score − neg_score`, then average over a group of articles
(usually all coverage by one source of one entity). Range −1 (fully adversarial) to
+1 (fully sympathetic). Empirically the metric is left-skewed in Israeli political
coverage; the name reflects that observed distribution.

**Polarization Index.** For a given entity or topic, compute the mean Adversarial Score
for each source (or each political lean). The Polarization Index is the gap between
the highest and lowest mean. A higher value means the entity or topic is framed very
differently across camps. A diagnostic standard deviation is reported alongside.

**Emotion Fingerprint.** Each article is tagged with one of nine emotion labels.
Per source or per lean we report the normalized distribution. Visualized as a radar
chart so two profiles can be compared at a glance.

**Source-lean mapping.**
Walla → Left, Ynet → Center-Left, Globes → Center, Jerusalem Post → Center-Right,
Channel 14 → Right. The mapping reflects common positioning in Israeli media literature
and is open to refinement.

**Limitations.**
The current dataset covers roughly 16 days, concentrated in May 2026. Temporal trend
analysis is therefore limited. Sentiment models trained on general Hebrew text are
conservative on news prose and frequently return neutral, which is why the
Adversarial Score concentrates near zero and below. Entities mentioned by fewer than
three sources are filtered out of polarization rankings by default.
"""
    )

    st.markdown("---")
    st.caption("Author: Tal Jacob. github.com/taljacob28")
