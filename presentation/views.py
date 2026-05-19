from __future__ import annotations

from pathlib import Path

from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from parser.forms import ExcelAskForm
from parser.models import ExcelAskJob
from presentation.services.excel_ask import (
    create_excel_job,
    schedule_excel_job_after_commit,
)


def excel_ask_view(request):
    if request.method == "POST":
        form = ExcelAskForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["workbook"]
            try:
                job = create_excel_job(upload, form.cleaned_data)
            except ValueError as exc:
                form.add_error("workbook", str(exc))
            except DatabaseError:
                form.add_error(
                    None,
                    "Не удалось сохранить задание. Проверьте миграции и доступ к базе данных.",
                )
            else:
                schedule_excel_job_after_commit(job)
                return redirect(
                    "presentation_ask_job",
                    pk=str(job.pk),
                )
    else:
        form = ExcelAskForm()

    return render(request, "presentation/excel_ask.html", {"form": form})


def excel_ask_job_list_view(request):
    """Список заданий Excel (история)."""
    paginator = Paginator(
        ExcelAskJob.objects.all(),
        per_page=30,
    )
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "presentation/excel_job_list.html",
        {"page_obj": page_obj},
    )


def excel_ask_job_view(request, pk):
    """Страница «задание принято» и опрос готовности."""
    job = get_object_or_404(ExcelAskJob, pk=pk)
    return render(
        request,
        "presentation/excel_ask_job.html",
        {
            "job": job,
            "status_url": reverse(
                "presentation_ask_job_status", kwargs={"pk": pk}
            ),
            "download_url": reverse(
                "presentation_ask_job_download",
                kwargs={"pk": pk},
            ),
        },
    )


def excel_ask_job_status_json(request, pk):
    """JSON для опроса: статус и ссылка на скачивание когда готово."""
    job = get_object_or_404(ExcelAskJob, pk=pk)
    payload = {
        "status": job.status,
        "error_message": job.error_message,
        "download_url": "",
    }
    if job.status == ExcelAskJob.Status.DONE and job.result_file:
        payload["download_url"] = reverse(
            "presentation_ask_job_download",
            kwargs={"pk": str(job.pk)},
        )
    return JsonResponse(payload)


def excel_ask_job_download_view(request, pk):
    """Отдаёт готовый .xlsx."""
    job = get_object_or_404(ExcelAskJob, pk=pk)
    if job.status != ExcelAskJob.Status.DONE or not job.result_file.name:
        raise Http404("Файл ещё не готов или задание завершилось с ошибкой.")
    try:
        return FileResponse(
            job.result_file.open("rb"),
            as_attachment=True,
            filename=Path(job.original_filename).stem + "_answered.xlsx",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
    except FileNotFoundError as exc:
        raise Http404("Файл результата не найден на диске.") from exc
