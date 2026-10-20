from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analysis, feedback, gold_set, health, insights
from .services.embedding_service import EmbeddingService
from .services.memory_service import MemoryService
from .services.qdrant_service import QdrantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedding_service = EmbeddingService()
    embedding_service.initialize()
    app.state.embedding_service = embedding_service

    qdrant_service = QdrantService()
    await qdrant_service.ensure_collection(vector_size=embedding_service.dimension)
    app.state.qdrant_service = qdrant_service

    memory_service = MemoryService()
    memory_service.initialize()
    app.state.memory_service = memory_service

    yield

    qdrant_service.close()


app = FastAPI(
    title="Artemis AI Analysis Service",
    description="Dual-LLM + RAG pipeline with per-developer temporal memory",
    version="0.2.0",
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
app.include_router(insights.router, prefix="/api/v1")
