from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from parser.models import ExcelAskJob
from parser.services.excel_job_runner import process_excel_job


def _start_excel_job_thread(job_id) -> None:
    """Запуск в отдельном потоке (после commit транзакции)."""
    thread = threading.Thread(
        target=process_excel_job,
        args=(job_id,),
        daemon=True,
    )
    thread.start()


def create_excel_job(
    upload: UploadedFile,
    cleaned_data: Mapping[str, Any],
) -> ExcelAskJob:
    """
    Создаёт задание Excel Ask из загруженного файла и данных формы.
    Проверяет расширение .xlsx; иначе ValueError.
    """
    if not upload.name.lower().endswith(".xlsx"):
        raise ValueError("Допускаются только файлы с расширением .xlsx.")

    return ExcelAskJob.objects.create(
        original_filename=upload.name,
        input_file=upload,
        sheet=cleaned_data["sheet"].strip(),
        questions_col=cleaned_data["questions_col"].strip(),
        answers_start_col=cleaned_data["answers_start_col"].strip(),
        top_k=cleaned_data["top_k"],
        min_score=cleaned_data["min_score"],
        save_history=cleaned_data["save_history"],
    )


def schedule_excel_job_after_commit(job: ExcelAskJob) -> None:
    """Планирует выполнение задания обработки Excel после фиксации транзакции."""
    transaction.on_commit(lambda pk=job.pk: _start_excel_job_thread(pk))
