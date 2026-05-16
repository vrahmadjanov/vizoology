from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from confluence.services.embedding import embed_chunk_batches


class Command(BaseCommand):
    help = "Генерирует локальные embeddings для Confluence-чанков и сохраняет их в pgvector."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=settings.EMBEDDING_BATCH_SIZE,
            help="Сколько чанков векторизовать за один проход модели.",
        )
        parser.add_argument(
            "--max-chunks",
            type=int,
            default=0,
            help="Ограничить количество чанков для пробного запуска.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Перегенерировать все embeddings, даже если они актуальны.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        max_chunks = options["max_chunks"]
        force = options["force"]

        try:
            processed, total = embed_chunk_batches(
                batch_size=batch_size,
                max_chunks=max_chunks,
                force=force,
                on_start=lambda tot, svc: self.stdout.write(
                    f"Векторизую чанки: {tot}, model={svc.model_name}, batch={batch_size}..."
                ),
                on_batch_saved=lambda done, plan: self.stdout.write(
                    f"Сохранено embeddings: {done}/{plan}"
                ),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нет чанков для векторизации."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Векторизация завершена. Сохранено embeddings: {processed}."
            )
        )
