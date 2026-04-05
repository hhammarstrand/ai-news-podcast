"""Central configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str
    claude_model: str = "claude-opus-4-6"

    # MiniMax TTS
    minimax_api_key: str = ""
    minimax_group_id: str = ""

    # ElevenLabs TTS (optional fallback)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id_host: str = "pNInz6obpgDQGcFmaJgB"  # Adam voice

    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-north-1"
    aws_s3_bucket: str

    # Database
    database_url: str

    # News sources
    news_api_key: str = ""
    svt_rss_url: str = "https://www.svt.se/nyheter/rss.xml"

    # Podcast metadata
    podcast_title: str = "AI Nyhetspodcast"
    podcast_language: str = "sv"
    podcast_author: str = "AI News AB"
    podcast_rss_s3_key: str = "feed.xml"

    # Pipeline
    max_stories_per_episode: int = 8
    target_episode_duration_min: int = 10
    pipeline_output_dir: str = "/tmp/podcast_output"


settings = Settings()
