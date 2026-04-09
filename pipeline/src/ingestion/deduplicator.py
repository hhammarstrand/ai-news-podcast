"""Deduplication logic — filters out stories already covered or re-reporting same facts."""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import Article, Episode, StoryCluster
from .models import NewsStory

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "was", "are", "were", "been", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
    "shall", "can", "need", "dare", "ought", "used", "this", "that", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "what", "which", "who", "whom",
    "their", "them", "they", "his", "her", "its", "our", "my", "your",
    "up", "down", "out", "more", "most", "some", "any", "no", "not", "only",
    "just", "also", "very", "so", "than", "too", "very", "s", "t", "m",
}

DUPLICATE_WINDOW_DAYS = 7
FOLLOWUP_GRACE_DAYS = 3


def extract_keywords(text: str) -> set[str]:
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return {w for w in words if w not in STOP_WORDS}


def make_topic_key(story: NewsStory) -> str:
    keywords = extract_keywords(story.title)
    if story.summary:
        keywords.update(list(extract_keywords(story.summary))[:5])
    sorted_keywords = sorted(keywords)[:8]
    return "|".join(sorted_keywords)


def find_existing_cluster(db: Session, topic_key: str) -> Optional[StoryCluster]:
    return db.query(StoryCluster).filter(StoryCluster.topic_key == topic_key).first()


def deduplicate(stories: list[NewsStory], db: Session) -> list[NewsStory]:
    if not stories:
        return []

    stories_by_key: dict[str, list[NewsStory]] = {}
    for story in stories:
        key = make_topic_key(story)
        stories_by_key.setdefault(key, []).append(story)

    existing_urls: set[str] = {
        row[0]
        for row in db.query(Article.url)
        .filter(Article.url.in_([s.url for s in stories]))
        .all()
    }

    new_stories = []
    for topic_key, topic_stories in stories_by_key.items():
        first_story = topic_stories[0]
        if first_story.url in existing_urls:
            logger.debug("All %d stories for topic %s skipped (URL already exists)", len(topic_stories), topic_key)
            continue

        cluster = find_existing_cluster(db, topic_key)

        if cluster is None:
            new_stories.extend(topic_stories)
            logger.debug("Topic %s is new, adding %d stories", topic_key, len(topic_stories))
            continue

        if not cluster.covered_in_episode:
            new_stories.extend(topic_stories)
            logger.debug("Topic %s cluster exists but not yet covered", topic_key)
            continue

        if cluster.last_covered_at:
            days_since_covered = (datetime.now(tz=timezone.utc) - cluster.last_covered_at).days
            if days_since_covered > DUPLICATE_WINDOW_DAYS:
                new_stories.extend(topic_stories)
                logger.info("Topic %s was covered %d days ago, treating as new", topic_key, days_since_covered)
            else:
                has_new_info = _detect_followup(first_story, cluster)
                if has_new_info:
                    new_stories.extend(topic_stories)
                    logger.info("Topic %s has follow-up with new information", topic_key)
                else:
                    logger.info("Topic %s is duplicate of recently covered story, skipping", topic_key)
        else:
            new_stories.extend(topic_stories)

    logger.info(
        "Deduplication: %d total, %d new after clustering",
        len(stories),
        len(new_stories),
    )
    return new_stories


def _detect_followup(story: NewsStory, cluster: StoryCluster) -> bool:
    if cluster.last_covered_at:
        days_old = (story.published_at - cluster.last_covered_at).days
        if days_old > FOLLOWUP_GRACE_DAYS:
            return True

    if story.full_text and len(story.full_text) > 200:
        return True

    summary_words = set(re.findall(r"\b[a-z]{4,}\b", story.summary.lower()))
    title_words = set(re.findall(r"\b[a-z]{4,}\b", story.title.lower()))
    combined = summary_words | title_words
    if len(combined) > 15:
        return True

    return False


def persist(stories: list[NewsStory], db: Session) -> int:
    if not stories:
        return 0

    stories_by_key: dict[str, list[NewsStory]] = {}
    for story in stories:
        key = make_topic_key(story)
        stories_by_key.setdefault(key, []).append(story)

    rows = []
    for topic_key, topic_stories in stories_by_key.items():
        cluster = find_existing_cluster(db, topic_key)
        if cluster is None:
            cluster = StoryCluster(
                topic_key=topic_key,
                title=topic_stories[0].title,
                article_count=0,
            )
            db.add(cluster)
            db.flush()

        for story in topic_stories:
            rows.append(
                Article(
                    url=story.url,
                    title=story.title,
                    summary=story.summary,
                    full_text=story.full_text,
                    source=story.source,
                    category=story.category,
                    published_at=story.published_at,
                    cluster_id=cluster.id,
                )
            )

        cluster.last_seen_at = datetime.now(tz=timezone.utc)
        cluster.article_count += len(topic_stories)

    db.add_all(rows)
    db.commit()
    logger.info("Persisted %d new articles in %d clusters", len(rows), len(stories_by_key))
    return len(rows)


def mark_episode_covered(db: Session, story_urls: list[str], episode_title: str, episode_url: str | None = None) -> None:
    cluster_ids = (
        db.query(Article.cluster_id)
        .filter(Article.url.in_(story_urls))
        .filter(Article.cluster_id.isnot(None))
        .distinct()
        .all()
    )
    cluster_ids = [cid for (cid,) in cluster_ids if cid is not None]

    if cluster_ids:
        db.query(StoryCluster).filter(StoryCluster.id.in_(cluster_ids)).update(
            {"covered_in_episode": True, "last_covered_at": datetime.now(tz=timezone.utc)},
            synchronize_session=False,
        )

    episode = Episode(
        episode_title=episode_title,
        episode_url=episode_url,
        story_count=len(story_urls),
    )
    db.add(episode)
    db.commit()
    logger.info("Marked %d clusters covered in episode '%s'", len(cluster_ids), episode_title)
