from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from confluence.client import ConfluenceClient
from confluence.services.pages import sync_pages_from_confluence


class Command(BaseCommand):
    help = "Скачивает страницы Confluence и сохраняет извлеченный текст в БД."

    def add_arguments(self, parser):
        parser.add_argument(
            "--space-key",
            default="",
            help="Ключ пространства Confluence (обязательно).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=25,
            help="Размер пачки при чтении страниц из Confluence.",
        )
        parser.add_argument(
            "--start",
            type=int,
            default=0,
            help="Позиция первой страницы в выдаче Confluence.",
        )
        parser.add_argument(
            "--retries",
            type=int,
            default=2,
            help="Сколько раз повторять запрос пачки при временной ошибке.",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=0,
            help="Ограничить количество страниц для пробного запуска.",
        )

    def handle(self, *args, **options):
        try:
            cf = ConfluenceClient()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc

        space_key = (options["space_key"] or "").strip()
        if not space_key:
            raise CommandError(
                "Укажите ключ пространства: python manage.py sync_pages --space-key YOUR_SPACE"
            )
        batch_size = options["batch_size"]
        start = options["start"]
        retries = options["retries"]
        max_pages = options["max_pages"]

        self.stdout.write(
            f"Читаю страницы из Confluence space={space_key}, start={start}, batch={batch_size}..."
        )

        try:
            result = sync_pages_from_confluence(
                cf.api,
                base_url=settings.CONFLUENCE_BASE_URL,
                space_key=space_key,
                batch_size=batch_size,
                start=start,
                retries=retries,
                max_pages=max_pages,
                on_batch_progress=lambda n: self.stdout.write(
                    f"Обработано страниц: {n}"
                ),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(
                f"Не удалось синхронизировать страницы Confluence: {exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Синхронизация завершена. "
                f"Прочитано: {result.seen_count}, создано: {result.created_count}, "
                f"обновлено: {result.updated_count}, без текста: {result.skipped_empty_count}."
            )
        )
