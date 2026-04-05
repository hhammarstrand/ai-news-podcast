"""Tests for editorial scriptwriter."""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.editorial.scriptwriter import ScriptWriter
from src.editorial.models import ScriptSegment
from src.ingestion.models import NewsStory, NewsCategory
from datetime import datetime, timezone


class TestScriptWriter:
    """Test ScriptWriter class."""

    @pytest.fixture
    def mock_stories(self):
        """Create mock news stories."""
        return [
            NewsStory(
                title="Test News",
                summary="Test summary",
                url="https://example.com/news/1",
                source="TestSource",
                category=NewsCategory.SWEDEN,
                published_at=datetime.now(tz=timezone.utc),
            ),
            NewsStory(
                title="Another News",
                summary="Another summary",
                url="https://example.com/news/2",
                source="TestSource",
                category=NewsCategory.TECH,
                published_at=datetime.now(tz=timezone.utc),
            ),
        ]

    @pytest.fixture
    def mock_claude_response(self):
        """Create mock Claude API response."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='{"episode_title": "Test Episode", "episode_summary": "A test episode", "segments": [{"speaker": "host", "text": "Hello world", "story_index": 0}], "story_urls": ["https://example.com/news/1"]}'
            )
        ]
        return mock_response

    def test_generate_script_parses_valid_json(self, mock_stories, mock_claude_response):
        """Test that generate_script correctly parses valid JSON response."""
        with patch("src.editorial.scriptwriter.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_claude_response
            mock_anthropic.return_value = mock_client

            writer = ScriptWriter()
            script = writer.generate_script(mock_stories)

            assert script.episode_title == "Test Episode"
            assert script.episode_summary == "A test episode"
            assert len(script.segments) == 1
            assert script.segments[0].speaker == "host"
            assert script.segments[0].text == "Hello world"

    def test_generate_script_strips_markdown_code_fences(self, mock_stories):
        """Test that generate_script correctly strips markdown code fences."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='```json\n{"episode_title": "Test", "episode_summary": "Summary", "segments": [{"speaker": "host", "text": "Hi", "story_index": 0}], "story_urls": []}\n```'
            )
        ]

        with patch("src.editorial.scriptwriter.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            writer = ScriptWriter()
            script = writer.generate_script(mock_stories)

            assert script.episode_title == "Test"
            assert len(script.segments) == 1

    def test_generate_script_raises_on_invalid_json(self, mock_stories):
        """Test that generate_script raises ValueError on invalid JSON."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON")]

        with patch("src.editorial.scriptwriter.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            writer = ScriptWriter()
            with pytest.raises(ValueError, match="invalid JSON"):
                writer.generate_script(mock_stories)


class TestNewsFetcher:
    """Test NewsFetcher class."""

    def test_fetch_all_handles_feed_errors(self):
        """Test that fetch_all continues when a feed fails."""
        from src.ingestion.fetcher import NewsFetcher

        with patch("src.ingestion.fetcher.feedparser.parse") as mock_parse:
            mock_parse.side_effect = Exception("Network error")

            fetcher = NewsFetcher()
            stories = fetcher.fetch_all()

            assert stories == []

    def test_fetch_all_limits_entries(self):
        """Test that _fetch_rss limits entries to 20."""
        from src.ingestion.fetcher import NewsFetcher, RSS_FEEDS
        from src.ingestion.models import NewsCategory

        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key: {
            "title": "Test",
            "summary": "Summary",
            "link": "https://example.com/1",
        }.get(key)
        mock_entry.published_parsed = None

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry] * 30

        with patch("src.ingestion.fetcher.feedparser.parse", return_value=mock_feed):
            fetcher = NewsFetcher()
            _, (category, url) = list(RSS_FEEDS.items())[0]
            stories = fetcher._fetch_rss("TestSource", category, url)

            assert len(stories) == 20


class TestTTSSynthesizer:
    """Test TTSSynthesizer class."""

    def test_synthesizer_requires_credentials(self):
        """Test that TTSSynthesizer raises error without credentials."""
        from src.tts.synthesizer import TTSSynthesizer

        with patch("src.tts.synthesizer.settings") as mock_settings:
            mock_settings.minimax_api_key = ""
            mock_settings.minimax_group_id = ""

            synthesizer = TTSSynthesizer()
            assert not synthesizer.use_minimax

    def test_synthesizer_uses_minimax_when_configured(self):
        """Test that TTSSynthesizer uses MiniMax when configured."""
        from src.tts.synthesizer import TTSSynthesizer

        with patch("src.tts.synthesizer.settings") as mock_settings:
            mock_settings.minimax_api_key = "test-key"
            mock_settings.minimax_group_id = "test-group"

            synthesizer = TTSSynthesizer()
            assert synthesizer.use_minimax
            assert "Bearer test-key" in synthesizer.headers["Authorization"]


class TestAudioAssembler:
    """Test AudioAssembler class."""

    def test_assemble_requires_audio_parts(self, tmp_path):
        """Test that assemble raises ValueError with no audio parts."""
        from src.audio.assembler import AudioAssembler

        assembler = AudioAssembler()
        with pytest.raises(ValueError, match="No audio parts"):
            assembler.assemble([], tmp_path / "output.mp3")


class TestEpisodePublisher:
    """Test EpisodePublisher class."""

    def test_publisher_local_mode_without_aws(self, tmp_path):
        """Test that publisher works in local mode without AWS."""
        from src.distribution.publisher import EpisodePublisher
        from src.editorial.models import PodcastScript, ScriptSegment

        with patch("src.distribution.publisher.settings") as mock_settings:
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_s3_bucket = ""
            mock_settings.pipeline_output_dir = str(tmp_path)

            publisher = EpisodePublisher()
            assert not publisher.use_aws

            script = PodcastScript(
                episode_title="Test Episode",
                episode_summary="A test",
                segments=[ScriptSegment(speaker="host", text="Hello", story_index=0)],
                story_urls=[],
            )

            episode_path = tmp_path / "test.mp3"
            episode_path.write_bytes(b"fake audio data")

            url = publisher.publish(episode_path, script)
            assert url.startswith(str(tmp_path))
