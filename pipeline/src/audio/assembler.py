"""AudioAssembler — concatenates TTS segments into a final episode MP3."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Silence gap between segments (milliseconds)
SEGMENT_SILENCE_MS = 600


class AudioAssembler:
    def assemble(
        self,
        segment_paths: list[Path],
        output_path: Path,
        intro_path: Path | None = None,
        outro_path: Path | None = None,
    ) -> Path:
        """Concatenate audio segments into a single MP3 episode."""
        all_parts: list[Path] = []
        if intro_path and intro_path.exists():
            all_parts.append(intro_path)
        all_parts.extend(segment_paths)
        if outro_path and outro_path.exists():
            all_parts.append(outro_path)

        if not all_parts:
            raise ValueError("No audio parts to assemble")

        # Build concat list file for ffmpeg
        concat_list = output_path.parent / "concat_list.txt"
        with concat_list.open("w") as f:
            for part in all_parts:
                f.write(f"file '{part.resolve()}'\n")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            "-ar", "44100",
            str(output_path),
        ]
        logger.info("Assembling episode: %s", output_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        concat_list.unlink(missing_ok=True)
        logger.info("Episode assembled: %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)
        return output_path
