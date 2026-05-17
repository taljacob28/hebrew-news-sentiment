"""
Configuration for Hebrew News Sentiment Analyzer.

Edit RSS feed URLs here if any source changes its endpoint.
Topic keywords drive the politics/security filter for sources without dedicated RSS feeds.
"""

from pathlib import Path

# Project paths (config.py lives in src/, so the project root is one level up)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "articles.db"

# News source RSS feeds (politics and security focused where available)
SOURCES = {
    "ynet": {
        "name": "Ynet",
        "language": "he",
        "feeds": [
            # Ynet news (general, will filter by keyword)
            "https://www.ynet.co.il/Integration/StoryRss2.xml",
            # Ynet politics
            "https://www.ynet.co.il/Integration/StoryRss1854.xml",
        ],
        "encoding": "utf-8",
    },
    "walla": {
        "name": "Walla",
        "language": "he",
        "feeds": [
            # Walla news
            "https://rss.walla.co.il/feed/22",
            # Walla politics
            "https://rss.walla.co.il/feed/2686",
        ],
        "encoding": "utf-8",
    },
"globes": {
    "name": "Globes",
    "language": "he",
    "feeds": [
        "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=2",
    ],
    "encoding": "utf-8",
},
"jpost": {
    "name": "Jerusalem Post",
    "language": "en",
    "feeds": [
        "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
    ],
    "encoding": "utf-8",
},
"c14": {
    "name": "Channel 14",
    "language": "he",
    "feeds": [
        "https://www.c14.co.il/feed/",
    ],
    "encoding": "utf-8",
},
}

# Topic filtering keywords (used as a fallback when feeds are general)
POLITICS_KEYWORDS_HE = [
    "ממשלה", "כנסת", "ראש הממשלה", "שר", "קואליציה", "אופוזיציה",
    "בחירות", "חקיקה", "חוק", "בג״ץ", "רפורמה", "מפלגה", "ליכוד",
    "יש עתיד", "המחנה הממלכתי", "ש״ס", "נתניהו", "לפיד", "גנץ",
]

SECURITY_KEYWORDS_HE = [
    "צה״ל", "צה\"ל", "מלחמה", "טרור", "פיגוע", "חמאס", "חיזבאללה",
    "איראן", "עזה", "לבנון", "גבול", "מבצע", "טיל", "מל״ט", "כוחות הביטחון",
    "שב״כ", "מוסד", "צבא", "חיילים", "פצועים", "נפגעים",
]

POLITICS_KEYWORDS_EN = [
    "knesset", "government", "coalition", "opposition", "election",
    "prime minister", "netanyahu", "minister", "parliament", "vote",
    "judicial", "supreme court", "reform", "party", "policy",
]

SECURITY_KEYWORDS_EN = [
    "idf", "military", "war", "terror", "attack", "hamas", "hezbollah",
    "iran", "gaza", "lebanon", "border", "operation", "missile", "drone",
    "soldiers", "casualties", "wounded", "shin bet", "mossad",
]

# NLP model settings
HEBREW_SENTIMENT_MODEL = "dicta-il/dictabert-sentiment"
ENGLISH_SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"

# Pipeline settings
MAX_ARTICLES_PER_FEED = 50
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"