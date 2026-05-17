from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

from django.db import close_old_connections
from django.utils import timezone

from confluence.models import DocumentationIndexJob
from confluence.services.indexing import (
    documentation_indexing_result_to_dict,
    run_documentation_indexing,
)

logger = logging.getLogger(__name__)


def schedule_documentation_indexing(
    params: dict[str, Any],
    *,
    user_id: int | None,
) -> uuid.UUID:
    job = DocumentationIndexJob.objects.create(
        params=params,
        created_by_id=user_id,
        status=DocumentationIndexJob.Status.PENDING,
    )
    thread = threading.Thread(
        target=_run_index_job,
        args=(job.pk,),
        daemon=True,
        name=f"confluence-index-{job.pk}",
    )
    thread.start()
    logger.info("Задание индексации %s поставлено в очередь", job.pk)
    return job.pk


def _job_notify(job_pk: uuid.UUID, stage: str, detail: dict) -> None:
    DocumentationIndexJob.objects.filter(pk=job_pk).update(
        stage=stage,
        detail=detail,
        updated_at=timezone.now(),
    )


def _run_index_job(job_pk: uuid.UUID) -> None:
    close_old_connections()
    try:
        job = DocumentationIndexJob.objects.get(pk=job_pk)
        job.status = DocumentationIndexJob.Status.RUNNING
        job.started_at = timezone.now()
        job.stage = "starting"
        job.detail = {}
        job.save(update_fields=["status", "started_at", "stage", "detail", "updated_at"])
        logger.info("Задание индексации %s: выполнение началось", job_pk)

        p = job.params
        result = run_documentation_indexing(
            p["space_keys"],
            batch_size=p["batch_size"],
            start=p["start"],
            retries=p["retries"],
            max_pages=p["max_pages"],
            max_chars=p["max_chars"],
            dry_run_chunks=p["dry_run_chunks"],
            embed_batch_size=p.get("embed_batch_size"),
            embed_max_chunks=p["embed_max_chunks"],
            force_embed=p["force_embed"],
            on_stage=lambda stage, detail: _job_notify(job_pk, stage, detail),
        )

        job = DocumentationIndexJob.objects.get(pk=job_pk)
        job.status = DocumentationIndexJob.Status.DONE
        job.result = documentation_indexing_result_to_dict(result)
        job.finished_at = timezone.now()
        job.stage = ""
        job.detail = {}
        job.error_message = ""
        job.save(
            update_fields=[
                "status",
                "result",
                "finished_at",
                "stage",
                "detail",
                "error_message",
                "updated_at",
            ]
        )
        logger.info("Задание индексации %s: успешно завершено", job_pk)
    except Exception as exc:
        logger.exception(
            "Задание индексации %s завершилось с ошибкой: %s",
            job_pk,
            exc,
        )
        try:
            job = DocumentationIndexJob.objects.get(pk=job_pk)
            job.status = DocumentationIndexJob.Status.FAILED
            job.error_message = str(exc)
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "error_message",
                    "finished_at",
                    "updated_at",
                ]
            )
        except DocumentationIndexJob.DoesNotExist:
            logger.error(
                "Не удалось сохранить статус ошибки: задание %s не найдено",
                job_pk,
            )
    finally:
        close_old_connections()
