from __future__ import annotations

import logging

import voyageai

from ..config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:

    def __init__(self) -> None:
        self._client: voyageai.AsyncClient | None = None
        self._model_name = settings.embedding_model
        self._dimension = settings.embedding_dim

    def initialize(self) -> None:
        if not settings.voyage_api_key:
            raise RuntimeError("VOYAGE_API_KEY is not configured.")
        self._client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        logger.info(
            "EmbeddingService initialized with Voyage model '%s' (dim=%d).",
            self._model_name,
            self._dimension,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_loaded(self) -> bool:
        return self._client is not None

    async def embed(self, text: str, input_type: str = "document") -> list[float]:
        if self._client is None:
            raise RuntimeError("EmbeddingService not initialized. Call initialize() first.")
        result = await self._client.embed(
            texts=[text],
            model=self._model_name,
            input_type=input_type,
        )
        return result.embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> list[list[float]]:
        if self._client is None:
            raise RuntimeError("EmbeddingService not initialized. Call initialize() first.")
        result = await self._client.embed(
            texts=texts,
            model=self._model_name,
            input_type=input_type,
        )
        return result.embeddings
