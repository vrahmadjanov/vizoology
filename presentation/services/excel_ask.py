from __future__ import annotations

import threading

from django.db import transaction

from parser.services.excel_job_runner import process_excel_job


def _start_excel_job_thread(job_id) -> None:
    """Запуск в отдельном потоке (после commit транзакции)."""
    thread = threading.Thread(
        target=process_excel_job,
        args=(job_id,),
        daemon=True,
    )
    thread.start()


def schedule_excel_job_after_commit(job) -> None:
    """Планирует выполнение задания обработки Excel после фиксации транзакции."""
    transaction.on_commit(lambda pk=job.pk: _start_excel_job_thread(pk))
