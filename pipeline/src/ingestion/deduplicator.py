"""Deduplication logic — filters out stories already in the database."""

import logging

from sqlalchemy.orm import Session

from ..db.models import Article
from .models import NewsStory

logger = logging.getLogger(__name__)


def deduplicate(stories: list[NewsStory], db: Session) -> list[NewsStory]:
    """Return only stories whose URL is not already in the articles table."""
    if not stories:
        return []

    urls = [s.url for s in stories]
    existing_urls: set[str] = {
        row[0] for row in db.query(Article.url).filter(Article.url.in_(urls)).all()
    }

    new_stories = [s for s in stories if s.url not in existing_urls]
    logger.info(
        "Deduplication: %d total, %d already known, %d new",
        len(stories),
        len(existing_urls),
        len(new_stories),
    )
    return new_stories


def persist(stories: list[NewsStory], db: Session) -> int:
    """Save new stories to the database. Returns count saved."""
    if not stories:
        return 0

    rows = [
        Article(
            url=s.url,
            title=s.title,
            summary=s.summary,
            full_text=s.full_text,
            source=s.source,
            category=s.category,
            published_at=s.published_at,
        )
        for s in stories
    ]
    db.add_all(rows)
    db.commit()
    logger.info("Persisted %d new articles", len(rows))
    return len(rows)
