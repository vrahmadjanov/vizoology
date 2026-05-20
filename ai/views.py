from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from ai.rag import answer_question
from ai.services.history import sources_for_answer


@staff_member_required
def ask(request):
    ctx: dict = {}
    if request.method == "POST":
        question = (request.POST.get("question") or "").strip()
        ctx["question"] = question
        if not question:
            ctx["error"] = "Введите вопрос."
        else:
            try:
                rag = answer_question(question)
                ctx["answer"] = rag.structured_answer.short_answer
                ctx["reasoning"] = rag.structured_answer.reasoning_summary
                ctx["sources"] = sources_for_answer(rag)
                ctx["model"] = rag.model
            except ValueError as exc:
                ctx["error"] = str(exc)
            except Exception as exc:
                ctx["error"] = f"Не удалось получить ответ: {exc}"
    return render(request, "ai/ask.html", ctx)
