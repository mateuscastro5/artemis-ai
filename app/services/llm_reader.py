from __future__ import annotations

import json
import logging
import re

from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, before_sleep_log

from ..config import settings
from ..models.enums import ChangeType
from ..models.schemas import ReaderOutput

logger = logging.getLogger(__name__)

READER_PROMPT = """You are a senior software engineer analyzing a Pull Request.
Given this PR diff, produce a concise technical summary that captures:
1. What problem it solves or what feature it adds
2. What patterns/techniques are used (design patterns, algorithms, architectural decisions)
3. The nature of the changes (algorithmic, architectural, simple CRUD, UI, config, etc.)
4. Technologies and frameworks involved

PR Title: {title}
PR Description: {body}

File Summary:
{file_summaries}

Diff:
{cleaned_diff}

Respond ONLY with valid JSON (no markdown, no code fences):
{{
  "summary": "A concise technical summary (200-500 tokens)",
  "technologies": ["list", "of", "technologies"],
  "change_type": "one of: bugfix, feature, refactor, config, docs, test",
  "key_patterns": ["list", "of", "patterns", "or", "techniques"]
}}"""


class LLMReaderService:

    async def summarize(
        self,
        cleaned_diff: str,
        title: str,
        body: str,
        file_summaries: list[str],
    ) -> ReaderOutput:
        prompt = READER_PROMPT.format(
            title=title,
            body=body or "(no description)",
            file_summaries="\n".join(file_summaries) if file_summaries else "(none)",
            cleaned_diff=cleaned_diff[:15000],
        )
        return await self._call_openrouter(prompt)

    async def _call_openrouter(self, prompt: str) -> ReaderOutput:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.openrouter_api_key,
                )
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1024,
                )
                return self._parse_response(response.choices[0].message.content)

    def _parse_response(self, raw_text: str) -> ReaderOutput:
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

        change_type = data.get("change_type", "feature").lower()
        valid_types = {e.value for e in ChangeType}
        if change_type not in valid_types:
            change_type = "feature"

        return ReaderOutput(
            summary=data.get("summary", ""),
            technologies=data.get("technologies", []),
            change_type=ChangeType(change_type),
            key_patterns=data.get("key_patterns", []),
        )
