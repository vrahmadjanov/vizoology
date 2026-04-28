from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from confluence.models import ConfluencePage
from confluence.services import (
    confluence_page_to_record,
    get_confluence_client,
    get_confluence_settings,
    iter_confluence_pages,
)


class Command(BaseCommand):
    help = "Скачивает страницы Confluence и сохраняет извлеченный текст в БД."

    def add_arguments(self, parser):
        parser.add_argument(
            "--space-key",
            default="",
            help="Ключ пространства Confluence. Если не указан, используется CONFLUENCE_SPACE_KEY.",
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
            connection_settings = get_confluence_settings(require_space_key=True)
            client = get_confluence_client()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc

        space_key = options["space_key"] or connection_settings.space_key
        batch_size = options["batch_size"]
        start = options["start"]
        retries = options["retries"]
        max_pages = options["max_pages"]

        if batch_size < 1:
            raise CommandError("--batch-size должен быть больше 0.")
        if start < 0:
            raise CommandError("--start не может быть отрицательным.")
        if retries < 0:
            raise CommandError("--retries не может быть отрицательным.")
        if max_pages < 0:
            raise CommandError("--max-pages не может быть отрицательным.")

        created_count = 0
        updated_count = 0
        skipped_empty_count = 0
        seen_count = 0

        self.stdout.write(
            f"Читаю страницы из Confluence space={space_key}, start={start}, batch={batch_size}..."
        )

        try:
            pages = iter_confluence_pages(
                client,
                space_key,
                batch_size=batch_size,
                start=start,
                max_pages=max_pages,
                retries=retries,
            )
            for page in pages:
                seen_count += 1

                record = confluence_page_to_record(page, connection_settings.base_url)
                if not record["body_text"]:
                    skipped_empty_count += 1

                defaults = {
                    key: value
                    for key, value in record.items()
                    if key != "confluence_id"
                }
                defaults["synced_at"] = timezone.now()

                with transaction.atomic():
                    _, created = ConfluencePage.objects.update_or_create(
                        confluence_id=record["confluence_id"],
                        defaults=defaults,
                    )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                if seen_count % batch_size == 0:
                    self.stdout.write(f"Обработано страниц: {seen_count}")
        except Exception as exc:
            raise CommandError(f"Не удалось синхронизировать страницы Confluence: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Синхронизация завершена. "
                f"Прочитано: {seen_count}, создано: {created_count}, "
                f"обновлено: {updated_count}, без текста: {skipped_empty_count}."
            )
        )
