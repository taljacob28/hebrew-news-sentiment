"""
Build an executive PDF summary of the Israeli Media Framing Tracker project.

Design choices:
- Justified body text (alignment=TA_JUSTIFY) on every paragraph.
- Generous line spacing (~1.7x leading) for readability.
- Two-page A4 layout: page 1 = context + findings, page 2 = methodology + skills.
- Navy/gold color identity consistent with the dashboard and CV.

Output: docs/Project_Summary.pdf
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "Project_Summary.pdf"
PIPELINE_IMG = ROOT / "docs" / "images" / "pipeline_overview.png"

# Color identity
NAVY = colors.HexColor("#1A3A5C")
GOLD = colors.HexColor("#C9A14A")
TEXT = colors.HexColor("#1F1F1F")
SUB = colors.HexColor("#555555")
RULE = colors.HexColor("#D5D5D5")


def make_styles():
    base = getSampleStyleSheet()
    # Typography scale. Body is 10pt with 17pt leading (~1.7x line height, double-spaced look).
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=20, textColor=NAVY,
            leading=24, spaceAfter=4, alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=9.5, textColor=SUB,
            leading=14, spaceAfter=8, alignment=TA_JUSTIFY,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=12, textColor=NAVY,
            leading=15, spaceBefore=8, spaceAfter=4, alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5, textColor=TEXT,
            leading=15, spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5, textColor=TEXT,
            leading=15, leftIndent=14, bulletIndent=2,
            spaceAfter=4, alignment=TA_JUSTIFY,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=8.5, textColor=SUB,
            leading=12, spaceAfter=8, alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=SUB,
            leading=11, alignment=TA_CENTER,
        ),
    }


def horizontal_rule(width_cm=17.6, color=RULE, thickness=0.5, space=6):
    """A thin horizontal divider line as a Table-based rule."""
    t = Table([[""]], colWidths=[width_cm * cm], rowHeights=[0.01])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), thickness, color),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), space),
    ]))
    return t


def header_band(S):
    """Title block: project name + tagline."""
    return [
        Paragraph("Israeli Media Framing Tracker", S["title"]),
        Paragraph(
            "An end-to-end NLP analytics pipeline that quantifies how five Israeli news outlets "
            "frame the same political entities and topics. The system pairs Hebrew and English sentiment "
            "models with LLM-based emotion and entity enrichment, then surfaces the results through three "
            "custom analytical metrics and a five-tab Streamlit dashboard. "
            "<i>Portfolio analytics project. Live daily collection via Windows Task Scheduler. The current "
            "snapshot covers 750 articles over 16 days; findings illustrate the methodology rather than "
            "make definitive claims about Israeli media.</i>",
            S["subtitle"],
        ),
    ]


def pipeline_image(S):
    """Pipeline diagram with centered caption."""
    elements = []
    if PIPELINE_IMG.exists():
        img = Image(str(PIPELINE_IMG), width=17.5 * cm, height=5.1 * cm)
        img.hAlign = "CENTER"
        elements.append(img)
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            "Figure 1. End-to-end pipeline from RSS and HTML ingestion through multilingual NLP, "
            "Claude API enrichment, and the final Streamlit dashboard.",
            S["caption"],
        ))
    return elements


def business_question_block(S):
    """The single business question + four sub-questions."""
    return [
        Paragraph("The Business Question", S["h2"]),
        Paragraph(
            "Israeli media is polarized, but the diagnosis is usually anecdotal. This project replaces "
            "anecdote with measurement and answers one operational question: "
            "<b>When five Israeli outlets cover the same entity or topic, how far apart are their frames, "
            "and which camp drives the gap?</b>",
            S["body"],
        ),
        Paragraph(
            "The question splits into four sub-questions an analyst at a PR firm, a corporate "
            "communications team, or a political consultancy would need to answer: "
            "<b>(1)</b> Where is the line? "
            "<b>(2)</b> Who is the most polarizing public figure? "
            "<b>(3)</b> Does each outlet carry a stable emotional fingerprint across topics? "
            "<b>(4)</b> Does political lean explain the variance, or is a second axis at work?",
            S["body"],
        ),
    ]


def findings_block(S):
    """The four headline findings as bullets."""
    bullets = [
        "<b>Cross-outlet framing gaps are large and structured.</b> Mean Polarization Index across "
        "13 tracked entities is 0.41 (max 0.75 for Yair Lapid, min 0.05 for Lebanon). The gap correlates "
        "with source identity in stable ways, not random noise.",

        "<b>Yair Lapid is the most polarizing entity, not Netanyahu.</b> Walla covers Lapid at "
        "-0.667 (hostile), Jerusalem Post at +0.085 (sympathetic). Netanyahu ranks only eighth at 0.27, "
        "because every outlet covers him adversarially. The disagreement is over which figures deserve "
        "the criticism, not whether to be critical.",

        "<b>Each outlet has a stable emotional fingerprint that cuts across topics.</b> Ynet leads on "
        "anger (42%); Walla on anger and fear (36% / 24%); Channel 14 on a distinctive Hopeful register "
        "(14% pride, 9% joy); Globes on anticipation and fear (24% / 22%); Jerusalem Post on anger and "
        "anticipation (32% / 24%). The signature persists when topic mix is controlled for.",

        "<b>Political lean only partly explains framing.</b> The left-right axis predicts framing on "
        "Judicial &amp; Legal (polarization 0.38) and Coalition &amp; Government (0.40), but not on "
        "Security Operations or International Diplomacy. A second axis is at work: domestic versus "
        "international focus.",
    ]
    elements = [Paragraph("Key Findings", S["h2"])]
    for b in bullets:
        elements.append(Paragraph("&bull;&nbsp; " + b, S["bullet"]))
    return elements


def bottom_line_block(S):
    """Stakeholder takeaways."""
    return [
        Paragraph("Bottom Line for a Stakeholder", S["h2"]),
        Paragraph(
            "<b>For PR and corporate communications.</b> Globes is structurally different from the other "
            "four outlets on both emotional register and topic mix, making it the right entry point for "
            "any financial or commercial pitch. Ynet's adversarial baseline requires a different playbook.",
            S["body"],
        ),
        Paragraph(
            "<b>For political consulting.</b> The Polarization Index ranks public figures by how divided "
            "their coverage is, a leading indicator of reputational exposure. A figure with a high score "
            "is reading two different narratives about themselves depending on the outlet. The Entity "
            "Tracker tab quantifies that gap and shows which outlets drive each side.",
            S["body"],
        ),
    ]


def methodology_block(S):
    """The three custom metrics, defined."""
    return [
        Paragraph("Methodology", S["h2"]),
        Paragraph(
            "<b>Adversarial Coverage Score.</b> For each article, sentiment_intensity equals pos_score "
            "minus neg_score, then averaged over a group (usually all coverage by one source of one "
            "entity). Range -1 (fully adversarial) to +1 (fully sympathetic). Empirically left-skewed in "
            "Israeli political coverage; the metric name reflects that observed distribution.",
            S["body"],
        ),
        Paragraph(
            "<b>Polarization Index.</b> For an entity or topic, compute the mean Adversarial Score per "
            "source (or per political lean). The Polarization Index is the gap between the highest and "
            "lowest mean, with a standard-deviation diagnostic reported alongside. Sources with fewer "
            "than two articles on the entity are excluded to avoid inflating the index on thin coverage.",
            S["body"],
        ),
        Paragraph(
            "<b>Emotion Fingerprint.</b> Each article carries one of nine Claude-assigned emotion labels. "
            "Labels collapse into four registers for the radar charts: Hostile (anger, disgust, "
            "disappointment), Anxious (fear, sadness, anxiety, tension, concern), Hopeful (anticipation, "
            "joy, pride, relief), Neutral (neutral, surprise).",
            S["body"],
        ),
    ]


def skills_block(S):
    """Skills demonstrated, suitable for a hiring manager scan."""
    bullets = [
        "<b>Multilingual NLP pipeline.</b> DictaBERT for Hebrew (648 articles), Cardiff RoBERTa for "
        "English (102 articles), with separate body and headline passes to capture clickbait amplification.",

        "<b>LLM enrichment.</b> Anthropic Claude (Haiku 4.5) for nine-label emotion classification, "
        "named entity recognition with Hebrew-to-English normalization (1,002 unique entities), and "
        "12-category topic labeling.",

        "<b>Three custom metrics designed from first principles.</b> Adversarial Coverage Score, "
        "Polarization Index, Emotion Fingerprint. Defined, documented, and validated against thin-data "
        "edge cases.",

        "<b>Five-tab Streamlit dashboard</b> with ten interactive Plotly visualizations: KPI cards, "
        "emotion heatmaps, topic specialization heatmaps, adversarial bar charts, four-axis radars, "
        "polarization rankings, and most-adversarial-headlines tables.",

        "<b>Production engineering.</b> JSON-LD date extraction fixed a 35% missing-timestamp bug on "
        "Walla and Channel 14; a backfill script then recovered 100% of those dates. Daily ingestion "
        "via Windows Task Scheduler, SQLite deduplication, structured logging.",

        "<b>Analyst judgment.</b> Honest scoping, explicit limitations, in-app methodology tab. Findings "
        "framed as illustrations of the methodology rather than overclaimed conclusions on a thin window.",
    ]
    elements = [Paragraph("Skills Demonstrated", S["h2"])]
    for b in bullets:
        elements.append(Paragraph("&bull;&nbsp; " + b, S["bullet"]))
    return elements


def tech_stack_block(S):
    """Compact tech stack paragraph."""
    return [
        Paragraph("Tech Stack", S["h2"]),
        Paragraph(
            "Python 3.13. Hugging Face transformers with DictaBERT and Cardiff RoBERTa. Anthropic Claude "
            "API. feedparser, requests, BeautifulSoup, lxml, and JSON-LD parsing for ingestion. SQLite "
            "via SQLAlchemy, with CSV exports for portability. Streamlit and Plotly for the interactive "
            "dashboard. pandas and numpy for the analytics layer. Windows Task Scheduler for daily runs.",
            S["body"],
        ),
    ]


def footer_block(S):
    """Final contact footer with a gold rule above it."""
    footer = Table(
        [[Paragraph(
            "Tal Jacob &middot; Data Analyst &middot; "
            "<font color='#1A3A5C'><b>github.com/taljacob28/hebrew-news-sentiment</b></font> &middot; "
            "taljacob28@gmail.com",
            S["footer"]
        )]],
        colWidths=[17.6 * cm],
    )
    footer.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 6), footer]


def make_pdf():
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=1.7 * cm, rightMargin=1.7 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="full",
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="single", frames=[frame])])

    S = make_styles()
    story = []

    # ----- PAGE 1: context + business question + findings -----
    story.extend(header_band(S))
    story.extend(pipeline_image(S))
    story.append(horizontal_rule())
    story.extend(business_question_block(S))
    story.extend(findings_block(S))

    # ----- PAGE 2: bottom line + methodology + skills + tech -----
    story.append(PageBreak())
    story.extend(bottom_line_block(S))
    story.extend(methodology_block(S))
    story.extend(skills_block(S))
    story.extend(tech_stack_block(S))
    story.extend(footer_block(S))

    doc.build(story)
    print(f"Wrote: {OUTPUT}")


if __name__ == "__main__":
    make_pdf()
