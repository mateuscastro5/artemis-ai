from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from ..config import settings
from ..models.schemas import DeveloperInsightsResponse, MemoryDeleteResponse
from ..services.insights_service import InsightsService

router = APIRouter(tags=["insights"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if not settings.internal_api_key:
        return "no-auth"
    if api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


@router.post("/insights/{developer_id}", response_model=DeveloperInsightsResponse)
async def generate_insights(
    developer_id: str,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> DeveloperInsightsResponse:
    memory_service = request.app.state.memory_service
    if not memory_service.is_enabled:
        raise HTTPException(status_code=503, detail="Memory service is not configured.")

    service = InsightsService(memory_service)
    try:
        return await service.generate(developer_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insights generation failed: {e}") from e


@router.delete("/memory/{developer_id}", response_model=MemoryDeleteResponse)
async def clear_developer_memory(
    developer_id: str,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> MemoryDeleteResponse:
    memory_service = request.app.state.memory_service
    if not memory_service.is_enabled:
        raise HTTPException(status_code=503, detail="Memory service is not configured.")

    try:
        deleted = await memory_service.delete_all(developer_id)
        return MemoryDeleteResponse(developer_id=developer_id, deleted_count=deleted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear memory: {e}") from e
