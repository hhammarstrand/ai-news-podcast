"""Main pipeline entrypoint — run this to generate one episode."""

import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import structlog

from .audio.assembler import AudioAssembler
from .config import settings
from .db.session import SessionLocal
from .distribution.publisher import EpisodePublisher
from .editorial.scriptwriter import ScriptWriter
from .ingestion.deduplicator import deduplicate, mark_episode_covered, persist
from .ingestion.fetcher import NewsFetcher
from .tts.synthesizer import TTSSynthesizer

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()


@contextmanager
def get_db_session():
    if not settings.database_url:
        yield None
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def run_pipeline() -> None:
    run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = Path(settings.pipeline_output_dir) / run_id

    log.info("pipeline.start", run_id=run_id)

    # Step 1: Ingest news
    log.info("pipeline.ingestion.start")
    fetcher = NewsFetcher()
    stories = fetcher.fetch_all()
    log.info("pipeline.ingestion.done", story_count=len(stories))

    if not stories:
        log.error("pipeline.no_stories")
        sys.exit(1)

    # Step 1b: Deduplicate and persist stories
    with get_db_session() as db:
        if db is not None:
            stories = deduplicate(stories, db)
            persist(stories, db)
            log.info("pipeline.dedup.done", story_count=len(stories))

    # Step 2: Generate script
    log.info("pipeline.editorial.start")
    writer = ScriptWriter()
    script = writer.generate_script(stories)
    log.info("pipeline.editorial.done", title=script.episode_title, segments=len(script.segments))

    # Step 3: TTS
    log.info("pipeline.tts.start")
    tts = TTSSynthesizer()
    segment_paths = tts.synthesize_segments(script.segments, output_dir / "segments")
    log.info("pipeline.tts.done", segment_count=len(segment_paths))

    # Step 4: Assemble audio
    log.info("pipeline.assembly.start")
    assembler = AudioAssembler()
    episode_path = assembler.assemble(segment_paths, output_dir / "episode.mp3")
    log.info("pipeline.assembly.done", episode_path=str(episode_path))

    # Step 5: Publish
    log.info("pipeline.publish.start")
    publisher = EpisodePublisher()
    episode_url = publisher.publish(episode_path, script)
    log.info("pipeline.publish.done", episode_url=episode_url)

    # Step 5b: Mark story clusters as covered
    with get_db_session() as db:
        if db is not None:
            mark_episode_covered(db, script.story_urls, script.episode_title, episode_url)

    log.info("pipeline.complete", run_id=run_id, episode_url=episode_url)


if __name__ == "__main__":
    run_pipeline()
