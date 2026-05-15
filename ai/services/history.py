from __future__ import annotations

from ai.models import QuestionAnswerHistory
from ai.rag import RAGAnswer, SourceSnippet


def save_question_answer_history(
    rag_answer: RAGAnswer,
    *,
    top_k: int,
    min_score: float,
) -> QuestionAnswerHistory:
    structured_answer = rag_answer.structured_answer
    return QuestionAnswerHistory.objects.create(
        question=rag_answer.question,
        short_answer=structured_answer.short_answer,
        reasoning_summary=structured_answer.reasoning_summary,
        source_numbers=structured_answer.source_numbers,
        sources=rag_answer.sources_payload(),
        model_name=rag_answer.model,
        top_k=top_k,
        min_score=min_score,
    )


def sources_for_answer(rag_answer: RAGAnswer) -> list[SourceSnippet]:
    source_numbers = set(rag_answer.structured_answer.source_numbers)
    if not source_numbers:
        return []

    used_sources = [
        source for source in rag_answer.sources if source.number in source_numbers
    ]
    return unique_sources(used_sources or rag_answer.sources)


def unique_sources(sources: list[SourceSnippet]) -> list[SourceSnippet]:
    unique: list[SourceSnippet] = []
    seen: set[str] = set()
    for source in sources:
        key = source.url or f"chunk:{source.chunk_id}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique
