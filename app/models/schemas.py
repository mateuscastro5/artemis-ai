from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from .enums import AnalysisStatus, ChangeType, DifficultyLabel, ExampleOrigin


# --- Analysis ---


class AnalyzePRRequest(BaseModel):
    pr_id: str
    title: str
    body: str = ""
    diff: str
    author: str
    repo_full_name: str
    pr_number: int
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    developer_id: str | None = None


class SimilarExample(BaseModel):
    score: float
    label: DifficultyLabel
    summary: str
    similarity: float


class AnalyzePRResponse(BaseModel):
    analysis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    score: float
    confidence: float
    difficulty_label: DifficultyLabel
    justification: str
    technical_summary: str
    technologies: list[str]
    change_type: ChangeType
    similar_examples: list[SimilarExample]
    requires_review: bool
    processing_time_ms: int


# --- LLM Reader Output ---


class ReaderOutput(BaseModel):
    summary: str
    technologies: list[str]
    change_type: ChangeType
    key_patterns: list[str]


# --- LLM Scorer Output ---


class ScorerOutput(BaseModel):
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    justification: str
    difficulty_label: DifficultyLabel


# --- Feedback ---


class FeedbackRequest(BaseModel):
    analysis_id: str
    pr_id: str
    original_score: float
    corrected_score: float = Field(ge=0, le=100)
    corrected_label: DifficultyLabel
    corrected_by: str
    technical_summary: str
    diff_snippet: str = ""


class FeedbackResponse(BaseModel):
    success: bool
    qdrant_point_id: str
    message: str


# --- Gold Set ---


class GoldSetCreateRequest(BaseModel):
    code_snippet: str
    difficulty_score: float = Field(ge=0, le=100)
    difficulty_label: DifficultyLabel
    technology: str
    change_type: ChangeType
    description: str


class GoldSetItem(BaseModel):
    id: str
    code_snippet: str
    difficulty_score: float
    difficulty_label: DifficultyLabel
    technology: str
    change_type: ChangeType
    description: str
    origin: ExampleOrigin
    created_at: str


class GoldSetListResponse(BaseModel):
    items: list[GoldSetItem]
    total: int


# --- Preprocessor Output ---


class DiffMetrics(BaseModel):
    files_changed: int
    lines_added: int
    lines_removed: int
    languages_detected: list[str]


class PreprocessedDiff(BaseModel):
    cleaned_diff: str
    metrics: DiffMetrics
    file_summaries: list[str]


# --- Health ---


class HealthResponse(BaseModel):
    status: str = "ok"
    qdrant_connected: bool
    embedding_model_loaded: bool
    collection_count: int = 0


# --- Insights ---


class DeveloperInsightsResponse(BaseModel):
    developer_id: str
    summary: str
    strengths: list[str]
    growth_areas: list[str]
    dominant_technologies: list[str]
    trend_narrative: str
    memory_count: int


class MemoryDeleteResponse(BaseModel):
    developer_id: str
    deleted_count: int


# --- Qdrant Payload ---


class QdrantPayload(BaseModel):
    codigo_original: str
    resumo_tecnico: str
    dificuldade_label: DifficultyLabel
    dificuldade_score: float
    tecnologia: str
    tipo_mudanca: ChangeType
    origem: ExampleOrigin
    data_insercao: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    pr_metadata: dict | None = None
