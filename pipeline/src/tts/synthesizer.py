"""TTSSynthesizer — converts script segments to audio via ElevenLabs."""

import logging
import os
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..editorial.models import ScriptSegment

logger = logging.getLogger(__name__)

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

# Voice IDs — configure these to your preferred ElevenLabs voices
VOICES = {
    "host": settings.elevenlabs_voice_id_host,
    "co_host": "EXAVITQu4vr4xnSDxMaL",  # Bella voice as co-host
}


class TTSSynthesizer:
    def __init__(self):
        self.headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        }

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
        voice_id = VOICES.get(segment.speaker, VOICES["host"])
        url = f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}"
        payload = {
            "text": segment.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
        output_path.write_bytes(resp.content)
