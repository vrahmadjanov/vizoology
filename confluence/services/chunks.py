from __future__ import annotations

"""
Разбиение текста на чанки для индексации (Confluence и др.).

Содержит структуру ``TextChunk``, нарезку сохранённого плоского текста
и запись чанков в ``Chunk`` из ``body_text`` страниц в БД.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from django.db import transaction

from confluence.models import Chunk, ConfluencePage


@dataclass(frozen=True)
class TextChunk:
    position: int
    text: str
    char_start: int
    char_end: int
    text_hash: str


def split_text_into_chunks(text: str, *, max_chars: int = 1800) -> list[TextChunk]:
    if max_chars < 200:
        raise ValueError("max_chars должен быть не меньше 200.")

    blocks = _text_blocks_with_offsets(text)
    chunks: list[TextChunk] = []
    current_parts: list[tuple[str, int, int]] = []

    for block in blocks:
        block_text, _, _ = block
        current_text = _join_chunk_parts(current_parts)
        separator_len = 2 if current_text else 0
        projected_len = len(current_text) + separator_len + len(block_text)

        if current_parts and projected_len > max_chars:
            chunks.append(_make_text_chunk(len(chunks), current_parts))
            current_parts = []

        if len(block_text) <= max_chars:
            current_parts.append(block)
            continue

        for part in _split_large_block(block, max_chars=max_chars):
            if current_parts:
                chunks.append(_make_text_chunk(len(chunks), current_parts))
                current_parts = []
            chunks.append(_make_text_chunk(len(chunks), [part]))

    if current_parts:
        chunks.append(_make_text_chunk(len(chunks), current_parts))

    return chunks


def _text_blocks_with_offsets(text: str) -> list[tuple[str, int, int]]:
    blocks = []
    cursor = 0
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            cursor += len(raw_line) + 1
            continue

        start = text.find(stripped, cursor)
        if start == -1:
            start = cursor
        end = start + len(stripped)
        blocks.append((stripped, start, end))
        cursor = end
    return blocks


def _split_large_block(
    block: tuple[str, int, int],
    *,
    max_chars: int,
) -> list[tuple[str, int, int]]:
    block_text, block_start, _ = block
    parts = []
    offset = 0

    while offset < len(block_text):
        end = min(offset + max_chars, len(block_text))
        if end < len(block_text):
            whitespace_at = block_text.rfind(" ", offset, end)
            if whitespace_at > offset:
                end = whitespace_at

        part_text = block_text[offset:end].strip()
        if part_text:
            part_start = block_start + offset + len(block_text[offset:end]) - len(
                block_text[offset:end].lstrip()
            )
            parts.append((part_text, part_start, part_start + len(part_text)))
        offset = end
        while offset < len(block_text) and block_text[offset].isspace():
            offset += 1

    return parts


def _join_chunk_parts(parts: list[tuple[str, int, int]]) -> str:
    return "\n\n".join(part[0] for part in parts).strip()


def _make_text_chunk(position: int, parts: list[tuple[str, int, int]]) -> TextChunk:
    chunk_text = _join_chunk_parts(parts)
    return TextChunk(
        position=position,
        text=chunk_text,
        char_start=parts[0][1],
        char_end=parts[-1][2],
        text_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
    )


@dataclass(frozen=True)
class ChunkBuildResult:
    page_count: int
    total_chunks: int


def validate_chunk_build_max_chars(max_chars: int) -> None:
    if max_chars < 200:
        raise ValueError("--max-chars должен быть не меньше 200.")


def build_chunks(
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
                Chunk(
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
                Chunk.objects.bulk_create(chunk_models, batch_size=500)

        if on_progress and index % progress_every == 0:
            on_progress(index, total_chunks)

    return ChunkBuildResult(page_count=page_count, total_chunks=total_chunks)
