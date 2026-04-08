"""ScriptWriter — uses OpenAI GPT-4o or MiniMax LLM to select stories and write podcast scripts."""

import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..ingestion.models import NewsStory
from .models import PodcastScript, ScriptSegment

logger = logging.getLogger(__name__)

MINIMAX_LLM_BASE = "https://api.minimax.io/v1"
OPENAI_LLM_BASE = "https://api.openai.com/v1"

SYSTEM_PROMPT = (
    "Du är chefredaktör för en AI-driven nyhetspodcast. Din uppgift är att skapa ett engagerande podcastmanus.\n\n"
    "Podcasten täcker: svenska nyheter, internationella nyheter, tech och AI.\n"
    "Ton: professionell men tillgänglig, faktuell, lagom tempostark.\n"
    "Längd: ca 8-12 minuter total lyssning.\n"
    "Format: Dialogformat med två värdar — \"host\" och \"co_host\".\n\n"
    "Svara ALLTID med giltig JSON enligt det schema du ges."
)

SCRIPT_SCHEMA = (
    "{\n"
    '  "episode_title": "string",\n'
    '  "episode_summary": "string (2-3 meningar för show notes)",\n'
    '  "segments": [\n'
    '    {"speaker": "host|co_host", "text": "talad text", "story_index": 0}\n'
    "  ],\n"
    '  "story_urls": ["url1", "url2"]\n'
    "}"
)

ML_TAG_CLOSE = "</think>"
ML_TAG_OPEN = "<think>"


class ScriptWriter:
    def __init__(self):
        if settings.openai_api_key:
            self.api_key = settings.openai_api_key
            self.model = settings.openai_llm_model
            self.base_url = OPENAI_LLM_BASE
            self.provider = "openai"
        elif settings.minimax_api_key:
            self.api_key = settings.minimax_api_key
            self.model = "MiniMax-M2.7-highspeed"
            self.base_url = MINIMAX_LLM_BASE
            self.provider = "minimax"
        else:
            raise ValueError("No LLM API key configured (need OPENAI_API_KEY or MINIMAX_API_KEY)")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def generate_script(self, stories: list[NewsStory]) -> PodcastScript:
        top_stories = stories[: settings.max_stories_per_episode]
        stories_text = self._format_stories(top_stories)

        prompt = (
            f"Här är dagens nyheter:\n\n{stories_text}\n\n"
            "Välj de viktigaste och mest intressanta nyheterna och skriv ett podcastmanus.\n"
            f"Svara med JSON enligt detta schema:\n{SCRIPT_SCHEMA}"
        )
        logger.info("Generating script for %d stories using %s", len(top_stories), self.provider)

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
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        if ML_TAG_CLOSE in raw:
            raw = raw.split(ML_TAG_CLOSE)[-1].strip()
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