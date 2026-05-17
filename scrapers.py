"""
News scrapers for four Israeli sources: Ynet, Walla, Globes, Jerusalem Post.

Each scraper inherits from BaseScraper and implements source-specific parsing.
Articles are filtered to politics and security topics either via dedicated RSS
feeds or via keyword matching on headlines and snippets.
"""

import hashlib
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

import feedparser
import requests
from dateutil import parser as date_parser

from config import (
    SOURCES,
    POLITICS_KEYWORDS_HE,
    SECURITY_KEYWORDS_HE,
    POLITICS_KEYWORDS_EN,
    SECURITY_KEYWORDS_EN,
    MAX_ARTICLES_PER_FEED,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """A single news article with metadata."""

    source: str
    language: str
    url: str
    headline: str
    snippet: str
    published_at: Optional[datetime]
    topic: str

    @property
    def hash(self) -> str:
        """Stable identifier for deduplication."""
        key = f"{self.url}|{self.headline}".encode("utf-8")
        return hashlib.sha256(key).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hash"] = self.hash
        if self.published_at:
            d["published_at"] = self.published_at.isoformat()
        return d


class BaseScraper:
    """Base class with shared RSS parsing and topic classification logic."""

    def __init__(self, source_key: str):
        self.source_key = source_key
        self.config = SOURCES[source_key]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self) -> List[Article]:
        """Fetch and parse all configured feeds for this source."""
        articles = []
        for feed_url in self.config["feeds"]:
            try:
                logger.info(f"Fetching {self.source_key}: {feed_url}")
                articles.extend(self._parse_feed(feed_url))
            except Exception as e:
                logger.error(f"Failed to fetch {feed_url}: {e}")
        return articles

    def _parse_feed(self, feed_url: str) -> List[Article]:
        """Parse a single RSS feed. Tries direct fetch first, falls back to feedparser."""
        parsed = None
        try:
            response = self.session.get(feed_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if not parsed.entries:
                logger.warning(f"Direct fetch returned no entries for {feed_url}, trying feedparser directly")
                parsed = feedparser.parse(feed_url)
        except Exception as e:
            logger.warning(f"Direct fetch failed for {feed_url} ({e}), trying feedparser directly")
            parsed = feedparser.parse(feed_url)
            if not parsed.entries:
                raise

        articles = []
        for entry in parsed.entries[:MAX_ARTICLES_PER_FEED]:
            article = self._entry_to_article(entry)
            if article and self._is_relevant(article):
                articles.append(article)
        return articles

    def _entry_to_article(self, entry) -> Optional[Article]:
        """Convert a feedparser entry to an Article."""
        headline = entry.get("title", "").strip()
        if not headline:
            return None

        snippet = self._extract_snippet(entry)
        url = entry.get("link", "").strip()
        published = self._parse_date(entry)

        article = Article(
            source=self.source_key,
            language=self.config["language"],
            url=url,
            headline=headline,
            snippet=snippet,
            published_at=published,
            topic="other",
        )
        return article

    def _extract_snippet(self, entry) -> str:
        """Extract a snippet from the entry."""
        for field in ["description", "summary", "content"]:
            value = entry.get(field, "")
            if isinstance(value, list) and value:
                value = value[0].get("value", "") if isinstance(value[0], dict) else str(value[0])
            if value:
                return self._strip_html(str(value))[:500]
        return ""

    @staticmethod
    def _strip_html(text: str) -> str:
        """Lightweight HTML tag stripper."""
        from bs4 import BeautifulSoup
        return BeautifulSoup(text, "lxml").get_text(separator=" ").strip()

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """Parse the published date from common feed fields."""
        for field in ["published", "updated", "pubDate"]:
            value = entry.get(field)
            if value:
                try:
                    return date_parser.parse(value)
                except (ValueError, TypeError):
                    continue
        return None

    def _is_relevant(self, article: Article) -> bool:
        """Mark article topic. Returns True if politics or security."""
        text = f"{article.headline} {article.snippet}".lower()

        if article.language == "he":
            politics_kw = POLITICS_KEYWORDS_HE
            security_kw = SECURITY_KEYWORDS_HE
        else:
            politics_kw = POLITICS_KEYWORDS_EN
            security_kw = SECURITY_KEYWORDS_EN

        is_politics = any(kw.lower() in text for kw in politics_kw)
        is_security = any(kw.lower() in text for kw in security_kw)

        if is_politics and is_security:
            article.topic = "both"
        elif is_politics:
            article.topic = "politics"
        elif is_security:
            article.topic = "security"
        else:
            article.topic = "other"

        return article.topic != "other"


class YnetScraper(BaseScraper):
    def __init__(self):
        super().__init__("ynet")


class WallaScraper(BaseScraper):
    def __init__(self):
        super().__init__("walla")


class GlobesScraper(BaseScraper):
    def __init__(self):
        super().__init__("globes")


class JerusalemPostScraper(BaseScraper):
    def __init__(self):
        super().__init__("jpost")

class C14Scraper(BaseScraper):
    def __init__(self):
        super().__init__("c14")

def get_all_scrapers() -> List[BaseScraper]:
    """Return one scraper per configured source."""
    return [
        YnetScraper(),
        WallaScraper(),
        GlobesScraper(),
        JerusalemPostScraper(),
        C14Scraper(),
    ]


def fetch_all() -> List[Article]:
    """Fetch articles from every source."""
    all_articles = []
    for scraper in get_all_scrapers():
        articles = scraper.fetch()
        logger.info(f"{scraper.source_key}: {len(articles)} relevant articles")
        all_articles.extend(articles)
    return all_articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    articles = fetch_all()
    print(f"\nTotal articles fetched: {len(articles)}")
    for art in articles[:5]:
        print(f"\n[{art.source} | {art.topic}] {art.headline}")
        print(f"  {art.url}")