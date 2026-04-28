from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from confluence.models import ConfluencePage, ConfluencePageChunk
from confluence.services import split_text_into_chunks


class Command(BaseCommand):
    help = "Разбивает сохраненный текст Confluence-страниц на чанки."

    def add_arguments(self, parser):
        parser.add_argument(
            "--space-key",
            default="",
            help="Обрабатывать только страницы указанного Confluence space.",
        )
        parser.add_argument(
            "--max-chars",
            type=int,
            default=1800,
            help="Максимальный размер одного чанка в символах.",
        )
        parser.add_argument(
            "--page-id",
            default="",
            help="Обработать только одну страницу по confluence_id.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Посчитать чанки без записи в БД.",
        )

    def handle(self, *args, **options):
        max_chars = options["max_chars"]
        if max_chars < 200:
            raise CommandError("--max-chars должен быть не меньше 200.")

        pages = ConfluencePage.objects.exclude(body_text="")
        if options["space_key"]:
            pages = pages.filter(space_key=options["space_key"])
        if options["page_id"]:
            pages = pages.filter(confluence_id=options["page_id"])

        page_count = pages.count()
        if page_count == 0:
            self.stdout.write(self.style.WARNING("Нет страниц с текстом для чанкинга."))
            return

        total_chunks = 0
        self.stdout.write(f"Разбиваю страниц: {page_count}, max_chars={max_chars}...")

        for index, page in enumerate(pages.iterator(chunk_size=100), start=1):
            chunks = split_text_into_chunks(page.body_text, max_chars=max_chars)
            total_chunks += len(chunks)

            if not options["dry_run"]:
                chunk_models = [
                    ConfluencePageChunk(
                        page=page,
                        position=chunk.position,
                        text=chunk.text,
                        text_hash=chunk.text_hash,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                    )
                    for chunk in chunks
                ]
                with transaction.atomic():
                    page.chunks.all().delete()
                    ConfluencePageChunk.objects.bulk_create(chunk_models, batch_size=500)

            if index % 100 == 0:
                self.stdout.write(f"Обработано страниц: {index}, чанков: {total_chunks}")

        mode = "Пробный расчет завершен" if options["dry_run"] else "Чанкинг завершен"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}. Страниц: {page_count}, чанков: {total_chunks}."
            )
        )
