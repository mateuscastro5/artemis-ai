from fastapi import APIRouter, Request

from ..models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    qdrant_service = request.app.state.qdrant_service
    embedding_service = request.app.state.embedding_service

    qdrant_connected = qdrant_service.is_connected()
    collection_count = 0
    if qdrant_connected:
        try:
            info = qdrant_service.get_collection_info()
            collection_count = info.get("points_count", 0)
        except Exception:
            pass

    return HealthResponse(
        status="ok" if qdrant_connected and embedding_service.is_loaded else "degraded",
        qdrant_connected=qdrant_connected,
        embedding_model_loaded=embedding_service.is_loaded,
        collection_count=collection_count,
    )
