from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from confluence.utils import LocalEmbeddingService
from confluence.models import Chunk

logger = logging.getLogger(__name__)


def validate_embed_chunks_options(batch_size: int, max_chunks: int) -> None:
    if batch_size < 1:
        raise ValueError("--batch-size должен быть больше 0.")
    if max_chunks < 0:
        raise ValueError("--max-chunks не может быть отрицательным.")


def iter_chunks_to_embed(*, force: bool, space_keys: Sequence[str] | None = None):
    chunks = Chunk.objects.select_related("page").exclude(text="")
    if space_keys:
        chunks = chunks.filter(page__space_key__in=list(space_keys))
    if not force:
        chunks = chunks.filter(
            Q(embedding__isnull=True)
            | ~Q(embedding_model=settings.EMBEDDING_MODEL_NAME)
            | ~Q(embedded_text_hash=F("text_hash"))
        )
    return chunks.order_by("id")


def embed_chunk_batches(
    *,
    batch_size: int,
    max_chunks: int,
    force: bool,
    space_keys: Sequence[str] | None = None,
    service: LocalEmbeddingService | None = None,
    on_start: Callable[[int, LocalEmbeddingService], None] | None = None,
    on_batch_saved: Callable[[int, int], None] | None = None,
) -> tuple[int, int]:
    """
    Векторизует чанки и сохраняет embeddings.
    Возвращает (processed, total_planned).
    """
    validate_embed_chunks_options(batch_size, max_chunks)

    qs = iter_chunks_to_embed(force=force, space_keys=space_keys)
    if max_chunks:
        qs = qs[:max_chunks]

    total = qs.count()
    if total == 0:
        logger.info("Эмбеддинги: нет чанков, требующих векторизации")
        return 0, 0

    logger.info("Эмбеддинги: к векторизации %s чанков (batch_size=%s)", total, batch_size)

    embed_service = service or LocalEmbeddingService()
    if on_start:
        on_start(total, embed_service)

    processed = 0
    batch: list[Chunk] = []

    for chunk in qs.iterator(chunk_size=batch_size):
        batch.append(chunk)
        if len(batch) >= batch_size:
            processed += _embed_and_save_batch(embed_service, batch, batch_size)
            if on_batch_saved:
                on_batch_saved(processed, total)
            batch = []

    if batch:
        processed += _embed_and_save_batch(embed_service, batch, batch_size)
        if on_batch_saved:
            on_batch_saved(processed, total)

    return processed, total


def _embed_and_save_batch(
    service: LocalEmbeddingService,
    chunks: list[Chunk],
    batch_size: int,
) -> int:
    results = service.embed_passages(
        [chunk.text for chunk in chunks], batch_size=batch_size
    )
    if len(results) != len(chunks):
        logger.error(
            "Сервис эмбеддингов вернул %s векторов при %s чанках",
            len(results),
            len(chunks),
        )
        raise ValueError("Количество embeddings не совпало с количеством чанков.")

    embedded_at = timezone.now()
    for chunk, result in zip(chunks, results, strict=True):
        if result.dimensions != settings.EMBEDDING_DIMENSIONS:
            logger.error(
                "Неверная размерность эмбеддинга: ожидалось %s, получено %s",
                settings.EMBEDDING_DIMENSIONS,
                result.dimensions,
            )
            raise ValueError(
                f"Ожидалась размерность {settings.EMBEDDING_DIMENSIONS}, "
                f"получено {result.dimensions}."
            )
        chunk.embedding = result.vector
        chunk.embedding_model = service.model_name
        chunk.embedded_text_hash = chunk.text_hash
        chunk.embedded_at = embedded_at
        chunk.updated_at = embedded_at

    Chunk.objects.bulk_update(
        chunks,
        [
            "embedding",
            "embedding_model",
            "embedded_text_hash",
            "embedded_at",
            "updated_at",
        ],
        batch_size=batch_size,
    )
    return len(chunks)
