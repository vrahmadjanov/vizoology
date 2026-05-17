from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ai.validators import validate_top_k
from confluence.utils import search_confluence_chunks


@staff_member_required
def local_documentation_search(request: HttpRequest) -> HttpResponse:
    q_raw = request.GET.get("q", "")
    q = q_raw.strip()
    try:
        top_k = min(max(int(request.GET.get("k") or 15), 1), 50)
    except (TypeError, ValueError):
        top_k = 15

    results: list = []
    error: str | None = None
    if q:
        try:
            validate_top_k(top_k)
            results = search_confluence_chunks(q, top_k=top_k)
        except Exception as exc:
            error = str(exc)

    return render(
        request,
        "confluence/search.html",
        {
            "q": q_raw,
            "k": top_k,
            "results": results,
            "error": error,
        },
    )
