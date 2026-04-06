"""NewsFetcher — pulls stories from configured sources."""

import logging
from datetime import datetime, timezone

import feedparser
import httpx

from .models import NewsCategory, NewsStory

logger = logging.getLogger(__name__)

# RSS feeds by category
# Swedish: primary news sources
# International: global wire services and major outlets
# Tech: leading technology publications
# AI: AI/ML-specific news and research
RSS_FEEDS: dict[str, tuple[NewsCategory, str]] = {
    # Swedish News
    "SVT Nyheter": (NewsCategory.SWEDEN, "https://www.svt.se/nyheter/rss.xml"),
    "SR Nyheter": (NewsCategory.SWEDEN, "https://api.sr.se/api/v2/news/episodes?format=json"),
    "DN Nyheter": (NewsCategory.SWEDEN, "https://www.dn.se/nyheter/puff/rss/"),
    "GP Nyheter": (NewsCategory.SWEDEN, "https://www.gp.se/nyheter/rss"),
    "Expressen": (NewsCategory.SWEDEN, "https://feeds.expressen.se/nyheter"),
    "Aftonbladet": (NewsCategory.SWEDEN, "https://www.aftonbladet.se/nyheter/rss"),
    # International News
    "Reuters World": (NewsCategory.INTERNATIONAL, "https://feeds.reuters.com/Reuters/worldNews"),
    "BBC World": (NewsCategory.INTERNATIONAL, "http://feeds.bbci.co.uk/news/world/rss.xml"),
    "AP News": (NewsCategory.INTERNATIONAL, "https://rsshub.app/apnews/topnews"),
    "Al Jazeera": (NewsCategory.INTERNATIONAL, "https://www.aljazeera.com/xml/rss/all.xml"),
    "NPR News": (NewsCategory.INTERNATIONAL, "https://feeds.npr.org/1001/rss.xml"),
    "The Guardian World": (NewsCategory.INTERNATIONAL, "https://www.theguardian.com/world/rss"),
    # Tech News
    "TechCrunch": (NewsCategory.TECH, "https://techcrunch.com/feed/"),
    "The Verge": (NewsCategory.TECH, "https://www.theverge.com/rss/index.xml"),
    "Wired": (NewsCategory.TECH, "https://www.wired.com/feed/rss"),
    "Ars Technica": (NewsCategory.TECH, "https://feeds.arstechnica.com/arstechnica/index"),
    "VentureBeat": (NewsCategory.TECH, "https://venturebeat.com/feed/"),
    # AI News
    "AI News": (NewsCategory.AI, "https://artificialintelligence-news.com/feed/"),
    "MIT Tech Review": (NewsCategory.AI, "https://www.technologyreview.com/feed/"),
    "The Gradient": (NewsCategory.AI, "https://thegradient.pub/rss/"),
    "VentureBeat AI": (NewsCategory.AI, "https://venturebeat.com/category/ai/feed/"),
    "AI Insider": (NewsCategory.AI, "https://newsletter.artificialintelligence-insider.com/feed"),
}


class NewsFetcher:
    """Fetches and normalises news stories from all configured sources."""

    def __init__(self, max_age_hours: int = 24):
        self.max_age_hours = max_age_hours

    def fetch_all(self) -> list[NewsStory]:
        stories: list[NewsStory] = []
        for source_name, (category, url) in RSS_FEEDS.items():
            try:
                fetched = self._fetch_rss(source_name, category, url)
                stories.extend(fetched)
                logger.info("Fetched %d stories from %s", len(fetched), source_name)
            except Exception:
                logger.exception("Failed to fetch from %s", source_name)
        return stories

    def _fetch_rss(self, source: str, category: NewsCategory, url: str) -> list[NewsStory]:
        feed = feedparser.parse(url)
        stories = []
        for entry in feed.entries[:20]:
            published = self._parse_date(entry)
            if published is None:
                continue
            stories.append(
                NewsStory(
                    title=entry.get("title", "").strip(),
                    summary=entry.get("summary", "").strip(),
                    url=entry.get("link", ""),
                    source=source,
                    category=category,
                    published_at=published,
                )
            )
        return stories

    def _parse_date(self, entry: dict) -> datetime | None:
        try:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                import time
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass
        return datetime.now(tz=timezone.utc)
