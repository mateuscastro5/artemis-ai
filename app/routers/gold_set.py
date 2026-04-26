from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from ..config import settings
from ..models.enums import ExampleOrigin
from ..models.schemas import GoldSetCreateRequest, GoldSetItem, GoldSetListResponse

router = APIRouter(tags=["gold-set"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if not settings.internal_api_key:
        return "no-auth"
    if api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


@router.post("/gold-set", response_model=GoldSetItem)
async def create_gold_set_example(
    body: GoldSetCreateRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> GoldSetItem:

    embedding_service = request.app.state.embedding_service
    qdrant_service = request.app.state.qdrant_service

    try:
        embedding = await embedding_service.embed(body.description)

        now = datetime.utcnow().isoformat()
        payload = {
            "codigo_original": body.code_snippet,
            "resumo_tecnico": body.description,
            "dificuldade_label": body.difficulty_label.value,
            "dificuldade_score": body.difficulty_score,
            "tecnologia": body.technology,
            "tipo_mudanca": body.change_type.value,
            "origem": ExampleOrigin.GOLD_SET.value,
            "data_insercao": now,
            "pr_metadata": None,
        }

        point_id = qdrant_service.upsert_example(
            point_id=None,
            embedding=embedding,
            payload=payload,
        )

        return GoldSetItem(
            id=point_id,
            code_snippet=body.code_snippet,
            difficulty_score=body.difficulty_score,
            difficulty_label=body.difficulty_label,
            technology=body.technology,
            change_type=body.change_type,
            description=body.description,
            origin=ExampleOrigin.GOLD_SET,
            created_at=now,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create gold set example: {e}") from e


@router.get("/gold-set", response_model=GoldSetListResponse)
async def list_gold_set(
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> GoldSetListResponse:
    qdrant_service = request.app.state.qdrant_service

    try:
        all_points = qdrant_service.scroll_all(limit=500)
        items = []
        for point in all_points:
            p = point["payload"]
            items.append(
                GoldSetItem(
                    id=point["id"],
                    code_snippet=p.get("codigo_original", ""),
                    difficulty_score=p.get("dificuldade_score", 0),
                    difficulty_label=p.get("dificuldade_label", "medium"),
                    technology=p.get("tecnologia", ""),
                    change_type=p.get("tipo_mudanca", "feature"),
                    description=p.get("resumo_tecnico", ""),
                    origin=p.get("origem", "gold_set"),
                    created_at=p.get("data_insercao", ""),
                )
            )
        return GoldSetListResponse(items=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list gold set: {e}") from e


@router.delete("/gold-set/{point_id}")
async def delete_gold_set_example(
    point_id: str,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> dict:
    qdrant_service = request.app.state.qdrant_service

    try:
        qdrant_service.delete_example(point_id)
        return {"success": True, "message": f"Deleted example {point_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete example: {e}") from e
