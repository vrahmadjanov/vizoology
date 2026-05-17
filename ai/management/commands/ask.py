from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from ai.rag import RAGAnswer, answer_question
from ai.services.history import save_question_answer_history, sources_for_answer
from ai.validators import validate_min_score, validate_top_k


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
            help="Минимальный score лучшего фрагмента для вызова модели.",
        )

    def handle(self, *args, **options):
        top_k = options["top_k"]
        min_score = options["min_score"]
        try:
            validate_top_k(top_k)
            validate_min_score(min_score)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        try:
            rag_answer = answer_question(
                options["question"],
                top_k=top_k,
                min_score=min_score,
            )
        except Exception as exc:
            raise CommandError(f"Не удалось получить ответ: {exc}") from exc

        try:
            history = save_question_answer_history(
                rag_answer, top_k=top_k, min_score=min_score
            )
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
            for source in sources_for_answer(rag_answer):
                url = source.url or "без ссылки"
                self.stdout.write(
                    f"- {source.title}: {url} "
                    f"(chunk_id={source.chunk_id}, score={source.score:.4f})"
                )
