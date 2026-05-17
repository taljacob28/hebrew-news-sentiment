"""
Reusable Plotly chart builders for the Israeli Media Framing Tracker.

Every function returns a plotly.graph_objects.Figure ready to drop into Streamlit.
No I/O, no Streamlit dependencies, no analytics. Pure rendering on top of
DataFrames produced by `src.metrics`.

Color conventions:
- Sources keep stable colors across all charts for visual continuity.
- Political leans use a perceptual blue (Left) -> gray (Center) -> red (Right) ramp.
- Adversarial Score uses a single divergent scale (red negative, blue positive)
  pinned to zero so visual weight matches the metric's meaning.
"""

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

SOURCE_COLORS = {
    "Walla": "#1f77b4",
    "Ynet": "#17becf",
    "Globes": "#bcbd22",
    "Jerusalem Post": "#8c564b",
    "Channel 14": "#d62728",
}

LEAN_COLORS = {
    "Left": "#1f4e79",
    "Center-Left": "#5b9bd5",
    "Center": "#a6a6a6",
    "Center-Right": "#ed7d31",
    "Right": "#c00000",
}

EMOTION_COLORS = {
    "Anger": "#c0392b",
    "Fear": "#7d3c98",
    "Sadness": "#2874a6",
    "Disgust": "#196f3d",
    "Anticipation": "#d68910",
    "Surprise": "#af7ac5",
    "Joy": "#f1c40f",
    "Pride": "#e67e22",
    "Neutral": "#95a5a6",
}


def adversarial_bar(
    df: pd.DataFrame,
    group_col: str,
    color_map: Optional[dict] = None,
    title: str = "",
) -> go.Figure:
    """
    Horizontal bar chart of Adversarial Coverage Score per group, sorted ascending
    so the most adversarial group sits at the bottom. Bars are overlaid with
    circular markers so even zero-value groups stay visible.
    """
    if df.empty:
        return _empty_fig("No data")

    plot_df = df.sort_values("adversarial_score", ascending=True).copy()
    plot_df["label"] = plot_df["adversarial_score"].apply(lambda v: f"{v:+.2f}")
    plot_df["y_label"] = plot_df.apply(
        lambda r: f"{r[group_col]}  (n={int(r['article_count'])})", axis=1
    )

    y_labels = plot_df["y_label"].tolist()
    x_values = plot_df["adversarial_score"].tolist()
    colors = (
        [color_map.get(g, "#777777") for g in plot_df[group_col].astype(str).tolist()]
        if color_map is not None
        else ["#34495e"] * len(y_labels)
    )

    fig = go.Figure()

    # Underlying bars
    fig.add_trace(
        go.Bar(
            x=x_values,
            y=y_labels,
            orientation="h",
            marker_color=colors,
            marker_line=dict(color="white", width=0),
            text=plot_df["label"],
            textposition="outside",
            textfont=dict(size=12),
            showlegend=False,
            customdata=plot_df[["article_count", group_col]].values,
            hovertemplate="%{customdata[1]}<br>Adversarial Score: %{x:.3f}<br>Mentions: %{customdata[0]}<extra></extra>",
        )
    )

    # Overlay markers so a zero-value group still shows a visible dot
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_labels,
            mode="markers",
            marker=dict(color=colors, size=14, line=dict(color="white", width=1.5)),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Adversarial Coverage Score (-1 adversarial, +1 sympathetic)",
        yaxis_title="",
        xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor="#666", range=[-1, 1]),
        yaxis=dict(categoryorder="array", categoryarray=y_labels),
        height=380,
        margin=dict(l=10, r=60, t=50, b=40),
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig


