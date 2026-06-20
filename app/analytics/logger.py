from __future__ import annotations

import time
from dataclasses import dataclass

from app.analytics.categories import (
    categorize_question,
    detect_answer_found,
    estimate_tokens,
    extract_primary_module,
)
from app.analytics.repository import QueryLogRepository


@dataclass(frozen=True)
class RequestMetrics:
    response_time: float
    tokens_input: int
    tokens_output: int
    question_category: str
    sources_count: int
    answer_found: bool
    module: str | None


class RequestLogger:
    def __init__(self, repository: QueryLogRepository | None = None) -> None:
        self.repository = repository or QueryLogRepository()

    def build_metrics(
        self,
        *,
        question: str,
        answer: str,
        response_time: float,
        response_type: str,
        retrieved_documents,
        prompt_text: str = "",
    ) -> RequestMetrics:
        sources_count = len(retrieved_documents) if retrieved_documents else 0
        tokens_input = estimate_tokens(prompt_text or question)
        tokens_output = estimate_tokens(answer)

        return RequestMetrics(
            response_time=response_time,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            question_category=categorize_question(question),
            sources_count=sources_count,
            answer_found=detect_answer_found(answer, sources_count, response_type),
            module=extract_primary_module(retrieved_documents),
        )

    def log(
        self,
        *,
        user_id: int,
        question: str,
        answer: str,
        metrics: RequestMetrics,
        response_type: str,
    ) -> int:
        return self.repository.log_query(
            user_id=user_id,
            question=question,
            answer=answer,
            question_category=metrics.question_category,
            response_time=metrics.response_time,
            tokens_input=metrics.tokens_input,
            tokens_output=metrics.tokens_output,
            sources_count=metrics.sources_count,
            answer_found=metrics.answer_found,
            module=metrics.module,
            response_type=response_type,
        )


class Timer:
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self._start
