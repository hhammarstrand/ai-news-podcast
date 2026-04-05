"""Data models for ingested news stories."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class NewsCategory(str, Enum):
    SWEDEN = "sweden"
    INTERNATIONAL = "international"
    TECH = "tech"
    AI = "ai"


class NewsStory(BaseModel):
    title: str
    summary: str
    url: str
    source: str
    category: NewsCategory
    published_at: datetime
    full_text: str = ""
    image_url: str = ""