def emotion_radar(
    fingerprint: pd.DataFrame,
    color_map: Optional[dict] = None,
    title: str = "",
    min_pct: float = 0.03,
) -> go.Figure:
    """
    Radar chart of emotion distribution per group, with three readability fixes:
    rare emotions (under min_pct in every group) are dropped; the radial axis
    auto-fits to the actual data range with small padding; the legend is placed
    below the chart so the polar plot keeps the full width.
    `fingerprint` is the output of metrics.emotion_fingerprint().
    """
    if fingerprint.empty:
        return _empty_fig("No data")

    keep = fingerprint.columns[(fingerprint >= min_pct).any(axis=0)]
    if len(keep) < 3:
        keep = fingerprint.columns
    fp = fingerprint[keep]

    # If the caller passed a register fingerprint (Hostile / Anxious / Hopeful / Neutral),
    # respect that exact order. Otherwise apply the canonical 9-emotion order.
    register_set = {"Hostile", "Anxious", "Hopeful", "Neutral"}
    if any(c in register_set for c in fp.columns):
        register_order = ["Hostile", "Anxious", "Hopeful", "Neutral"]
        ordered = [r for r in register_order if r in fp.columns]
        others = [c for c in fp.columns if c not in register_order]
        fp = fp[ordered + others]
    else:
        # Canonical emotion order so radar axes stay consistent across selections.
        # Matching is case-insensitive because raw labels arrive in mixed case.
        canonical = ["anger", "fear", "sadness", "disgust",
                     "anticipation", "surprise", "joy", "pride", "neutral"]
        cols_lower = {c.lower(): c for c in fp.columns}
        ordered = [cols_lower[e] for e in canonical if e in cols_lower]
        others = [c for c in fp.columns if c.lower() not in canonical]
        fp = fp[ordered + others]

    emotions = list(fp.columns)
    max_val = float(fp.values.max())
    radius_max = max(0.35, max_val * 1.15)

    fig = go.Figure()
    for group in fp.index:
        values = fp.loc[group].tolist()
        color = color_map.get(str(group), "#777777") if color_map else None
        fig.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=emotions + [emotions[0]],
                fill="toself",
                name=str(group),
                line=dict(color=color, width=2) if color else dict(width=2),
                opacity=0.55,
                hovertemplate=f"{group}<br>%{{theta}}: %{{r:.0%}}<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, radius_max],
                tickformat=".0%",
                tickfont=dict(size=10),
            ),
            angularaxis=dict(rotation=90, direction="clockwise", tickfont=dict(size=11)),
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.05,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
        showlegend=True,
        height=520,
        margin=dict(l=40, r=40, t=60, b=80),
    )
    return fig


