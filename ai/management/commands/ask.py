from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from django.conf import settings

from ai.models import QuestionAnswerHistory
from ai.rag import RAGAnswer, SourceSnippet, answer_question


class Command(BaseCommand):
    help = "Отвечает на вопрос по Confluence-документации через RAG."

    def add_arguments(self, parser):
        parser.add_argument("question", help="Вопрос к документации.")
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="Сколько ближайших фрагментов использовать как контекст.",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=settings.RAG_MIN_SCORE,
            help="Минимальный score лучшего фрагмента для вызова Gemini.",
        )

    def handle(self, *args, **options):
        top_k = options["top_k"]
        min_score = options["min_score"]
        if top_k < 1:
            raise CommandError("--top-k должен быть больше 0.")
        if not 0 <= min_score <= 1:
            raise CommandError("--min-score должен быть от 0 до 1.")

        try:
            rag_answer = answer_question(
                options["question"],
                top_k=top_k,
                min_score=min_score,
            )
        except Exception as exc:
            raise CommandError(f"Не удалось получить ответ: {exc}") from exc

        try:
            history = _save_history(rag_answer, top_k=top_k, min_score=min_score)
        except DatabaseError as exc:
            raise CommandError(
                "Ответ получен, но не удалось сохранить историю в БД. "
                "Проверьте, что для ai.QuestionAnswerHistory созданы и применены миграции."
            ) from exc

        self._write_answer(rag_answer, history_id=history.id)

    def _write_answer(self, rag_answer: RAGAnswer, *, history_id: int | None = None) -> None:
        structured_answer = rag_answer.structured_answer

        self.stdout.write(self.style.SUCCESS("Короткий ответ:"))
        self.stdout.write(structured_answer.short_answer)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Обоснование:"))
        self.stdout.write(structured_answer.reasoning_summary)

        if rag_answer.model:
            self.stdout.write("")
            self.stdout.write(f"Модель: {rag_answer.model}")

        if history_id:
            self.stdout.write(f"Запись истории: #{history_id}")

        if rag_answer.sources:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Источники:"))
            for source in _sources_for_answer(rag_answer):
                url = source.url or "без ссылки"
                self.stdout.write(
                    f"- {source.title}: {url} "
                    f"(chunk_id={source.chunk_id}, score={source.score:.4f})"
                )


def _save_history(
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


def _sources_for_answer(rag_answer: RAGAnswer) -> list[SourceSnippet]:
    source_numbers = set(rag_answer.structured_answer.source_numbers)
    if not source_numbers:
        return []

    used_sources = [
        source for source in rag_answer.sources
        if source.number in source_numbers
    ]
    return _unique_sources(used_sources or rag_answer.sources)


def _unique_sources(sources: list[SourceSnippet]) -> list[SourceSnippet]:
    unique = []
    seen = set()
    for source in sources:
        key = source.url or f"chunk:{source.chunk_id}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique
