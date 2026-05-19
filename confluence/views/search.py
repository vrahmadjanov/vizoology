from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from confluence.utils import search_confluence_chunks

SEARCH_TOP_K = 5


@staff_member_required
def local_documentation_search(request: HttpRequest) -> HttpResponse:
    q_raw = request.GET.get("q", "")
    q = q_raw.strip()

    results: list = []
    error: str | None = None
    if q:
        try:
            results = search_confluence_chunks(q, top_k=SEARCH_TOP_K)
        except Exception as exc:
            error = str(exc)

    return render(
        request,
        "confluence/search.html",
        {
            "q": q_raw,
            "results": results,
            "error": error,
        },
    )