def polarization_ranking(df: pd.DataFrame, label_col: str, top_n: int = 15, title: str = "") -> go.Figure:
    """Horizontal bar chart of the most polarizing entities or topics."""
    if df.empty:
        return _empty_fig("No data")

    plot_df = df.head(top_n).sort_values("polarization", ascending=True).copy()
    fig = go.Figure(
        go.Bar(
            x=plot_df["polarization"],
            y=plot_df[label_col].astype(str),
            orientation="h",
            marker_color="#34495e",
            text=plot_df["polarization"].round(2),
            textposition="outside",
            hovertemplate="%{y}<br>Polarization Index: %{x:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Polarization Index (max - min Adversarial Score across groups)",
        yaxis_title="",
        height=max(360, 28 * len(plot_df)),
        margin=dict(l=10, r=40, t=50, b=40),
        plot_bgcolor="white",
    )
    return fig


def volume_timeseries(volume_df: pd.DataFrame, title: str = "") -> go.Figure:
    """Stacked area chart of article volume per source over time."""
    if volume_df.empty:
        return _empty_fig("No date-stamped articles")

    fig = px.area(
        volume_df,
        x="date",
        y="article_count",
        color="source_label",
        color_discrete_map=SOURCE_COLORS,
        title=title,
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Articles",
        legend_title="Source",
        height=380,
        plot_bgcolor="white",
        margin=dict(l=10, r=20, t=50, b=40),
    )
    return fig


def source_emotion_heatmap(fingerprint: pd.DataFrame, title: str = "") -> go.Figure:
    """Heatmap of source x emotion percentages."""
    if fingerprint.empty:
        return _empty_fig("No data")

    fig = go.Figure(
        go.Heatmap(
            z=fingerprint.values,
            x=fingerprint.columns.astype(str),
            y=fingerprint.index.astype(str),
            colorscale="Reds",
            zmin=0,
            zmax=max(0.6, fingerprint.values.max()),
            colorbar=dict(title="% of articles"),
            hovertemplate="%{y} | %{x}<br>%{z:.0%}<extra></extra>",
            text=[[f"{v:.0%}" for v in row] for row in fingerprint.values],
            texttemplate="%{text}",
        )
    )
    fig.update_layout(
        title=title,
        height=380,
        margin=dict(l=10, r=20, t=50, b=40),
    )
    return fig


def topic_lean_bar(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Bar chart of Adversarial Score per political lean for a single topic."""
    if df.empty:
        return _empty_fig("No data")

    plot_df = df.sort_values("source_lean").copy()
    fig = go.Figure(
        go.Bar(
            x=plot_df["source_lean"].astype(str),
            y=plot_df["adversarial_score"],
            marker_color=[LEAN_COLORS.get(str(l), "#777") for l in plot_df["source_lean"]],
            text=plot_df["adversarial_score"].round(3),
            textposition="outside",
            customdata=plot_df[["article_count"]].values,
            hovertemplate="%{x}<br>Adversarial Score: %{y:.3f}<br>Articles: %{customdata[0]}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Political Lean",
        yaxis_title="Adversarial Coverage Score",
        yaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor="#444", range=[-1, 1]),
        height=380,
        plot_bgcolor="white",
        margin=dict(l=10, r=20, t=50, b=40),
    )
    return fig


def articles_per_source_bar(articles_df, title: str = "") -> go.Figure:
    """Horizontal bar chart of article count per source."""
    if articles_df.empty:
        return _empty_fig("No data")

    counts = articles_df["source_label"].value_counts().sort_values(ascending=True)
    colors = [SOURCE_COLORS.get(str(s), "#777777") for s in counts.index]

    fig = go.Figure(
        go.Bar(
            x=counts.values,
            y=counts.index.astype(str),
            orientation="h",
            marker_color=colors,
            text=counts.values,
            textposition="outside",
            hovertemplate="%{y}<br>Articles: %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Articles",
        yaxis_title="",
        height=300,
        margin=dict(l=10, r=40, t=50, b=40),
        plot_bgcolor="white",
    )
    return fig


def source_topic_heatmap(articles_df, top_n_topics: int = 10, title: str = "") -> go.Figure:
    """
    Heatmap of source vs topic, normalized so each row shows what share of that
    source's coverage goes to each topic. Reveals topical specialization per outlet.
    """
    import pandas as pd

    if articles_df.empty:
        return _empty_fig("No data")

    top_topics = articles_df["topic_master"].value_counts().head(top_n_topics).index.tolist()
    sub = articles_df.loc[articles_df["topic_master"].isin(top_topics)]
    if sub.empty:
        return _empty_fig("No data")

    ct = pd.crosstab(sub["source_label"], sub["topic_master"], normalize="index")
    ct = ct.reindex(columns=top_topics, fill_value=0)

    fig = go.Figure(
        go.Heatmap(
            z=ct.values,
            x=ct.columns.astype(str),
            y=ct.index.astype(str),
            colorscale="Blues",
            zmin=0,
            zmax=max(0.5, float(ct.values.max())),
            colorbar=dict(title="% of source's coverage"),
            hovertemplate="%{y} | %{x}<br>%{z:.0%}<extra></extra>",
            text=[[f"{v:.0%}" for v in row] for row in ct.values],
            texttemplate="%{text}",
        )
    )
    fig.update_layout(
        title=title,
        height=380,
        xaxis=dict(tickangle=-25),
        margin=dict(l=10, r=20, t=50, b=80),
    )
    return fig


def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#888"),
    )
    fig.update_layout(height=300, plot_bgcolor="white", xaxis_visible=False, yaxis_visible=False)
    return fig
