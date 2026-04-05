"""News ingestion module — fetches stories from RSS, APIs, and scrapers."""

from .fetcher import NewsFetcher
from .models import NewsStory

__all__ = ["NewsFetcher", "NewsStory"]
