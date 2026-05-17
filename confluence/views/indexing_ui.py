from __future__ import annotations

import json
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from confluence.client import ConfluenceClient
from confluence.forms import DocumentationIndexForm
from confluence.models import DocumentationIndexJob
from confluence.services.accessible_spaces import get_accessible_space_summaries
from confluence.services.indexing_job import schedule_documentation_indexing


def _available_spaces_context() -> dict:
    try:
        cf = ConfluenceClient(require_space_key=False)
        return {
            "available_spaces": get_accessible_space_summaries(cf.api),
            "available_spaces_error": None,
        }
    except Exception as exc:
        return {"available_spaces": [], "available_spaces_error": str(exc)}


@staff_member_required
def index_documentation_form(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DocumentationIndexForm(request.POST)
        if form.is_valid():
            keys = form.cleaned_data["space_keys_list"]
            embed_bs = form.cleaned_data.get("embed_batch_size")
            params = {
                "space_keys": keys,
                "batch_size": form.cleaned_data["batch_size"],
                "start": 0,
                "retries": 2,
                "max_pages": form.cleaned_data["max_pages"],
                "max_chars": form.cleaned_data["max_chars"],
                "dry_run_chunks": form.cleaned_data["dry_run_chunks"],
                "embed_max_chunks": form.cleaned_data["embed_max_chunks"],
                "force_embed": form.cleaned_data["force_embed"],
                "embed_batch_size": embed_bs,
            }
            job_id = schedule_documentation_indexing(
                params,
                user_id=request.user.id if request.user.is_authenticated else None,
            )
            messages.success(
                request,
                f"Индексация запущена. Задание {job_id}",
            )
            return redirect(
                "confluence:index_documentation_job",
                job_id=job_id,
            )
    else:
        form = DocumentationIndexForm()

    ctx = {"form": form, **_available_spaces_context()}
    return render(
        request,
        "confluence/index_form.html",
        ctx,
    )


@staff_member_required
def index_documentation_job(request: HttpRequest, job_id: uuid.UUID) -> HttpResponse:
    job = DocumentationIndexJob.objects.filter(pk=job_id).first()
    if job is None:
        messages.error(request, "Задание не найдено.")
        return redirect("confluence:index_documentation_ui")

    auto_refresh = job.status in (
        DocumentationIndexJob.Status.PENDING,
        DocumentationIndexJob.Status.RUNNING,
    )
    detail_pretty = json.dumps(job.detail, ensure_ascii=False, indent=2) if job.detail else ""
    result_pretty = (
        json.dumps(job.result, ensure_ascii=False, indent=2) if job.result else ""
    )

    return render(
        request,
        "confluence/index_job.html",
        {
            "job": job,
            "auto_refresh": auto_refresh,
            "detail_pretty": detail_pretty,
            "result_pretty": result_pretty,
            "form_url": reverse("confluence:index_documentation_ui"),
            "status_url": reverse(
                "confluence:index_documentation_job",
                kwargs={"job_id": job.id},
            ),
        },
    )
