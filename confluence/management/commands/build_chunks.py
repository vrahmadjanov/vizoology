from django.core.management.base import BaseCommand, CommandError

from confluence.services.chunks import build_chunks


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

        try:
            result = build_chunks(
                space_key=options["space_key"],
                page_id=options["page_id"],
                max_chars=max_chars,
                dry_run=options["dry_run"],
                on_start=lambda pc: self.stdout.write(
                    f"Разбиваю страниц: {pc}, max_chars={max_chars}..."
                ),
                on_progress=lambda idx, tc: self.stdout.write(
                    f"Обработано страниц: {idx}, чанков: {tc}"
                ),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if result is None:
            self.stdout.write(self.style.WARNING("Нет страниц с текстом для чанкинга."))
            return

        mode = "Пробный расчет завершен" if options["dry_run"] else "Чанкинг завершен"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}. Страниц: {result.page_count}, чанков: {result.total_chunks}."
            )
        )
