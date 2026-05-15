from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings

from ai.client import GeminiClient, GeminiResponse
from ai.validators import validate_min_score, validate_top_k
from confluence.search import ConfluenceSearchResult, search_confluence_chunks


class TextGenerator(Protocol):
    def generate_text(self, prompt: str) -> GeminiResponse:
        ...


@dataclass(frozen=True)
class SourceSnippet:
    number: int
    title: str
    url: str
    chunk_id: int
    chunk_position: int
    score: float
    text: str

    def to_payload(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "chunk_id": self.chunk_id,
            "chunk_position": self.chunk_position,
            "score": self.score,
        }


@dataclass(frozen=True)
class StructuredAnswer:
    short_answer: str
    reasoning_summary: str
    source_numbers: list[int]


@dataclass(frozen=True)
class RAGAnswer:
    question: str
    structured_answer: StructuredAnswer
    sources: list[SourceSnippet]
    model: str

    @property
    def answer(self) -> str:
        return self.structured_answer.short_answer

    def sources_payload(self) -> list[dict]:
        return [source.to_payload() for source in self.sources]


def answer_question(
    question: str,
    *,
    top_k: int = 5,
    min_score: float | None = None,
    generator: TextGenerator | None = None,
) -> RAGAnswer:
    question = question.strip()
    if not question:
        raise ValueError("question не может быть пустым.")
    min_score = settings.RAG_MIN_SCORE if min_score is None else min_score
    validate_top_k(top_k)
    validate_min_score(min_score)

    results = search_confluence_chunks(question, top_k=top_k)
    sources = source_snippets_from_results(results)
    if not sources:
        return RAGAnswer(
            question=question,
            structured_answer=StructuredAnswer(
                short_answer="Не найдено релевантных фрагментов документации для ответа.",
                reasoning_summary="Поиск по векторной базе не вернул подходящий контекст.",
                source_numbers=[],
            ),
            sources=[],
            model="",
        )
    if not has_sufficient_relevance(sources, min_score=min_score):
        best_score = max(source.score for source in sources)
        return RAGAnswer(
            question=question,
            structured_answer=StructuredAnswer(
                short_answer="Не найдено достаточно данных в документации для ответа.",
                reasoning_summary=(
                    f"Лучший найденный фрагмент имеет score={best_score:.4f}, "
                    f"что ниже порога {min_score:.4f}."
                ),
                source_numbers=[],
            ),
            sources=sources,
            model="",
        )

    prompt = build_answer_prompt(question, sources)
    text_generator = generator or GeminiClient()
    response = text_generator.generate_text(prompt)

    return RAGAnswer(
        question=question,
        structured_answer=parse_structured_answer(response.text),
        sources=sources,
        model=response.model,
    )


def has_sufficient_relevance(
    sources: list[SourceSnippet],
    *,
    min_score: float,
) -> bool:
    if not sources:
        return False
    return max(source.score for source in sources) >= min_score


def source_snippets_from_results(
    results: list[ConfluenceSearchResult],
) -> list[SourceSnippet]:
    sources = []
    for number, result in enumerate(results, start=1):
        chunk = result.chunk
        sources.append(
            SourceSnippet(
                number=number,
                title=result.page_title,
                url=result.page_url,
                chunk_id=chunk.id,
                chunk_position=chunk.position,
                score=result.score,
                text=chunk.text,
            )
        )
    return sources


def build_answer_prompt(question: str, sources: list[SourceSnippet]) -> str:
    question = question.strip()
    if not question:
        raise ValueError("question не может быть пустым.")
    if not sources:
        raise ValueError("sources не может быть пустым.")

    context = "\n\n".join(_format_source(source) for source in sources)
    return f"""Ты отвечаешь на вопросы по документации Visiology из Confluence.

Жесткие правила:
- Отвечай только на основании фрагментов документации ниже.
- Если информации недостаточно, прямо скажи, чего не хватает.
- Не выдумывай факты, названия настроек, команды и ссылки.
- Не раскрывай скрытую цепочку рассуждений. Вместо этого дай короткое проверяемое обоснование по источникам.
- Отвечай на русском языке.

Формат ответа:
Верни только валидный JSON без markdown-блока и без дополнительного текста:
{{
  "short_answer": "<1-3 предложения>",
  "reasoning_summary": "<краткое проверяемое обоснование по источникам>",
  "source_numbers": [<номера источников, использованных в ответе>]
}}

Вопрос:
{question}

Фрагменты документации:
{context}
"""


def parse_structured_answer(raw_text: str) -> StructuredAnswer:
    data = json.loads(_strip_json_markdown(raw_text))
    if not isinstance(data, dict):
        raise ValueError("Gemini вернул JSON не в виде объекта.")

    short_answer = _required_string(data, "short_answer")
    reasoning_summary = _required_string(data, "reasoning_summary")
    source_numbers = data.get("source_numbers", [])
    if not isinstance(source_numbers, list):
        raise ValueError("Поле source_numbers должно быть списком.")

    clean_source_numbers = []
    for number in source_numbers:
        if isinstance(number, int) and number > 0:
            clean_source_numbers.append(number)

    return StructuredAnswer(
        short_answer=short_answer,
        reasoning_summary=reasoning_summary,
        source_numbers=clean_source_numbers,
    )


def _strip_json_markdown(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    return text


def _required_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Поле {key} должно быть непустой строкой.")
    return value.strip()


def _format_source(source: SourceSnippet) -> str:
    url = source.url or "без ссылки"
    return (
        f"Источник {source.number}: {source.title}\n"
        f"Ссылка: {url}\n"
        f"chunk_id: {source.chunk_id}, chunk_position: {source.chunk_position}, "
        f"score: {source.score:.4f}\n"
        f"{source.text.strip()}"
    )
