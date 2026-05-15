from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import close_old_connections
from openpyxl import load_workbook

from parser.models import ExcelAskJob
from parser.services.excel_batch import fill_workbook_rag

logger = logging.getLogger(__name__)


def _optional_str(value: str) -> str | None:
    value = (value or "").strip()
    return value or None


def process_excel_job(job_id) -> None:
    """
    Выполняет RAG по сохранённому input_file, пишет result_file, обновляет status.
    Предполагается вызов из фонового потока после close_old_connections().
    """
    close_old_connections()
    try:
        try:
            job = ExcelAskJob.objects.get(pk=job_id)
        except ExcelAskJob.DoesNotExist:
            return

        if job.status != ExcelAskJob.Status.PENDING:
            return

        job.status = ExcelAskJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])

        input_path = job.input_file.path
        wb = load_workbook(input_path)

        try:
            fill_workbook_rag(
                wb,
                sheet_name=_optional_str(job.sheet),
                questions_col=_optional_str(job.questions_col),
                answers_start_col=_optional_str(job.answers_start_col),
                top_k=job.top_k,
                min_score=job.min_score,
                save_history=job.save_history,
            )
        except Exception as exc:
            logger.exception("ExcelAskJob %s failed", job_id)
            job.status = ExcelAskJob.Status.FAILED
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message", "updated_at"])
            return

        buf = BytesIO()
        wb.save(buf)
        stem = Path(job.original_filename).stem
        out_name = f"{stem}_answered.xlsx"
        job.result_file.save(
            out_name,
            ContentFile(buf.getvalue()),
            save=False,
        )
        job.status = ExcelAskJob.Status.DONE
        job.save(update_fields=["result_file", "status", "updated_at"])
    finally:
        close_old_connections()
