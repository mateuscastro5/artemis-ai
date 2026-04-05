from __future__ import annotations

import logging

from ..config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:

    def __init__(self) -> None:
        self._model = None
        self._model_name = settings.embedding_model

    def load_model(self) -> None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", self._model_name)
        self._model = SentenceTransformer(self._model_name)
        logger.info(
            "Embedding model loaded. Dimension: %d",
            self._model.get_sentence_embedding_dimension(),
        )

    @property
    def dimension(self) -> int:
        if self._model is None:
            raise RuntimeError("Embedding model not loaded. Call load_model() first.")
        return self._model.get_sentence_embedding_dimension()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def embed(self, text: str) -> list[float]:
        if self._model is None:
            raise RuntimeError("Embedding model not loaded. Call load_model() first.")
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            raise RuntimeError("Embedding model not loaded. Call load_model() first.")
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
