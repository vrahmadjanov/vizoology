from django.contrib import admin

from confluence.models import Chunk, ConfluencePage, DocumentationIndexJob


@admin.register(ConfluencePage)
class ConfluencePageAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "space_key",
        "confluence_id",
        "version_number",
        "synced_at",
    )
    list_filter = ("space_key",)
    search_fields = ("title", "confluence_id", "body_text")
    readonly_fields = ("created_at", "updated_at", "synced_at")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = (
        "page",
        "position",
        "char_start",
        "char_end",
        "embedding_model",
        "embedded_at",
    )
    list_filter = ("page__space_key", "embedding_model")
    search_fields = ("text", "page__title", "page__confluence_id")
    readonly_fields = ("created_at", "updated_at", "embedded_at")


@admin.register(DocumentationIndexJob)
class DocumentationIndexJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "stage",
        "created_at",
        "finished_at",
        "created_by",
    )
    list_filter = ("status",)
    search_fields = ("id", "stage", "error_message")
    readonly_fields = (
        "id",
        "status",
        "stage",
        "detail",
        "params",
        "result",
        "error_message",
        "created_by",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    )
