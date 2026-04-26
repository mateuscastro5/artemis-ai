from __future__ import annotations

import json
import logging
import re

from openai import AsyncOpenAI
from tenacity import AsyncRetrying, before_sleep_log, stop_after_attempt, wait_exponential

from ..config import settings
from ..models.schemas import DeveloperInsightsResponse
from .memory_service import MemoryService

logger = logging.getLogger(__name__)

INSIGHTS_PROMPT = """You are an engineering coach analyzing a developer's PR history to write
performance insights for a Tech Lead dashboard.

You receive a list of memories about this developer's past PRs (technical summaries, scores, technologies).
Produce a concise, evidence-based JSON profile.

== DEVELOPER MEMORIES ==

{memories_block}

== INSTRUCTIONS ==

- Base every claim on the memories above. Do not invent technologies or behaviors not present.
- "summary" should be 2-3 sentences in third person, neutral tone.
- "strengths" and "growth_areas": 2-4 short bullet points each, specific and actionable.
- "dominant_technologies": list of techs that appear most often (max 5).
- "trend_narrative": 1-2 sentences interpreting the score trajectory (improving / stable / declining
  based on the past_score values you see).
- If the developer has very few memories (< 3), be honest: say there isn't enough data yet and keep
  arrays short.

Respond ONLY with valid JSON (no markdown, no code fences):
{{
  "summary": "...",
  "strengths": ["...", "..."],
  "growth_areas": ["...", "..."],
  "dominant_technologies": ["...", "..."],
  "trend_narrative": "..."
}}"""


class InsightsService:

    def __init__(self, memory_service: MemoryService) -> None:
        self._memory = memory_service

    async def generate(self, developer_id: str) -> DeveloperInsightsResponse:
        memories = await self._memory.get_all(developer_id)

        if not memories:
            return DeveloperInsightsResponse(
                developer_id=developer_id,
                summary="No analyses recorded yet for this developer. Run a few PR analyses to populate insights.",
                strengths=[],
                growth_areas=[],
                dominant_technologies=[],
                trend_narrative="Not enough data to determine a trend.",
                memory_count=0,
            )

        memories_block = _format_memories(memories)
        prompt = INSIGHTS_PROMPT.format(memories_block=memories_block)
        parsed = await self._call_llm(prompt)

        return DeveloperInsightsResponse(
            developer_id=developer_id,
            summary=parsed.get("summary", ""),
            strengths=_as_str_list(parsed.get("strengths", [])),
            growth_areas=_as_str_list(parsed.get("growth_areas", [])),
            dominant_technologies=_as_str_list(parsed.get("dominant_technologies", [])),
            trend_narrative=parsed.get("trend_narrative", ""),
            memory_count=len(memories),
        )

    async def _call_llm(self, prompt: str) -> dict:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.openrouter_api_key,
                )
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,
                )
                return _parse_json(response.choices[0].message.content)


def _format_memories(memories: list[dict]) -> str:
    lines = []
    for i, m in enumerate(memories, 1):
        text = (m.get("memory") or "").strip()
        if not text:
            continue
        meta = m.get("metadata") or {}
        score = meta.get("score")
        label = meta.get("difficulty_label") or "?"
        score_str = f"{score:.0f}" if isinstance(score, (int, float)) else "?"
        lines.append(f"{i}. [past_score={score_str}, label={label}] {text}")
    return "\n".join(lines) if lines else "(empty)"


def _parse_json(raw: str) -> dict:
    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Insights LLM returned invalid JSON: %s", e)
        return {}


def _as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]
