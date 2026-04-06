"""ScriptWriter — uses MiniMax LLM to select stories and write podcast scripts."""

import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..ingestion.models import NewsStory
from .models import PodcastScript, ScriptSegment

logger = logging.getLogger(__name__)

MINIMAX_LLM_BASE = "https://api.minimax.io/v1"

SYSTEM_PROMPT = """\
Du är chefredaktör för en AI-driven nyhetspodcast. Din uppgift är att skapa ett engagerande podcastmanus.

Podcasten täcker: svenska nyheter, internationella nyheter, tech och AI.
Ton: professionell men tillgänglig, faktuell, lagom tempostark.
Längd: ca 8-12 minuter total lyssning.
Format: Dialogformat med två värdar — "host" och "co_host".

Svara ALLTID med giltig JSON enligt det schema du ges.
"""

SCRIPT_SCHEMA = """\
{
  "episode_title": "string",
  "episode_summary": "string (2-3 meningar för show notes)",
  "segments": [
    {"speaker": "host|co_host", "text": "talad text", "story_index": 0}
  ],
  "story_urls": ["url1", "url2"]
}
"""


class ScriptWriter:
    def __init__(self):
        self.api_key = settings.minimax_api_key
        self.group_id = settings.minimax_group_id
        self.model = settings.minimax_llm_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def generate_script(self, stories: list[NewsStory]) -> PodcastScript:
        top_stories = stories[: settings.max_stories_per_episode]
        stories_text = self._format_stories(top_stories)

        prompt = f"""\
Här är dagens nyheter:

{stories_text}

Välj de viktigaste och mest intressanta nyheterna och skriv ett podcastmanus.
Svara med JSON enligt detta schema:
{SCRIPT_SCHEMA}
"""
        logger.info("Generating script for %d stories", len(top_stories))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.7,
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{MINIMAX_LLM_BASE}/chat/completions",
                headers=headers,
                json=payload,
                params={"GroupId": self.group_id} if self.group_id else {},
            )
            resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse script JSON: %s\nRaw response: %s", e, raw[:500])
            raise ValueError(f"ScriptWriter returned invalid JSON: {e}") from e
        return PodcastScript(
            episode_title=data["episode_title"],
            episode_summary=data["episode_summary"],
            segments=[ScriptSegment(**s) for s in data["segments"]],
            story_urls=data.get("story_urls", [s.url for s in top_stories]),
        )

    def _format_stories(self, stories: list[NewsStory]) -> str:
        lines = []
        for i, s in enumerate(stories):
            lines.append(
                f"[{i}] [{s.category.value.upper()}] {s.source}\n"
                f"Titel: {s.title}\n"
                f"Sammanfattning: {s.summary}\n"
                f"URL: {s.url}\n"
            )
        return "\n".join(lines)
