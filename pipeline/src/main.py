"""Main pipeline entrypoint — run this to generate one episode."""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

from .audio.assembler import AudioAssembler
from .config import settings
from .distribution.publisher import EpisodePublisher
from .editorial.scriptwriter import ScriptWriter
from .ingestion.fetcher import NewsFetcher
from .tts.synthesizer import TTSSynthesizer

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()


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

    log.info("pipeline.complete", run_id=run_id, episode_url=episode_url)


if __name__ == "__main__":
    run_pipeline()
