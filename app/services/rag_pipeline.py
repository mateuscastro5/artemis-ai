from __future__ import annotations

import asyncio
import logging
import time

from ..config import settings
from ..models.enums import ChangeType
from ..models.schemas import AnalyzePRRequest, AnalyzePRResponse, SimilarExample
from .embedding_service import EmbeddingService
from .llm_reader import LLMReaderService
from .llm_scorer import LLMScorerService
from .memory_service import MemoryService
from .preprocessor import Preprocessor
from .qdrant_service import QdrantService

logger = logging.getLogger(__name__)


class RAGPipeline:

    def __init__(
        self,
        embedding_service: EmbeddingService,
        qdrant_service: QdrantService,
        memory_service: MemoryService,
    ) -> None:
        self._embedding = embedding_service
        self._qdrant = qdrant_service
        self._memory = memory_service
        self._preprocessor = Preprocessor()
        self._reader = LLMReaderService()
        self._scorer = LLMScorerService()

    async def analyze_pr(self, request: AnalyzePRRequest) -> AnalyzePRResponse:

        start_time = time.time()

        logger.info("Analyzing PR %s from %s", request.pr_number, request.repo_full_name)
        preprocessed = self._preprocessor.clean_diff(
            request.diff,
            max_lines=settings.max_diff_lines,
        )

        if not preprocessed.cleaned_diff.strip():
            logger.warning("PR %s has no meaningful diff content after preprocessing", request.pr_number)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return AnalyzePRResponse(
                score=0,
                confidence=0.9,
                difficulty_label="trivial",
                justification="No meaningful code changes detected after filtering noise files.",
                technical_summary="Empty or noise-only diff.",
                technologies=[],
                change_type=ChangeType.CONFIG,
                similar_examples=[],
                requires_review=False,
                processing_time_ms=elapsed_ms,
            )

        logger.info("Step 2: Summarizing with LLM Reader...")
        reader_output = await self._reader.summarize(
            cleaned_diff=preprocessed.cleaned_diff,
            title=request.title,
            body=request.body,
            file_summaries=preprocessed.file_summaries,
        )

        logger.info("Step 3: Generating embedding...")
        embedding = await self._embedding.embed(reader_output.summary)

        logger.info("Step 4: Searching Qdrant for similar examples...")
        raw_results = self._qdrant.search_similar(embedding, limit=3, min_score=0.4)

        similar_examples = [
            SimilarExample(
                score=r.payload.get("dificuldade_score", 50),
                label=r.payload.get("dificuldade_label", "medium"),
                summary=r.payload.get("resumo_tecnico", ""),
                similarity=r.score,
            )
            for r in raw_results
        ]

        scorer_examples = [
            {
                "payload": r.payload,
                "similarity": r.score,
            }
            for r in raw_results
        ]

        developer_context = ""
        if request.developer_id and self._memory.is_enabled:
            logger.info("Step 4b: Loading developer memory for %s...", request.developer_id)
            memories = await self._memory.search(
                developer_id=request.developer_id,
                query=reader_output.summary,
                limit=5,
            )
            developer_context = _format_developer_context(memories)

        logger.info(
            "Step 5: Scoring with LLM Scorer (RAG: %d examples, memory: %s)...",
            len(scorer_examples),
            "yes" if developer_context else "no",
        )
        scorer_output = await self._scorer.score(
            summary=reader_output.summary,
            cleaned_diff=preprocessed.cleaned_diff,
            technologies=reader_output.technologies,
            change_type=reader_output.change_type.value,
            lines_added=preprocessed.metrics.lines_added,
            lines_removed=preprocessed.metrics.lines_removed,
            files_changed=preprocessed.metrics.files_changed,
            similar_examples=scorer_examples,
            developer_context=developer_context,
        )

        if request.developer_id and self._memory.is_enabled:
            asyncio.create_task(
                self._memory.add_analysis(
                    developer_id=request.developer_id,
                    technical_summary=reader_output.summary,
                    score=scorer_output.score,
                    difficulty_label=scorer_output.difficulty_label.value,
                    technologies=reader_output.technologies,
                    change_type=reader_output.change_type.value,
                    pr_number=request.pr_number,
                    repo=request.repo_full_name,
                )
            )

        elapsed_ms = int((time.time() - start_time) * 1000)
        requires_review = scorer_output.confidence < settings.confidence_threshold

        logger.info(
            "Analysis complete for PR %s: score=%s, confidence=%s, requires_review=%s (%dms)",
            request.pr_number,
            scorer_output.score,
            scorer_output.confidence,
            requires_review,
            elapsed_ms,
        )

        return AnalyzePRResponse(
            score=scorer_output.score,
            confidence=scorer_output.confidence,
            difficulty_label=scorer_output.difficulty_label,
            justification=scorer_output.justification,
            technical_summary=reader_output.summary,
            technologies=reader_output.technologies,
            change_type=reader_output.change_type,
            similar_examples=similar_examples,
            requires_review=requires_review,
            processing_time_ms=elapsed_ms,
        )


def _format_developer_context(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = []
    for i, m in enumerate(memories, 1):
        text = (m.get("memory") or "").strip()
        if not text:
            continue
        meta = m.get("metadata") or {}
        score = meta.get("score")
        score_str = f" [past score: {score:.0f}]" if isinstance(score, (int, float)) else ""
        lines.append(f"{i}.{score_str} {text}")
    return "\n".join(lines) if lines else ""
