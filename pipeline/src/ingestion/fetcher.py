"""NewsFetcher — pulls stories from configured sources."""

import logging
from datetime import datetime, timezone

import feedparser
import httpx

from .models import NewsCategory, NewsStory

logger = logging.getLogger(__name__)

# RSS feeds by category
RSS_FEEDS: dict[str, tuple[NewsCategory, str]] = {
    "SVT Nyheter": (NewsCategory.SWEDEN, "https://www.svt.se/nyheter/rss.xml"),
    "SR Nyheter": (NewsCategory.SWEDEN, "https://api.sr.se/api/v2/news/episodes?format=json"),
    "Reuters World": (NewsCategory.INTERNATIONAL, "https://feeds.reuters.com/Reuters/worldNews"),
    "BBC World": (NewsCategory.INTERNATIONAL, "http://feeds.bbci.co.uk/news/world/rss.xml"),
    "TechCrunch": (NewsCategory.TECH, "https://techcrunch.com/feed/"),
    "The Verge": (NewsCategory.TECH, "https://www.theverge.com/rss/index.xml"),
    "AI News": (NewsCategory.AI, "https://artificialintelligence-news.com/feed/"),
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
