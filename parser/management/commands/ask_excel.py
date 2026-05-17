from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from parser.services.excel_cli import ask_excel_workbook_inplace


class Command(BaseCommand):
    help = (
        "Читает вопросы из колонки Excel, для каждой строки вызывает RAG и записывает "
        "ответ в ту же книгу (три колонки: ответ, источники, рассуждения), затем сохраняет файл."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "workbook",
            type=str,
            help="Путь к файлу .xlsx (результат пишется в этот же файл).",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default="",
            help="Имя листа; по умолчанию активный лист.",
        )
        parser.add_argument(
            "--questions-col",
            type=str,
            default="",
            help=(
                "Буква колонки с вопросами (например Q). "
                "Пусто — из PARSER_DEFAULT_QUESTION_COLUMN_LETTER в settings."
            ),
        )
        parser.add_argument(
            "--answers-start-col",
            type=str,
            default="",
            help=(
                "Буква первой колонки блока ответа (3 колонки подряд). "
                "Пусто — сразу справа от колонки вопросов."
            ),
        )
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
        parser.add_argument(
            "--no-history",
            action="store_true",
            help="Не сохранять записи в QuestionAnswerHistory.",
        )

    def handle(self, *args, **options):
        path = Path(options["workbook"]).expanduser().resolve()
        min_score = options["min_score"]

        questions_col = options["questions_col"].strip() or None
        answers_start = options["answers_start_col"].strip() or None
        sheet_name = options["sheet"].strip() or None

        try:
            stats = ask_excel_workbook_inplace(
                path,
                sheet_name=sheet_name,
                questions_col=questions_col,
                answers_start_col=answers_start,
                top_k=options["top_k"],
                min_score=min_score,
                save_history=not options["no_history"],
                warn_row=lambda msg: self.stderr.write(self.style.WARNING(msg)),
                info_row=lambda msg: self.stdout.write(msg),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except DatabaseError as exc:
            raise CommandError(
                "Не удалось сохранить историю в БД (миграции ai?). "
                f"Подробнее: {exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Сохранено в {path}: обработано вопросов {stats.processed}, "
                f"с ошибками {stats.errors}."
            )
        )
