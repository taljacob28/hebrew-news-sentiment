# Israeli Media Framing Tracker

> End-to-end NLP pipeline that ingests politics and security coverage from five Israeli outlets, classifies it with Hebrew and English sentiment models, enriches it with emotion and entity labels via Claude, and surfaces three custom analytical metrics through a five-tab Streamlit dashboard.

![Python](https://img.shields.io/badge/Python-3.13-1A3A5C?style=flat-square)
![NLP](https://img.shields.io/badge/NLP-DictaBERT%20%2B%20RoBERTa-C9A14A?style=flat-square)
![LLM](https://img.shields.io/badge/LLM-Claude%20API-C9A14A?style=flat-square)
![Storage](https://img.shields.io/badge/Storage-SQLite-1A3A5C?style=flat-square)
![Dashboard](https://img.shields.io/badge/Dashboard-Streamlit%20%2B%20Plotly-1A3A5C?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-1A3A5C?style=flat-square)

![Pipeline Overview](docs/images/pipeline_overview.png)

> ⚠ **Live portfolio project.** A Windows Task Scheduler job ingests new articles daily. The numbers below reflect the snapshot at the time of writing (~750 articles over a 16-day window). Findings are illustrative of the methodology, not definitive claims about Israeli media.

## The Business Question

Israeli media is famously polarized, but the diagnosis is almost always anecdotal. This project answers four questions that an analyst at a PR firm, a corporate communications team, a political consultancy, or a media research desk would actually need to know:

1. **Where is the line?** When five Israeli outlets cover the same entity or topic, how far apart are their frames, and which camp drives the gap?
2. **Who is the most polarizing figure?** Which political entities surface the widest cross-outlet gap, and which outlet is the most adversarial against each one?
3. **Does each outlet have a distinct fingerprint?** Beyond topic mix, do the five outlets carry measurably different emotional registers, and are they stable enough to characterize the outlet?
4. **Does political lean explain the variance?** When you collapse the five outlets into five lean categories, does the spread on a topic align with the left-right axis?

The pipeline, the three custom metrics, and the five-tab dashboard all answer back to these four questions.

## At a Glance

- **Engineered a multilingual NLP pipeline** moving 750 politics and security articles from five Israeli outlets (Walla, Ynet, Globes, Jerusalem Post, Channel 14) into a deduplicated SQLite warehouse with daily ingestion via Windows Task Scheduler.
- **Designed three custom analytical metrics from first principles.** Adversarial Coverage Score (mean sentiment intensity per group, range -1 to +1), Polarization Index (max minus min Adversarial Score across groups), and Emotion Fingerprint (normalized distribution across four registers: Hostile, Anxious, Hopeful, Neutral).
- **Built a five-tab Streamlit dashboard** with ten interactive Plotly visualizations: KPI cards, articles-per-source bars, source-by-emotion heatmap, source-by-topic heatmap, adversarial bar charts, four-axis radar charts, polarization rankings, and a most-adversarial-headlines table per entity.
- **Composed a two-pass sentiment classification layer** using DictaBERT for Hebrew (465 articles) and Cardiff RoBERTa for English (102 articles), with separate body and headline passes to capture clickbait amplification.
- **Integrated the Anthropic Claude API** for emotion classification (nine fine-grained labels), named entity recognition with English normalization (1,002 unique entities), and topic categorization across 12 macro categories.
- **Diagnosed and fixed a date-extraction bug** in the Walla and Channel 14 scrapers by reading JSON-LD structured data instead of standard meta tags, then wrote a backfill script that recovered timestamps for 100% of previously dateless articles.
- **Wrote an honest methodology and limitations layer** that acknowledges a thin data window and conservative Hebrew sentiment models, modeling intellectual maturity rather than overclaiming.

A one-page PDF summary lives at [docs/Project_Summary.pdf](docs/Project_Summary.pdf).

## The Dashboard

### Overview — Coverage at a glance

![Overview](docs/images/01_overview.png)

The landing tab anchors four story-bearing KPIs at the top: total articles, share of adversarial articles, Net Adversarial Score (mean intensity across the corpus), and the most polarizing entity in the dataset. Below them, a source-by-emotion heatmap and a source-by-topic specialization heatmap reveal that each outlet has a distinct editorial focus. Globes dedicates 57% of its coverage to Economic Affairs, Jerusalem Post 36% to International Diplomacy, Walla 18% to Security Operations. The bottom row ranks every tracked entity and topic by polarization.

### Entity Tracker — Per-entity adversarial profile

![Entity Tracker — Netanyahu](docs/images/02_entity_netanyahu.png)

Select any of the 29 tracked entities (10+ mentions, three or more sources) and see how each outlet frames it. For Benjamin Netanyahu, the most aggressive source is Ynet at -0.246 Adversarial Score, Globes is neutral at 0.000, and the gap between them is the entity's Polarization Index. The four-axis emotion register radar (Hostile / Anxious / Hopeful / Neutral) shows the same finding visually: Walla and Ynet cluster on Hostile, Globes is uniquely on Anxious, Channel 14 leans Hopeful. The bottom table surfaces the most adversarial headlines mentioning the entity, with source, date, intensity, and detected emotion.

### Topic Polarization — Coverage across the spectrum

![Topic Polarization — Judicial & Legal](docs/images/03_topic_judicial.png)

Pick a topic and the tool aggregates the five outlets into five political lean categories (Left, Center-Left, Center, Center-Right, Right), shows the Adversarial Score per lean as a colored bar chart, and overlays the emotion register radar by lean. For Judicial & Legal coverage, Center-Right is the most adversarial (-0.375), Center is the most neutral, and the polarization gap is 0.38. The table at the bottom ranks every topic by polarization. Knesset & Legislation leads at 0.5, Economic Affairs trails at 0.01.

### Source Profile — Each outlet's fingerprint

![Source Profile — Ynet](docs/images/04_source_ynet.png)

Pick an outlet to see its emotional register against the market average and to enumerate the entities it frames most adversarially. Ynet's profile: 194 articles, -0.201 average Adversarial Score, 23% negative, anger dominant. The radar overlay shows Ynet's Hostile register significantly above the market average. The right-side table reveals that Ynet's harshest framing targets Israeli Police (-0.79), Israeli Government (-0.67), and the Israeli Basketball League (-0.67).

### Methodology — Transparent metric definitions

![Methodology](docs/images/05_methodology.png)

Every metric is defined explicitly in-app, the source-to-lean mapping is documented, and the limitations are spelled out. This is the tab a hiring manager opens to verify that the analyst understands their own tool.

## Key Findings

> All findings below are computed on the current snapshot of 750 articles spanning 16 days in early 2026. They illustrate what the methodology surfaces; they are not generalizable claims about Israeli media as a whole.

**Q1. Cross-outlet framing gaps are large and structured.** The mean Polarization Index across 13 tracked entities is 0.41, with a maximum of 0.75 (Yair Lapid) and a minimum of 0.05 (Lebanon). The gap is not random noise; it correlates with source identity in stable, repeatable ways across entities.

**Q2. Yair Lapid is the most polarizing entity, followed by the Likud and Isaac Herzog.** Lapid's Polarization Index of 0.75 is driven by a sharp split: Walla covers him at -0.667 (very hostile), Jerusalem Post at +0.085 (sympathetic). The Likud (0.59) and Herzog (0.55) show similar cross-spectrum splits. Netanyahu, by contrast, is only the eighth most polarizing entity at 0.27, because every outlet covers him adversarially. The disagreement is not over whether to be critical, it is over which figures deserve the criticism.

**Q3. Each outlet has a stable emotional fingerprint that cuts across topics.** Ynet leads on anger (42%), Walla on a mix of anger and fear (36% / 24%), Channel 14 on a distinctive Hopeful register (14% pride, 9% joy), Globes on anticipation and fear (24% / 22%), Jerusalem Post on anger and anticipation (32% / 24%). The Source Profile tab shows these registers compared against the market average, and they persist even when the topic mix is controlled for.

**Q4. The left-right axis explains only part of the variance.** When the five outlets collapse into five lean categories, the political spectrum predicts framing on some topics (Judicial & Legal, Coalition & Government) but not others. Security Operations and International Diplomacy show smaller lean-based gaps. The data suggests a second axis at work: domestic-vs-international focus. Globes and JPost cover international stories adversarially (foreign actors, financial markets), while Walla and Ynet cover domestic politics adversarially.

## The Bottom Line

Three takeaways an analyst can hand to a stakeholder today.

**For corporate communications and PR.** The "which outlet is most receptive" question has a quantitative answer per topic. Globes is dramatically different from the other four on emotional register and topic mix, which makes it the right entry point for any financial or commercial story. Conversely, Ynet's structural adversarial baseline means pitching it requires a different playbook.

**For political consulting.** The Polarization Index ranks public figures by how divided their coverage is, which is a leading indicator of how exposed they are. A figure with high polarization is reading two different narratives about themselves depending on the outlet. The Entity Tracker tab quantifies that gap and shows which outlets drive each side.

**For methodology critics.** The numbers above sit on top of an honest layer of caveats. Hebrew sentiment models are conservative on news prose, the data window is thin, and the source-lean mapping is an editorial judgment open to debate. Productionizing this would mean months of data, a validation set with human-labeled ground truth, and outlet weighting by audience reach. The point of the current build is to prove the methodology and the analyst's command of it.

## Methodology

**Adversarial Coverage Score.** For each article, `sentiment_intensity = pos_score - neg_score`, averaged over a group (usually all coverage by one source of one entity). Range -1 (fully adversarial) to +1 (fully sympathetic). Empirically left-skewed in Israeli political coverage; the metric name reflects that observed distribution rather than its mathematical symmetry.

**Polarization Index.** For a given entity or topic, compute the mean Adversarial Score for each source (or each lean category). The Polarization Index is the gap between the highest and lowest mean, with a standard-deviation diagnostic reported alongside. Sources or leans with fewer than two articles on the entity are excluded to avoid inflating the index on thin coverage.

**Emotion Fingerprint.** Every article carries one of nine emotion labels assigned by Claude. Labels collapse into four registers for the radar charts: **Hostile** (anger, disgust, disappointment), **Anxious** (fear, sadness, anxiety, tension, concern), **Hopeful** (anticipation, joy, pride, relief), **Neutral** (neutral, surprise). The four-axis radar is more readable on small datasets than the nine-axis raw version; both versions live in the codebase.

**Source-lean mapping.** Walla → Left, Ynet → Center-Left, Globes → Center, Jerusalem Post → Center-Right, Channel 14 → Right. Reflects common positioning in Israeli media literature; open to refinement and explicitly documented so the user can override it.

## Tech Stack

| Layer | Tools |
|-------|-------|
| Language | Python 3.13 |
| Scraping | feedparser, requests, BeautifulSoup, lxml, JSON-LD extraction |
| Hebrew NLP | transformers, DictaBERT (`dicta-il/dictabert-sentiment`) |
| English NLP | Cardiff RoBERTa (`cardiffnlp/twitter-roberta-base-sentiment-latest`) |
| LLM | Anthropic Claude (Haiku 4.5) for emotion, entity, topic enrichment |
| Storage | SQLite via SQLAlchemy, CSV exports for sharing |
| Dashboard | Streamlit (5 tabs, custom KPI layout, caching) |
| Visualization | Plotly (bar, scatter, radar, heatmap) |
| Scheduling | Windows Task Scheduler |
| Analytics | pandas, numpy for metric computation |

## Project Structure

```
news-sentiment-project/
├── app/
│   └── streamlit_app.py          The 5-tab interactive dashboard
├── src/
│   ├── data_load.py              Quality-filtered loaders for articles & entities
│   ├── metrics.py                Adversarial Score, Polarization Index, Fingerprint
│   └── viz.py                    Reusable Plotly chart builders
├── scripts/
│   ├── diagnose_dates.py         Discover where each outlet hides publish dates
│   ├── backfill_dates.py         Recover missing timestamps for existing articles
│   └── (other ETL utilities)
├── data/
│   └── exports/
│       ├── articles_final.csv    Clean article-level data (committed, ready for the dashboard)
│       └── entities_final.csv    Clean entity-level mentions (committed)
├── docs/
│   ├── Project_Summary.pdf       One-page executive summary
│   └── images/                   Dashboard screenshots + pipeline diagram
├── pipeline.py                   End-to-end orchestration
├── scrapers.py                   RSS scrapers for all 5 sources
├── archive_scrapers.py           HTML archive scrapers with JSON-LD date parse
├── claude_analyzer.py            Claude API enrichment wrapper
├── data_clean.py                 Cleaning and feature engineering
├── prepare_final_data.py         Final CSV exports
├── nlp.py                        DictaBERT and RoBERTa wrappers
├── database.py                   SQLAlchemy schema and helpers
├── config.py                     Source registry, keywords, paths
└── requirements.txt
```

## Setup

This repo ships with the cleaned CSV exports (`data/exports/articles_final.csv` and `entities_final.csv`) so the dashboard runs immediately without re-running the pipeline.

```bash
git clone https://github.com/taljacob28/hebrew-news-sentiment.git
cd hebrew-news-sentiment

python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

streamlit run app/streamlit_app.py
```

That is the full path to a running dashboard.

### Extending the dataset

To pull new articles, run the pipeline. You will need an Anthropic API key in a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Then:

```bash
python pipeline.py --run                    # latest RSS, today's articles
python pipeline.py --archive --days 14      # archive backfill, 14 days back
python analyze_existing.py --auto           # Claude enrichment on new rows
python data_clean.py                        # cleaning
python prepare_final_data.py                # final CSVs
```

The first invocation downloads the DictaBERT and Cardiff RoBERTa models (~1 GB combined, one-time).

## Limitations

- **Thin time window.** The current snapshot covers roughly 16 days. Daily collection is ongoing via Windows Task Scheduler, but trend analysis at the moment is illustrative rather than statistically powerful.
- **Conservative Hebrew sentiment models.** DictaBERT-sentiment scores most news prose as neutral, which is why the Adversarial Score concentrates near zero and below. A production version would calibrate or fine-tune on labeled news data.
- **Source-lean mapping is editorial.** The five-category mapping reflects common positioning in Israeli media research but is an editorial judgment, not a measurement.
- **RSS bias.** Articles are sourced from RSS feeds and category pages; outlets that publish mostly to mobile apps or social media will be underrepresented.
- **Entity normalization carries model error.** Claude maps Hebrew entity mentions to canonical English forms (e.g., צה"ל → IDF), validated on a small held-out sample.

## Roadmap

- Calibrate sentiment thresholds with a small human-labeled validation set.
- Add an explicit "framing divergence" page that compares headline vs body intensity per outlet over time.
- Bring online a sixth source to break ties in cross-source comparisons.
- Build a weekly email digest that flags the day's most polarized entity.

## Contact

**Tal Jacob** — Data Analyst.

- GitHub: [@taljacob28](https://github.com/taljacob28)
- Email: <taljacob28@gmail.com>
- LinkedIn: [linkedin.com/in/tal-jacob-9753bb256](https://www.linkedin.com/in/tal-jacob-9753bb256)

## License

MIT
