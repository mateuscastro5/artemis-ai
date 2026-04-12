from __future__ import annotations

import json
import logging
import re

from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, before_sleep_log

from ..config import settings
from ..models.enums import DifficultyLabel
from ..models.schemas import ScorerOutput

logger = logging.getLogger(__name__)

SCORER_PROMPT = """You are an expert code reviewer scoring Pull Request complexity on a 0-100 scale.

Consider these factors when scoring:
- Algorithmic complexity (simple CRUD vs complex algorithms)
- Architectural impact (isolated change vs cross-cutting concerns)
- Domain knowledge required (generic code vs domain-specific logic)
- Risk level (safe refactor vs critical path changes)
- Number and variety of files changed
- Patterns and techniques used

Scale reference:
- 0-20 (trivial): Config changes, typo fixes, simple formatting
- 21-40 (easy): Simple CRUD, basic UI changes, straightforward bug fixes
- 41-60 (medium): Feature implementation, moderate refactoring, API changes
- 61-80 (hard): Complex features, architectural changes, performance optimization
- 81-100 (expert): System design changes, complex algorithms, critical infrastructure

== PR TO SCORE ==

Technical Summary: {summary}
Technologies: {technologies}
Change Type: {change_type}
Stats: {lines_added} lines added, {lines_removed} removed, {files_changed} files changed

Diff (excerpt):
{cleaned_diff}

== REFERENCE EXAMPLES FOR CALIBRATION ==

{examples_block}

== INSTRUCTIONS ==

Based on the reference examples above (if any), calibrate your score for this PR.
If no reference examples are provided, score based on your expert judgment alone.

Respond ONLY with valid JSON (no markdown, no code fences):
{{
  "score": <number 0-100>,
  "confidence": <number 0.0-1.0>,
  "justification": "Brief explanation of the score",
  "difficulty_label": "one of: trivial, easy, medium, hard, expert"
}}"""


def _build_examples_block(similar_examples: list[dict]) -> str:
    if not similar_examples:
        return "No reference examples available. Score based on your expert judgment."

    parts = []
    for i, ex in enumerate(similar_examples, 1):
        payload = ex.get("payload", {})
        parts.append(
            f"Example {i}:\n"
            f"  Score: {payload.get('dificuldade_score', '?')}/100 "
            f"({payload.get('dificuldade_label', '?')})\n"
            f"  Summary: {payload.get('resumo_tecnico', 'N/A')}\n"
            f"  Technology: {payload.get('tecnologia', 'N/A')}\n"
            f"  Similarity: {ex.get('similarity', 0):.2f}"
        )
    return "\n\n".join(parts)


class LLMScorerService:

    async def score(
        self,
        summary: str,
        cleaned_diff: str,
        technologies: list[str],
        change_type: str,
        lines_added: int,
        lines_removed: int,
        files_changed: int,
        similar_examples: list[dict],
    ) -> ScorerOutput:
        examples_block = _build_examples_block(similar_examples)

        prompt = SCORER_PROMPT.format(
            summary=summary,
            technologies=", ".join(technologies) if technologies else "N/A",
            change_type=change_type,
            lines_added=lines_added,
            lines_removed=lines_removed,
            files_changed=files_changed,
            cleaned_diff=cleaned_diff[:10000],
            examples_block=examples_block,
        )

        try:
            return await self._call_gemini(prompt)
        except Exception as e:
            logger.warning("Gemini Scorer failed, trying local Ollama fallback: %s", e)
            return await self._call_ollama(prompt)

    async def _call_gemini(self, prompt: str) -> ScorerOutput:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                from google import genai

                client = genai.Client(api_key=settings.gemini_api_key)
                response = client.models.generate_content(
                    model=settings.llm_scorer_model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=1024,
                    ),
                )
                return self._parse_response(response.text)

    async def _call_ollama(self, prompt: str) -> ScorerOutput:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(
                    base_url=f"{settings.ollama_url}/v1",
                    api_key="ollama",  # required by client but not used by Ollama
                )
                response = await client.chat.completions.create(
                    model=settings.llm_local_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=1024,
                )
                return self._parse_response(response.choices[0].message.content)

    def _parse_response(self, raw_text: str) -> ScorerOutput:
        text = raw_text.strip()

        # Try to extract JSON from a code fence first
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1)
        else:
            # Fall back to finding the first {...} block in the response
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                text = json_match.group(0)

        data = json.loads(text)

        score = max(0, min(100, float(data.get("score", 50))))
        confidence = max(0, min(1, float(data.get("confidence", 0.5))))

        label = data.get("difficulty_label", "medium").lower()
        valid_labels = {e.value for e in DifficultyLabel}
        if label not in valid_labels:
            if score <= 20:
                label = "trivial"
            elif score <= 40:
                label = "easy"
            elif score <= 60:
                label = "medium"
            elif score <= 80:
                label = "hard"
            else:
                label = "expert"

        return ScorerOutput(
            score=score,
            confidence=confidence,
            justification=data.get("justification", ""),
            difficulty_label=DifficultyLabel(label),
        )
