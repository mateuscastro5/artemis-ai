from __future__ import annotations

import logging
import time

from ..config import settings
from ..models.enums import ChangeType
from ..models.schemas import AnalyzePRRequest, AnalyzePRResponse, SimilarExample
from .embedding_service import EmbeddingService
from .llm_reader import LLMReaderService
from .llm_scorer import LLMScorerService
from .preprocessor import Preprocessor
from .qdrant_service import QdrantService

logger = logging.getLogger(__name__)


class RAGPipeline:

    def __init__(
        self,
        embedding_service: EmbeddingService,
        qdrant_service: QdrantService,
    ) -> None:
        self._embedding = embedding_service
        self._qdrant = qdrant_service
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
        embedding = self._embedding.embed(reader_output.summary)

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

        logger.info("Step 5: Scoring with LLM Scorer (RAG context: %d examples)...", len(scorer_examples))
        scorer_output = await self._scorer.score(
            summary=reader_output.summary,
            cleaned_diff=preprocessed.cleaned_diff,
            technologies=reader_output.technologies,
            change_type=reader_output.change_type.value,
            lines_added=preprocessed.metrics.lines_added,
            lines_removed=preprocessed.metrics.lines_removed,
            files_changed=preprocessed.metrics.files_changed,
            similar_examples=scorer_examples,
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
