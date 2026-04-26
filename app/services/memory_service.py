from __future__ import annotations

import logging

from mem0 import AsyncMemoryClient

from ..config import settings

logger = logging.getLogger(__name__)


class MemoryService:

    def __init__(self) -> None:
        self._client: AsyncMemoryClient | None = None

    def initialize(self) -> None:
        if not settings.mem0_api_key:
            logger.warning("MEM0_API_KEY not configured. MemoryService will be disabled.")
            return
        self._client = AsyncMemoryClient(api_key=settings.mem0_api_key)
        logger.info("MemoryService initialized (mem0 Platform).")

    @property
    def is_enabled(self) -> bool:
        return self._client is not None

    async def add_analysis(
        self,
        developer_id: str,
        technical_summary: str,
        score: float,
        difficulty_label: str,
        technologies: list[str],
        change_type: str,
        pr_number: int,
        repo: str,
    ) -> None:
        if self._client is None:
            return

        text = (
            f"PR #{pr_number} in {repo} (score {score:.0f}/100, label '{difficulty_label}', "
            f"type '{change_type}', tech: {', '.join(technologies) or 'unspecified'}). "
            f"Summary: {technical_summary}"
        )

        try:
            await self._client.add(
                messages=[{"role": "user", "content": text}],
                user_id=developer_id,
                metadata={
                    "score": float(score),
                    "difficulty_label": difficulty_label,
                    "change_type": change_type,
                    "pr_number": pr_number,
                    "repo": repo,
                },
            )
            logger.info("Memory added for developer %s (PR #%s)", developer_id, pr_number)
        except Exception as e:
            logger.warning("Failed to add memory for developer %s: %s", developer_id, e)

    async def search(
        self,
        developer_id: str,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        if self._client is None:
            return []
        try:
            results = await self._client.search(
                query=query,
                filters={"user_id": developer_id},
                limit=limit,
            )
            return _normalize_results(results)
        except Exception as e:
            logger.warning("Memory search failed for developer %s: %s", developer_id, e)
            return []

    async def get_all(self, developer_id: str) -> list[dict]:
        if self._client is None:
            return []
        try:
            results = await self._client.get_all(
                filters={"user_id": developer_id},
            )
            return _normalize_results(results)
        except Exception as e:
            logger.warning("Memory get_all failed for developer %s: %s", developer_id, e)
            return []

    async def delete_all(self, developer_id: str) -> int:
        if self._client is None:
            return 0
        try:
            existing = await self.get_all(developer_id)
            await self._client.delete_all(filters={"user_id": developer_id})
            logger.info("Deleted %d memories for developer %s", len(existing), developer_id)
            return len(existing)
        except Exception as e:
            logger.warning("Failed to delete memories for developer %s: %s", developer_id, e)
            return 0


def _normalize_results(raw) -> list[dict]:
    if isinstance(raw, dict) and "results" in raw:
        items = raw["results"]
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "id": item.get("id"),
                "memory": item.get("memory") or item.get("text") or "",
                "score": item.get("score"),
                "metadata": item.get("metadata") or {},
            }
        )
    return out
