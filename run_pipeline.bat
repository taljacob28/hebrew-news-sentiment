@echo off
REM Hebrew News Sentiment - Daily automated run
REM Activates the venv and runs the full pipeline:
REM   1. Scraping + sentiment classification (DictaBERT / RoBERTa)
REM   2. Claude API enrichment (emotion, entities, topics)
REM   3. Refresh cleaned articles CSV
REM   4. Refresh final canonical CSVs (articles_final.csv, entities_final.csv)

cd /d C:\Users\talja\Desktop\news-sentiment-project

REM Activate virtual environment
call .\.venv\Scripts\activate.bat

REM Log start time
echo. >> logs\daily_run.log
echo === Run started at %date% %time% === >> logs\daily_run.log

REM Step 1: Scrape + run new sentiment classifier (3-class probabilities + headline-only pass)
echo --- Step 1: Scraping and sentiment classification --- >> logs\daily_run.log
python scripts\pipeline.py --run >> logs\daily_run.log 2>&1

REM Step 2: Run Claude API enrichment for any articles missing emotion/entities/topic
REM Cost: ~$0.002 per new article. Expect $0.05 to $0.15 per day.
echo --- Step 2: Claude API enrichment --- >> logs\daily_run.log
python scripts\analyze_existing.py --auto >> logs\daily_run.log 2>&1

REM Step 3: Refresh cleaned articles CSV (propagates all sentiment fields to disk)
echo --- Step 3: Data cleaning --- >> logs\daily_run.log
python scripts\data_clean.py >> logs\daily_run.log 2>&1

REM Step 4: Refresh final canonical CSVs (computes intensity and divergence, applies filters)
echo --- Step 4: Final data preparation --- >> logs\daily_run.log
python scripts\prepare_final_data.py >> logs\daily_run.log 2>&1

REM Log completion
echo === Run completed at %date% %time% === >> logs\daily_run.log
echo. >> logs\daily_run.log