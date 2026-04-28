from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from confluence.embeddings import LocalEmbeddingService
from confluence.models import ConfluencePageChunk


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

        if batch_size < 1:
            raise CommandError("--batch-size должен быть больше 0.")
        if max_chunks < 0:
            raise CommandError("--max-chunks не может быть отрицательным.")

        chunks = ConfluencePageChunk.objects.select_related("page").exclude(text="")
        if not force:
            chunks = chunks.filter(
                Q(embedding__isnull=True)
                | ~Q(embedding_model=settings.EMBEDDING_MODEL_NAME)
                | ~Q(embedded_text_hash=F("text_hash"))
            )
        chunks = chunks.order_by("id")
        if max_chunks:
            chunks = chunks[:max_chunks]

        total = chunks.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нет чанков для векторизации."))
            return

        service = LocalEmbeddingService()
        self.stdout.write(
            f"Векторизую чанки: {total}, model={service.model_name}, batch={batch_size}..."
        )

        processed = 0
        batch = []
        for chunk in chunks.iterator(chunk_size=batch_size):
            batch.append(chunk)
            if len(batch) >= batch_size:
                processed += self._embed_batch(service, batch, batch_size)
                self.stdout.write(f"Сохранено embeddings: {processed}/{total}")
                batch = []

        if batch:
            processed += self._embed_batch(service, batch, batch_size)
            self.stdout.write(f"Сохранено embeddings: {processed}/{total}")

        self.stdout.write(
            self.style.SUCCESS(f"Векторизация завершена. Сохранено embeddings: {processed}.")
        )

    def _embed_batch(
        self,
        service: LocalEmbeddingService,
        chunks: list[ConfluencePageChunk],
        batch_size: int,
    ) -> int:
        results = service.embed_passages([chunk.text for chunk in chunks], batch_size=batch_size)
        if len(results) != len(chunks):
            raise CommandError("Количество embeddings не совпало с количеством чанков.")

        embedded_at = timezone.now()
        for chunk, result in zip(chunks, results, strict=True):
            if result.dimensions != settings.EMBEDDING_DIMENSIONS:
                raise CommandError(
                    f"Ожидалась размерность {settings.EMBEDDING_DIMENSIONS}, "
                    f"получено {result.dimensions}."
                )
            chunk.embedding = result.vector
            chunk.embedding_model = service.model_name
            chunk.embedded_text_hash = chunk.text_hash
            chunk.embedded_at = embedded_at
            chunk.updated_at = embedded_at

        ConfluencePageChunk.objects.bulk_update(
            chunks,
            ["embedding", "embedding_model", "embedded_text_hash", "embedded_at", "updated_at"],
            batch_size=batch_size,
        )
        return len(chunks)
