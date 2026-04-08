"""Tests for editorial scriptwriter."""

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.db.models import Article, StoryCluster
from src.editorial.scriptwriter import ScriptWriter
from src.editorial.models import ScriptSegment
from src.ingestion.deduplicator import (
    deduplicate,
    extract_keywords,
    make_topic_key,
    mark_episode_covered,
    persist,
)
from src.ingestion.models import NewsStory, NewsCategory


class TestDeduplicator:
    """Tests for news deduplication system."""

    @pytest.fixture
    def sample_story(self):
        return NewsStory(
            title="AI breakthrough announced",
            summary="A major AI research lab announced a significant breakthrough",
            url="https://example.com/ai-breakthrough",
            source="TestSource",
            category=NewsCategory.AI,
            published_at=datetime.now(tz=timezone.utc),
        )

    @pytest.fixture
    def followup_story(self, sample_story):
        return NewsStory(
            title="AI breakthrough: follow-up report",
            summary="Further details emerged about the AI breakthrough announced yesterday",
            url="https://example.com/ai-breakthrough-followup",
            source="TestSource",
            category=NewsCategory.AI,
            published_at=sample_story.published_at + timedelta(days=1),
        )

    def test_extract_keywords(self):
        text = "The quick brown fox jumps over the lazy dog"
        keywords = extract_keywords(text)
        assert "quick" in keywords
        assert "brown" in keywords
        assert "fox" in keywords
        assert "the" not in keywords
        assert "over" not in keywords

    def test_make_topic_key_same_article(self, sample_story):
        key1 = make_topic_key(sample_story)
        key2 = make_topic_key(sample_story)
        assert key1 == key2

    def test_make_topic_key_different_articles(self, sample_story):
        different_story = NewsStory(
            title="Weather forecast for Stockholm",
            summary="It will be sunny tomorrow",
            url="https://example.com/weather",
            source="TestSource",
            category=NewsCategory.SWEDEN,
            published_at=datetime.now(tz=timezone.utc),
        )
        key1 = make_topic_key(sample_story)
        key2 = make_topic_key(different_story)
        assert key1 != key2

    def test_deduplicate_empty_list(self):
        with patch("src.ingestion.deduplicator.get_db_session"):
            result = deduplicate([], MagicMock())
            assert result == []

    def test_deduplicate_new_story(self, sample_story):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = deduplicate([sample_story], mock_db)
        assert len(result) == 1
        assert result[0].url == sample_story.url

    def test_deduplicate_duplicate_url(self, sample_story):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            (sample_story.url,)
        ]

        result = deduplicate([sample_story], mock_db)
        assert len(result) == 0

    def test_deduplicate_cluster_covered_recently(self, sample_story):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        existing_cluster = MagicMock()
        existing_cluster.covered_in_episode = True
        existing_cluster.last_covered_at = datetime.now(tz=timezone.utc)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_cluster

        result = deduplicate([sample_story], mock_db)
        assert len(result) == 0

    def test_deduplicate_cluster_covered_old(self, sample_story):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        existing_cluster = MagicMock()
        existing_cluster.covered_in_episode = True
        existing_cluster.last_covered_at = datetime.now(tz=timezone.utc) - timedelta(days=10)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_cluster

        result = deduplicate([sample_story], mock_db)
        assert len(result) == 1

    def test_deduplicate_followup_with_new_info(self, sample_story):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        existing_cluster = MagicMock()
        existing_cluster.covered_in_episode = True
        existing_cluster.last_covered_at = datetime.now(tz=timezone.utc) - timedelta(days=1)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_cluster

        followup = NewsStory(
            title="AI breakthrough: follow-up report",
            summary="Further details emerged about the AI breakthrough",
            url="https://example.com/ai-followup",
            source="TestSource",
            category=NewsCategory.AI,
            published_at=datetime.now(tz=timezone.utc),
            full_text="A" * 300,
        )

        result = deduplicate([followup], mock_db)
        assert len(result) == 1


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
