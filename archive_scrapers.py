"""
Archive scrapers for historical article fetching across 5 sources.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from config import (
    POLITICS_KEYWORDS_HE,
    SECURITY_KEYWORDS_HE,
    POLITICS_KEYWORDS_EN,
    SECURITY_KEYWORDS_EN,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from scrapers import Article

logger = logging.getLogger(__name__)


class BaseArchiveScraper:
    SOURCE_KEY = "base"
    LANGUAGE = "he"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "he,en;q=0.9",
        })

    def _classify_topic(self, headline, snippet, language="he"):
        text = (headline + " " + snippet).lower()
        if language == "he":
            politics_kw = POLITICS_KEYWORDS_HE
            security_kw = SECURITY_KEYWORDS_HE
        else:
            politics_kw = POLITICS_KEYWORDS_EN
            security_kw = SECURITY_KEYWORDS_EN

        is_politics = any(kw.lower() in text for kw in politics_kw)
        is_security = any(kw.lower() in text for kw in security_kw)

        if is_politics and is_security:
            return "both"
        elif is_politics:
            return "politics"
        elif is_security:
            return "security"
        return "other"

    def _polite_delay(self, seconds=0.8):
        time.sleep(seconds)

    def _extract_date_from_meta(self, soup):
        # Standard meta and time tags first.
        selectors = [
            ('meta[property="article:published_time"]', "content"),
            ('meta[name="publish-date"]', "content"),
            ('meta[itemprop="datePublished"]', "content"),
            ("time[datetime]", "datetime"),
        ]
        for selector, attr in selectors:
            tag = soup.select_one(selector)
            if tag and tag.get(attr):
                try:
                    return date_parser.parse(tag[attr])
                except (ValueError, TypeError):
                    continue

        # JSON-LD structured data fallback. Walla and Channel 14 embed dates
        # there, not in meta tags. ISO 8601 inside the script body.
        for script in soup.select('script[type="application/ld+json"]'):
            text = script.string or script.get_text() or ""
            for key in ("datePublished", "dateCreated", "uploadDate"):
                match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', text)
                if match:
                    try:
                        return date_parser.parse(match.group(1))
                    except (ValueError, TypeError):
                        continue
        return None

    @staticmethod
    def _strip_html(text):
        if not text:
            return ""
        return BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()


class YnetArchiveScraper(BaseArchiveScraper):
    SOURCE_KEY = "ynet"
    LANGUAGE = "he"

    RSS_FEEDS = [
        "https://www.ynet.co.il/Integration/StoryRss2.xml",
        "https://www.ynet.co.il/Integration/StoryRss1854.xml",
        "https://www.ynet.co.il/Integration/StoryRss3.xml",
        "https://www.ynet.co.il/Integration/StoryRss194.xml",
        "https://www.ynet.co.il/Integration/StoryRss544.xml",
    ]

    def fetch(self, days_back=30):
        cutoff = datetime.now() - timedelta(days=days_back)
        all_articles = []
        seen_urls = set()
        for feed_url in self.RSS_FEEDS:
            try:
                logger.info("Ynet RSS: " + feed_url)
                articles = self._fetch_feed(feed_url, cutoff, seen_urls)
                all_articles.extend(articles)
                self._polite_delay(1)
            except Exception as e:
                logger.warning("  Ynet feed failed: " + str(e))
        logger.info("Ynet archive: " + str(len(all_articles)) + " articles")
        return all_articles

    def _fetch_feed(self, feed_url, cutoff, seen_urls):
        try:
            response = self.session.get(feed_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if not parsed.entries:
                parsed = feedparser.parse(feed_url)
        except Exception:
            parsed = feedparser.parse(feed_url)

        articles = []
        for entry in parsed.entries[:100]:
            url = entry.get("link", "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            headline = entry.get("title", "").strip()
            if not headline:
                continue
            snippet = self._strip_html(entry.get("summary", "") or entry.get("description", ""))[:500]
            published = None
            for field in ["published", "updated", "pubDate"]:
                if entry.get(field):
                    try:
                        published = date_parser.parse(entry[field])
                        break
                    except (ValueError, TypeError):
                        continue
            if published and published.tzinfo:
                published = published.replace(tzinfo=None)
            if published and published < cutoff:
                continue
            topic = self._classify_topic(headline, snippet, self.LANGUAGE)
            if topic == "other":
                continue
            articles.append(Article(
                source=self.SOURCE_KEY,
                language=self.LANGUAGE,
                url=url,
                headline=headline,
                snippet=snippet,
                published_at=published,
                topic=topic,
            ))
        return articles


class WallaArchiveScraper(BaseArchiveScraper):
    SOURCE_KEY = "walla"
    LANGUAGE = "he"
    BASE_URL = "https://news.walla.co.il"

    CATEGORY_URLS = [
        "https://news.walla.co.il/category/2686",
        "https://news.walla.co.il/category/22",
        "https://news.walla.co.il/category/9",
    ]

    def fetch(self, days_back=30):
        cutoff = datetime.now() - timedelta(days=days_back)
        all_articles = []
        seen_urls = set()
        for category_url in self.CATEGORY_URLS:
            logger.info("Walla: scanning " + category_url)
            articles = self._fetch_category(category_url, cutoff, seen_urls)
            all_articles.extend(articles)
            self._polite_delay(1.5)
        logger.info("Walla archive: " + str(len(all_articles)) + " articles")
        return all_articles

    def _fetch_category(self, url, cutoff, seen_urls):
        articles = []
        max_pages = 8
        for page_num in range(1, max_pages + 1):
            page_url = url + ("?page=" + str(page_num) if page_num > 1 else "")
            try:
                logger.info("  Page " + str(page_num) + ": " + page_url)
                response = self.session.get(page_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "lxml")
                article_links = self._extract_article_links(soup, seen_urls)
                logger.info("    Found " + str(len(article_links)) + " new links on page " + str(page_num))
                if len(article_links) == 0:
                    logger.info("    No new links, stopping pagination")
                    break
                page_articles = []
                for link in article_links[:50]:
                    try:
                        article = self._fetch_article(link, cutoff)
                        if article:
                            page_articles.append(article)
                        self._polite_delay(0.4)
                    except Exception:
                        continue
                articles.extend(page_articles)
                if len(page_articles) == 0 and page_num > 1:
                    logger.info("    All articles too old, stopping pagination")
                    break
                self._polite_delay(1)
            except Exception as e:
                logger.warning("  Page " + str(page_num) + " failed: " + str(e))
                break
        return articles

    def _extract_article_links(self, soup, seen_urls):
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"/(?:item|article|breaking)/\d+", href) or re.search(r"/\d{7,}/?$", href):
                full_url = urljoin(self.BASE_URL, href)
                clean_url = full_url.split("?")[0].split("#")[0]
                if clean_url not in seen_urls and "walla.co.il" in clean_url:
                    seen_urls.add(clean_url)
                    links.append(clean_url)
        return links

    def _fetch_article(self, url, cutoff):
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.content, "lxml")
        h1 = soup.find("h1")
        headline = h1.get_text(strip=True) if h1 else ""
        if not headline:
            return None
        snippet = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            snippet = meta_desc["content"][:500]
        published = self._extract_date_from_meta(soup)
        if published and published.tzinfo:
            published = published.replace(tzinfo=None)
        if published and published < cutoff:
            return None
        topic = self._classify_topic(headline, snippet, self.LANGUAGE)
        if topic == "other":
            return None
        return Article(
            source=self.SOURCE_KEY,
            language=self.LANGUAGE,
            url=url,
            headline=headline,
            snippet=snippet,
            published_at=published,
            topic=topic,
        )


class GlobesArchiveScraper(BaseArchiveScraper):
    SOURCE_KEY = "globes"
    LANGUAGE = "he"

    RSS_FEEDS = [
        "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=2",
        "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=585",
        "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=1725",
    ]

    def fetch(self, days_back=30):
        cutoff = datetime.now() - timedelta(days=days_back)
        all_articles = []
        seen_urls = set()
        for feed_url in self.RSS_FEEDS:
            try:
                logger.info("Globes RSS: " + feed_url)
                articles = self._fetch_feed(feed_url, cutoff, seen_urls)
                all_articles.extend(articles)
                self._polite_delay(1)
            except Exception as e:
                logger.warning("  Globes failed: " + str(e))
        logger.info("Globes archive: " + str(len(all_articles)) + " articles")
        return all_articles

    def _fetch_feed(self, feed_url, cutoff, seen_urls):
        try:
            response = self.session.get(feed_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if not parsed.entries:
                parsed = feedparser.parse(feed_url)
        except Exception:
            parsed = feedparser.parse(feed_url)

        articles = []
        for entry in parsed.entries[:100]:
            url = entry.get("link", "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            headline = entry.get("title", "").strip()
            if not headline:
                continue
            snippet = self._strip_html(entry.get("summary", "") or entry.get("description", ""))[:500]
            published = None
            for field in ["published", "updated", "pubDate"]:
                if entry.get(field):
                    try:
                        published = date_parser.parse(entry[field])
                        break
                    except (ValueError, TypeError):
                        continue
            if published and published.tzinfo:
                published = published.replace(tzinfo=None)
            if published and published < cutoff:
                continue
            topic = self._classify_topic(headline, snippet, self.LANGUAGE)
            if topic == "other":
                continue
            articles.append(Article(
                source=self.SOURCE_KEY,
                language=self.LANGUAGE,
                url=url,
                headline=headline,
                snippet=snippet,
                published_at=published,
                topic=topic,
            ))
        return articles


class JerusalemPostArchiveScraper(BaseArchiveScraper):
    SOURCE_KEY = "jpost"
    LANGUAGE = "en"

    RSS_FEEDS = [
        "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
        "https://www.jpost.com/rss/rssfeedsisraelnews.aspx",
        "https://www.jpost.com/rss/rssfeedsmiddleeastnews.aspx",
    ]

    def fetch(self, days_back=30):
        cutoff = datetime.now() - timedelta(days=days_back)
        all_articles = []
        seen_urls = set()
        for feed_url in self.RSS_FEEDS:
            try:
                logger.info("JPost RSS: " + feed_url)
                parsed = feedparser.parse(feed_url)
                logger.info("  Parsed " + str(len(parsed.entries)) + " entries")
                for entry in parsed.entries[:80]:
                    url = entry.get("link", "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    headline = entry.get("title", "").strip()
                    if not headline:
                        continue
                    snippet = self._strip_html(entry.get("summary", "") or entry.get("description", ""))[:500]
                    published = None
                    for field in ["published", "updated", "pubDate"]:
                        if entry.get(field):
                            try:
                                published = date_parser.parse(entry[field])
                                break
                            except (ValueError, TypeError):
                                continue
                    if published and published.tzinfo:
                        published = published.replace(tzinfo=None)
                    if published and published < cutoff:
                        continue
                    topic = self._classify_topic(headline, snippet, self.LANGUAGE)
                    if topic == "other":
                        continue
                    all_articles.append(Article(
                        source=self.SOURCE_KEY,
                        language=self.LANGUAGE,
                        url=url,
                        headline=headline,
                        snippet=snippet,
                        published_at=published,
                        topic=topic,
                    ))
                self._polite_delay(1)
            except Exception as e:
                logger.warning("  JPost failed: " + str(e))
        logger.info("JPost archive: " + str(len(all_articles)) + " articles")
        return all_articles


class Now14ArchiveScraper(BaseArchiveScraper):
    SOURCE_KEY = "c14"
    LANGUAGE = "he"
    BASE_URL = "https://www.c14.co.il"

    CATEGORY_URLS = [
        "https://www.c14.co.il/",
    ]

    def fetch(self, days_back=30):
        cutoff = datetime.now() - timedelta(days=days_back)
        all_articles = []
        seen_urls = set()
        for category_url in self.CATEGORY_URLS:
            logger.info("Now14: scanning " + category_url)
            articles = self._fetch_category(category_url, cutoff, seen_urls)
            all_articles.extend(articles)
            self._polite_delay(1.5)
        logger.info("Now14 archive: " + str(len(all_articles)) + " articles")
        return all_articles

    def _fetch_category(self, url, cutoff, seen_urls):
        articles = []
        max_pages = 8
        for page_num in range(1, max_pages + 1):
            page_url = url + ("?page=" + str(page_num) if page_num > 1 else "")
            try:
                logger.info("  Page " + str(page_num) + ": " + page_url)
                response = self.session.get(page_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "lxml")
                article_links = self._extract_article_links(soup, seen_urls)
                logger.info("    Found " + str(len(article_links)) + " new links on page " + str(page_num))
                if len(article_links) == 0:
                    logger.info("    No new links, stopping pagination")
                    break
                page_articles = []
                for link in article_links[:50]:
                    try:
                        article = self._fetch_article(link, cutoff)
                        if article:
                            page_articles.append(article)
                        self._polite_delay(0.4)
                    except Exception:
                        continue
                articles.extend(page_articles)
                if len(page_articles) == 0 and page_num > 1:
                    logger.info("    All articles too old, stopping pagination")
                    break
                self._polite_delay(1)
            except Exception as e:
                logger.warning("  Page " + str(page_num) + " failed: " + str(e))
                break
        return articles

    def _extract_article_links(self, soup, seen_urls):
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"/(?:archive|article)/\d+", href):
                full_url = urljoin(self.BASE_URL, href)
                clean_url = full_url.split("?")[0].split("#")[0]
                if clean_url not in seen_urls and "c14.co.il" in clean_url:
                    seen_urls.add(clean_url)
                    links.append(clean_url)
        return links

    def _fetch_article(self, url, cutoff):
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.content, "lxml")
        h1 = soup.find("h1")
        headline = h1.get_text(strip=True) if h1 else ""
        if not headline:
            return None
        snippet = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            snippet = meta_desc["content"][:500]
        published = self._extract_date_from_meta(soup)
        if published and published.tzinfo:
            published = published.replace(tzinfo=None)
        if published and published < cutoff:
            return None
        topic = self._classify_topic(headline, snippet, self.LANGUAGE)
        if topic == "other":
            return None
        return Article(
            source=self.SOURCE_KEY,
            language=self.LANGUAGE,
            url=url,
            headline=headline,
            snippet=snippet,
            published_at=published,
            topic=topic,
        )


def fetch_archives(days_back=30):
    scrapers = [
        YnetArchiveScraper(),
        WallaArchiveScraper(),
        GlobesArchiveScraper(),
        JerusalemPostArchiveScraper(),
        Now14ArchiveScraper(),
    ]
    all_articles = []
    for scraper in scrapers:
        try:
            articles = scraper.fetch(days_back=days_back)
            all_articles.extend(articles)
        except Exception as e:
            logger.error("Scraper " + scraper.SOURCE_KEY + " failed: " + str(e))
    return all_articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    logger.info("Fetching archive for last " + str(days) + " days")
    articles = fetch_archives(days_back=days)
    print("\nTotal articles fetched: " + str(len(articles)))
    from collections import Counter
    by_source = Counter(a.source for a in articles)
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print("  " + source + ": " + str(count))
    by_topic = Counter(a.topic for a in articles)
    print("\nBy topic:")
    for topic, count in sorted(by_topic.items(), key=lambda x: -x[1]):
        print("  " + topic + ": " + str(count))
    print("\nSample articles:")
    for art in articles[:5]:
        print("\n[" + art.source + " | " + art.topic + "] " + art.headline)
        print("  Published: " + str(art.published_at))
        print("  " + art.url)