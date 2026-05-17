from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass

from django.conf import settings

from confluence.client import ConfluenceClient
from confluence.services.chunks import build_chunks
from confluence.services.embedding import embed_chunk_batches
from confluence.services.pages import sync_pages_from_confluence

logger = logging.getLogger(__name__)

OnIndexStage = Callable[[str, dict], None]


@dataclass(frozen=True)
class SpaceIndexStepResult:
    space_key: str
    sync: dict[str, int]
    chunks: dict[str, int] | None


@dataclass(frozen=True)
class DocumentationIndexingResult:
    spaces: tuple[SpaceIndexStepResult, ...]
    embed_processed: int
    embed_total: int


def documentation_indexing_result_to_dict(result: DocumentationIndexingResult) -> dict:
    return {
        "spaces": [asdict(s) for s in result.spaces],
        "embed": {
            "processed": result.embed_processed,
            "total": result.embed_total,
        },
    }


def run_documentation_indexing(
    space_keys: list[str],
    *,
    batch_size: int = 25,
    start: int = 0,
    retries: int = 2,
    max_pages: int = 0,
    max_chars: int = 1800,
    dry_run_chunks: bool = False,
    embed_batch_size: int | None = None,
    embed_max_chunks: int = 0,
    force_embed: bool = False,
    on_stage: OnIndexStage | None = None,
) -> DocumentationIndexingResult:
    """
    По очереди для каждого space: синхронизация страниц → чанкинг → в конце эмбеддинги
    только для чанков страниц из переданных пространств.

    ``on_stage(stage, detail)`` вызывается на этапах (для UI / фоновой задачи).
    """
    if not space_keys:
        raise ValueError("Список space_keys не может быть пустым.")

    space_keys = list(dict.fromkeys(space_keys))

    def _notify(stage: str, detail: dict | None = None) -> None:
        if on_stage:
            on_stage(stage, detail or {})

    _notify("init", {"space_keys": space_keys})
    logger.info("Индексация документации: старт, пространства %s", space_keys)

    cf = ConfluenceClient()
    base_url = settings.CONFLUENCE_BASE_URL
    embed_bs = embed_batch_size if embed_batch_size is not None else settings.EMBEDDING_BATCH_SIZE

    steps: list[SpaceIndexStepResult] = []
    for space_key in space_keys:
        _notify(f"sync:{space_key}", {})
        logger.info("Синхронизация страниц началась (space=%s)", space_key)
        sync_out = sync_pages_from_confluence(
            cf.api,
            base_url=base_url,
            space_key=space_key,
            batch_size=batch_size,
            start=start,
            retries=retries,
            max_pages=max_pages,
            on_batch_progress=None,
        )
        _notify(
            f"sync:{space_key}:done",
            {
                "seen_count": sync_out.seen_count,
                "created_count": sync_out.created_count,
                "updated_count": sync_out.updated_count,
                "skipped_empty_count": sync_out.skipped_empty_count,
            },
        )
        logger.info(
            "Синхронизация страниц завершена (space=%s): "
            "просмотрено=%s создано=%s обновлено=%s без_текста=%s",
            space_key,
            sync_out.seen_count,
            sync_out.created_count,
            sync_out.updated_count,
            sync_out.skipped_empty_count,
        )

        _notify(f"chunks:{space_key}", {})
        logger.info("Построение чанков началось (space=%s)", space_key)
        chunk_result = build_chunks(
            space_key=space_key,
            page_id="",
            max_chars=max_chars,
            dry_run=dry_run_chunks,
            on_start=None,
            on_progress=None,
        )
        _notify(
            f"chunks:{space_key}:done",
            asdict(chunk_result) if chunk_result else {"page_count": 0, "total_chunks": 0},
        )
        if chunk_result:
            logger.info(
                "Построение чанков завершено (space=%s): страниц=%s чанков=%s",
                space_key,
                chunk_result.page_count,
                chunk_result.total_chunks,
            )
        else:
            logger.info(
                "Построение чанков завершено (space=%s): нет страниц с текстом",
                space_key,
            )
        steps.append(
            SpaceIndexStepResult(
                space_key=space_key,
                sync=asdict(sync_out),
                chunks=asdict(chunk_result) if chunk_result else None,
            )
        )

    def _embed_saved(processed: int, total: int) -> None:
        _notify("embed", {"processed": processed, "total": total})

    _notify("embed", {"message": "starting"})
    logger.info("Эмбеддинги: этап начат")
    embed_processed, embed_total = embed_chunk_batches(
        batch_size=embed_bs,
        max_chunks=embed_max_chunks,
        force=force_embed,
        space_keys=space_keys,
        on_batch_saved=_embed_saved if on_stage else None,
    )

    logger.info(
        "Эмбеддинги: завершено, векторизовано %s из %s чанков",
        embed_processed,
        embed_total,
    )
    logger.info("Индексация документации: все этапы успешно выполнены")

    return DocumentationIndexingResult(
        spaces=tuple(steps),
        embed_processed=embed_processed,
        embed_total=embed_total,
    )
