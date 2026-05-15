from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.db import transaction

from confluence.models import ConfluencePage, ConfluencePageChunk
from confluence.services.core import split_text_into_chunks


@dataclass(frozen=True)
class ChunkBuildResult:
    page_count: int
    total_chunks: int


def validate_chunk_build_max_chars(max_chars: int) -> None:
    if max_chars < 200:
        raise ValueError("--max-chars должен быть не меньше 200.")


def build_chunks_for_stored_pages(
    *,
    space_key: str = "",
    page_id: str = "",
    max_chars: int,
    dry_run: bool,
    progress_every: int = 100,
    on_start: Callable[[int], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> ChunkBuildResult | None:
    """
    Разбивает body_text страниц в БД на чанки (или только считает при dry_run).
    Возвращает None, если нет страниц с текстом.
    """
    validate_chunk_build_max_chars(max_chars)

    pages = ConfluencePage.objects.exclude(body_text="")
    if space_key:
        pages = pages.filter(space_key=space_key)
    if page_id:
        pages = pages.filter(confluence_id=page_id)

    page_count = pages.count()
    if page_count == 0:
        return None

    if on_start:
        on_start(page_count)

    total_chunks = 0
    for index, page in enumerate(pages.iterator(chunk_size=100), start=1):
        chunks = split_text_into_chunks(page.body_text, max_chars=max_chars)
        total_chunks += len(chunks)

        if not dry_run:
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

        if on_progress and index % progress_every == 0:
            on_progress(index, total_chunks)

    return ChunkBuildResult(page_count=page_count, total_chunks=total_chunks)
