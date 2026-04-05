from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analysis, feedback, gold_set, health
from .services.embedding_service import EmbeddingService
from .services.qdrant_service import QdrantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedding_service = EmbeddingService()
    embedding_service.load_model()
    app.state.embedding_service = embedding_service

    qdrant_service = QdrantService()
    await qdrant_service.ensure_collection()
    app.state.qdrant_service = qdrant_service

    yield

    qdrant_service.close()


app = FastAPI(
    title="PERFORM AI Analysis Service",
    description="Dual-LLM + RAG pipeline for PR complexity scoring",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(gold_set.router, prefix="/api/v1")
