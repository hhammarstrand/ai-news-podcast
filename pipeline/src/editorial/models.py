"""Models for podcast script structures."""

from pydantic import BaseModel


class ScriptSegment(BaseModel):
    speaker: str  # "host", "co_host"
    text: str
    story_index: int | None = None  # Which story this segment covers


class PodcastScript(BaseModel):
    episode_title: str
    episode_summary: str
    segments: list[ScriptSegment]
    story_urls: list[str]  # Source URLs for show notes
