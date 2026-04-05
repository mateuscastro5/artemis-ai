from __future__ import annotations

import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from ..config import settings

logger = logging.getLogger(__name__)


class QdrantService:

    def __init__(self) -> None:
        api_key = settings.qdrant_api_key or None
        self._client = QdrantClient(url=settings.qdrant_url, api_key=api_key)
        self._collection = settings.qdrant_collection

    async def ensure_collection(self, vector_size: int = 384) -> None:
        collections = self._client.get_collections().collections
        exists = any(c.name == self._collection for c in collections)

        if not exists:
            logger.info(
                "Creating Qdrant collection '%s' with vector size %d",
                self._collection,
                vector_size,
            )
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Collection '%s' created.", self._collection)
        else:
            logger.info("Collection '%s' already exists.", self._collection)

    def search_similar(
        self,
        embedding: list[float],
        limit: int = 3,
        min_score: float = 0.5,
    ) -> list[ScoredPoint]:
        results = self._client.query_points(
            collection_name=self._collection,
            query=embedding,
            limit=limit,
            score_threshold=min_score,
            with_payload=True,
        )
        return results.points

    def upsert_example(
        self,
        point_id: str | None,
        embedding: list[float],
        payload: dict,
    ) -> str:
        if point_id is None:
            point_id = str(uuid.uuid4())

        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                ),
            ],
        )
        logger.info("Upserted point %s into collection '%s'", point_id, self._collection)
        return point_id

    def delete_example(self, point_id: str) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=[point_id],
        )
        logger.info("Deleted point %s from collection '%s'", point_id, self._collection)

    def get_collection_info(self) -> dict:
        info = self._client.get_collection(self._collection)
        return {
            "name": self._collection,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": info.status.value,
        }

    def scroll_all(self, limit: int = 100) -> list[dict]:
        result = self._client.scroll(
            collection_name=self._collection,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        points, _ = result
        return [
            {"id": str(p.id), "payload": p.payload}
            for p in points
        ]

    def is_connected(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()
