from django.contrib import admin

from ai.models import QuestionAnswerHistory


@admin.register(QuestionAnswerHistory)
class QuestionAnswerHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "short_question",
        "short_answer_preview",
        "model_name",
        "top_k",
        "min_score",
        "created_at",
    ]
    list_filter = ["model_name", "created_at"]
    search_fields = ["question", "short_answer", "reasoning_summary"]
    readonly_fields = [
        "question",
        "short_answer",
        "reasoning_summary",
        "source_numbers",
        "sources",
        "model_name",
        "top_k",
        "min_score",
        "created_at",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    @admin.display(description="Вопрос")
    def short_question(self, obj: QuestionAnswerHistory) -> str:
        return _truncate(obj.question, max_length=100)

    @admin.display(description="Короткий ответ")
    def short_answer_preview(self, obj: QuestionAnswerHistory) -> str:
        return _truncate(obj.short_answer, max_length=120)

    def has_add_permission(self, request) -> bool:
        return False


def _truncate(text: str, *, max_length: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."
