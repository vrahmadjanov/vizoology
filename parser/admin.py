from django.contrib import admin

from parser.models import ExcelAskJob


@admin.register(ExcelAskJob)
class ExcelAskJobAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    readonly_fields = (
        "id",
        "status",
        "original_filename",
        "input_file",
        "result_file",
        "sheet",
        "questions_col",
        "answers_start_col",
        "top_k",
        "min_score",
        "save_history",
        "error_message",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False
