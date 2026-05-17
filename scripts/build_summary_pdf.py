"""
Build a single-page executive PDF summary of the project.

Output: docs/Project_Summary.pdf
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "Project_Summary.pdf"
PIPELINE_IMG = ROOT / "docs" / "images" / "pipeline_overview.png"

NAVY = colors.HexColor("#1A3A5C")
GOLD = colors.HexColor("#C9A14A")
TEXT = colors.HexColor("#222222")
SUB = colors.HexColor("#555555")
LINE = colors.HexColor("#D5D5D5")


def make_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=18, textColor=NAVY,
            leading=20, spaceAfter=2,
        ),
        "tagline": ParagraphStyle(
            "tagline", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.5, textColor=SUB,
            leading=11, spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=10.5, textColor=NAVY,
            leading=12, spaceBefore=6, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.2, textColor=TEXT,
            leading=10.6, spaceAfter=2,
        ),
        "body_tight": ParagraphStyle(
            "body_tight", parent=base["Normal"],
            fontName="Helvetica", fontSize=7.8, textColor=TEXT,
            leading=9.8, spaceAfter=1,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.2, textColor=TEXT,
            leading=10.6, leftIndent=10, bulletIndent=0,
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontName="Helvetica", fontSize=7.5, textColor=SUB,
            leading=9, alignment=1,
        ),
    }


def make_pdf():
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="full",
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="single", frames=[frame])])

    S = make_styles()
    story = []

    # ----- Header -----
    story.append(Paragraph("Israeli Media Framing Tracker", S["title"]))
    story.append(Paragraph(
        "An end-to-end NLP pipeline that quantifies how five Israeli news outlets "
        "frame political entities and topics. Hebrew &amp; English sentiment + LLM "
        "enrichment + three custom analytical metrics + a 5-tab Streamlit dashboard. "
        "<i>Portfolio analytics project. Live data collection via Windows Task Scheduler. "
        "Findings illustrate the methodology; the data window is currently ~16 days.</i>",
        S["tagline"],
    ))

    # ----- Pipeline image -----
    if PIPELINE_IMG.exists():
        img = Image(str(PIPELINE_IMG), width=18.6 * cm, height=5.4 * cm)
        story.append(img)
        story.append(Spacer(1, 3))

    # ----- Two-column body using a Table for layout -----
    left_col = []
    left_col.append(Paragraph("The business question", S["h2"]))
    left_col.append(Paragraph(
        "When five Israeli outlets cover the same entity or topic, how far apart are "
        "their frames, and which camp drives the gap? Four sub-questions: "
        "<b>(1)</b> Where is the line? <b>(2)</b> Who is the most polarizing figure? "
        "<b>(3)</b> Does each outlet have a distinct emotional fingerprint? "
        "<b>(4)</b> Does political lean explain the variance?",
        S["body"],
    ))

    left_col.append(Paragraph("Key findings (current snapshot)", S["h2"]))
    for b in [
        "<b>Polarization is structured, not noise.</b> Mean entity-level Polarization Index = 0.41 "
        "across 13 tracked entities (max 0.75, min 0.05).",
        "<b>Yair Lapid is the most polarizing figure.</b> Walla covers him at -0.667 (hostile), "
        "JPost at +0.085 (sympathetic). Netanyahu is less polarizing (0.27) because every outlet "
        "covers him adversarially.",
        "<b>Each outlet has a stable emotional fingerprint.</b> Ynet 42% anger; Channel 14 14% pride "
        "+ 9% joy; Globes 24% anticipation + 22% fear; Walla 36% anger + 24% fear.",
        "<b>Political lean only partly explains framing.</b> Judicial &amp; Legal (0.38) and Coalition "
        "&amp; Government (0.40) follow the L/R axis; Security Operations and International Diplomacy "
        "do not. A second axis (domestic vs international focus) is at work.",
    ]:
        left_col.append(Paragraph("• " + b, S["bullet"]))

    left_col.append(Paragraph("Bottom line for a stakeholder", S["h2"]))
    left_col.append(Paragraph(
        "For PR &amp; corporate comms, Globes' uniquely different topical and emotional profile makes "
        "it the entry point for financial or commercial pitches. For political consulting, the "
        "Polarization Index ranks public figures by their cross-spectrum exposure, a leading "
        "indicator of reputational risk.",
        S["body"],
    ))

    right_col = []
    right_col.append(Paragraph("Skills demonstrated", S["h2"]))
    for b in [
        "<b>Multilingual NLP pipeline</b> (DictaBERT for Hebrew, Cardiff RoBERTa for English) on 750 articles.",
        "<b>LLM enrichment</b> via Anthropic Claude API for emotion, entity, and topic labels.",
        "<b>Three custom analytical metrics</b> designed from first principles "
        "(Adversarial Score, Polarization Index, Emotion Fingerprint).",
        "<b>5-tab Streamlit dashboard</b> with 10 interactive Plotly visualizations.",
        "<b>SQL data warehouse</b> in SQLite with deduplication and indexed lookups.",
        "<b>Production patterns</b>: daily ingestion via Task Scheduler, JSON-LD date extraction, "
        "backfill scripts, quality flags, structured logging.",
        "<b>Analyst judgment</b>: honest scoping, explicit limitations, methodology tab in-app for transparency.",
    ]:
        right_col.append(Paragraph("• " + b, S["bullet"]))

    right_col.append(Paragraph("Methodology, at a glance", S["h2"]))
    right_col.append(Paragraph(
        "<b>Adversarial Score</b> = mean(pos_score − neg_score) per group, range -1 to +1. "
        "<b>Polarization Index</b> = max − min of group means. "
        "<b>Emotion Fingerprint</b> = normalized distribution across four registers: "
        "Hostile, Anxious, Hopeful, Neutral.",
        S["body_tight"],
    ))

    right_col.append(Paragraph("Tech stack", S["h2"]))
    right_col.append(Paragraph(
        "Python 3.13 · transformers / DictaBERT / Cardiff RoBERTa · Anthropic Claude · "
        "feedparser · BeautifulSoup · SQLite via SQLAlchemy · pandas / numpy · "
        "Streamlit · Plotly · Windows Task Scheduler.",
        S["body_tight"],
    ))

    body_table = Table(
        [[left_col, right_col]],
        colWidths=[9.5 * cm, 9.1 * cm],
    )
    body_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 8),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
    ]))
    story.append(body_table)
    story.append(Spacer(1, 6))

    # ----- Footer line + contact -----
    footer_table = Table(
        [[Paragraph(
            "Tal Jacob · Data Analyst · "
            "<font color='#1A3A5C'><b>github.com/taljacob28/hebrew-news-sentiment</b></font> · "
            "taljacob28@gmail.com",
            S["footer"]
        )]],
        colWidths=[18.6 * cm],
    )
    footer_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(footer_table)

    doc.build(story)
    print(f"Wrote: {OUTPUT}")


if __name__ == "__main__":
    make_pdf()
