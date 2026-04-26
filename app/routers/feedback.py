from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from ..config import settings
from ..models.enums import ExampleOrigin
from ..models.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if not settings.internal_api_key:
        return "no-auth"
    if api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> FeedbackResponse:

    embedding_service = request.app.state.embedding_service
    qdrant_service = request.app.state.qdrant_service

    try:
        embedding = await embedding_service.embed(body.technical_summary)

        payload = {
            "codigo_original": body.diff_snippet,
            "resumo_tecnico": body.technical_summary,
            "dificuldade_label": body.corrected_label.value,
            "dificuldade_score": body.corrected_score,
            "tecnologia": "",
            "tipo_mudanca": "",
            "origem": ExampleOrigin.USER_FEEDBACK.value,
            "data_insercao": datetime.utcnow().isoformat(),
            "pr_metadata": {
                "analysis_id": body.analysis_id,
                "pr_id": body.pr_id,
                "original_score": body.original_score,
                "corrected_by": body.corrected_by,
            },
        }

        point_id = qdrant_service.upsert_example(
            point_id=None,
            embedding=embedding,
            payload=payload,
        )

        return FeedbackResponse(
            success=True,
            qdrant_point_id=point_id,
            message=f"Feedback saved. Score corrected from {body.original_score} to {body.corrected_score}.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback processing failed: {e}") from e
