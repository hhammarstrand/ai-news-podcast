"""Ingestion scheduler — runs the fetcher every 1-2 hours."""

import logging
import time

import schedule

from ..db.models import Base
from ..db.session import SessionLocal, engine
from .deduplicator import deduplicate, persist
from .fetcher import NewsFetcher

logger = logging.getLogger(__name__)


def run_ingestion_job() -> None:
    """Fetch and persist new articles. Called on schedule."""
    logger.info("ingestion_job.start")
    fetcher = NewsFetcher(max_age_hours=3)
    stories = fetcher.fetch_all()

    db = SessionLocal()
    try:
        new_stories = deduplicate(stories, db)
        saved = persist(new_stories, db)
        logger.info("ingestion_job.done", extra={"saved": saved, "total_fetched": len(stories)})
    finally:
        db.close()


def run_scheduler() -> None:
    """Block and run ingestion on a schedule. Called by the scheduler process."""
    Base.metadata.create_all(bind=engine)

    # Run immediately on startup, then every 90 minutes
    run_ingestion_job()
    schedule.every(90).minutes.do(run_ingestion_job)

    logger.info("Ingestion scheduler started. Running every 90 minutes.")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import structlog
    structlog.configure()
    run_scheduler()
