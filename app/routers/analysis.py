from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from ..config import settings
from ..models.schemas import AnalyzePRRequest, AnalyzePRResponse
from ..services.rag_pipeline import RAGPipeline

router = APIRouter(tags=["analysis"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if not settings.internal_api_key:
        return "no-auth"
    if api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def get_pipeline(request: Request) -> RAGPipeline:
    return RAGPipeline(
        embedding_service=request.app.state.embedding_service,
        qdrant_service=request.app.state.qdrant_service,
    )


@router.post("/analyze-pr", response_model=AnalyzePRResponse)
async def analyze_pr(
    body: AnalyzePRRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
    _api_key: str = Depends(verify_api_key),
) -> AnalyzePRResponse:

    try:
        return await pipeline.analyze_pr(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") from e
