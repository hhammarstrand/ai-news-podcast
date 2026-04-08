"""TTSSynthesizer — converts script segments to audio via MiniMax TTS, ElevenLabs fallback, or gTTS emergency fallback."""

import logging
import os
from pathlib import Path

import httpx
from gtts import gTTS
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..editorial.models import ScriptSegment

logger = logging.getLogger(__name__)

MINIMAX_BASE = "https://api.minimax.io/v1"

MINIMAX_VOICES = {
    "host": "Swedish_male_1_v1",
    "co_host": "Swedish_female_1_v1",
}

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

ELEVENLABS_VOICES = {
    "host": "pNInz6obpgDQGcFmaJgB",
    "co_host": "pNInz6obpgDQGcFmaJgB",
}

LANG_MAP = {
    "host": "sv",
    "co_host": "sv",
}


class TTSSynthesizer:
    def __init__(self):
        self.use_minimax = bool(settings.minimax_api_key)
        self.use_elevenlabs = bool(settings.elevenlabs_api_key)
        if self.use_minimax:
            self.minimax_headers = {
                "Authorization": f"Bearer {settings.minimax_api_key}",
                "Content-Type": "application/json",
            }
            self.minimax_group_id = settings.minimax_group_id if settings.minimax_group_id else None
        if self.use_elevenlabs:
            self.elevenlabs_headers = {
                "xi-api-key": settings.elevenlabs_api_key,
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
        if self.use_minimax:
            try:
                self._synthesize_minimax(segment, output_path)
                return
            except Exception as e:
                logger.warning("MiniMax TTS failed: %s. Trying ElevenLabs fallback.", e)
        if self.use_elevenlabs:
            try:
                self._synthesize_elevenlabs(segment, output_path)
                return
            except Exception as e:
                logger.warning("ElevenLabs TTS failed: %s. Trying gTTS emergency fallback.", e)
        self._synthesize_gtts(segment, output_path)

    def _synthesize_gtts(self, segment: ScriptSegment, output_path: Path) -> None:
        lang = LANG_MAP.get(segment.speaker, "sv")
        tts = gTTS(text=segment.text, lang=lang, slow=False)
        tts.save(str(output_path))

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
                headers=self.minimax_headers,
                json=payload,
                params={"GroupId": self.minimax_group_id} if self.minimax_group_id else {},
            )
            resp.raise_for_status()
        data = resp.json()
        if "data" in data:
            if "audio_file" in data["data"]:
                audio_url = data["data"]["audio_file"]
                audio_resp = client.get(audio_url)
                audio_resp.raise_for_status()
                output_path.write_bytes(audio_resp.content)
            elif "audio" in data["data"]:
                audio_bytes = bytes.fromhex(data["data"]["audio"])
                output_path.write_bytes(audio_bytes)
            else:
                raise RuntimeError(f"MiniMax TTS failed: unexpected data format {data}")
        else:
            raise RuntimeError(f"MiniMax TTS failed: {data}")

    def _synthesize_elevenlabs(self, segment: ScriptSegment, output_path: Path) -> None:
        voice_id = ELEVENLABS_VOICES.get(segment.speaker, ELEVENLABS_VOICES["host"])
        url = f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}"
        payload = {
            "text": segment.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
            },
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                url,
                headers=self.elevenlabs_headers,
                json=payload,
            )
            resp.raise_for_status()
        output_path.write_bytes(resp.content)
