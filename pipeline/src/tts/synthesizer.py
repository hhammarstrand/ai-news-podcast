"""TTSSynthesizer — converts script segments to audio via MiniMax TTS."""

import logging
import os
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..editorial.models import ScriptSegment

logger = logging.getLogger(__name__)

MINIMAX_BASE = "https://api.minimax.io/v1"

MINIMAX_VOICES = {
    "host": "Swedish_male_1_v1",
    "co_host": "Swedish_female_1_v1",
}


class TTSSynthesizer:
    def __init__(self):
        self.use_minimax = bool(settings.minimax_api_key and settings.minimax_group_id)
        if self.use_minimax:
            self.headers = {
                "Authorization": f"Bearer {settings.minimax_api_key}",
                "Content-Type": "application/json",
            }
            self.group_id = settings.minimax_group_id

    def synthesize_segments(
        self, segments: list[ScriptSegment], output_dir: Path
    ) -> list[Path]:
        """Synthesize all segments and return list of audio file paths in order."""
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_paths = []
        for i, segment in enumerate(segments):
            path = output_dir / f"segment_{i:03d}_{segment.speaker}.mp3"
            self._synthesize_segment(segment, path)
            audio_paths.append(path)
            logger.info("Synthesized segment %d/%d", i + 1, len(segments))
        return audio_paths

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _synthesize_segment(self, segment: ScriptSegment, output_path: Path) -> None:
        if self.use_minimax:
            self._synthesize_minimax(segment, output_path)
        else:
            raise RuntimeError("No TTS provider configured. Set MINIMAX_API_KEY and MINIMAX_GROUP_ID or ELEVENLABS_API_KEY")

    def _synthesize_minimax(self, segment: ScriptSegment, output_path: Path) -> None:
        voice = MINIMAX_VOICES.get(segment.speaker, MINIMAX_VOICES["host"])
        url = f"{MINIMAX_BASE}/t2a_v2"
        payload = {
            "model": "speech-2.8-hd",
            "text": segment.text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
            },
            "audio_setting": {
                "sample_rate": 44100,
                "bitrate": 256000,
                "format": "mp3",
            },
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                url,
                headers=self.headers,
                json=payload,
                params={"GroupId": self.group_id},
            )
            resp.raise_for_status()
        data = resp.json()
        if "data" in data and "audio_file" in data["data"]:
            audio_url = data["data"]["audio_file"]
            audio_resp = client.get(audio_url)
            audio_resp.raise_for_status()
            output_path.write_bytes(audio_resp.content)
        else:
            raise RuntimeError(f"MiniMax TTS failed: {data}")
