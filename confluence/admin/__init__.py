from django.contrib import admin

from confluence.models import ConfluencePage, ConfluencePageChunk


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


@admin.register(ConfluencePageChunk)
class ConfluencePageChunkAdmin(admin.ModelAdmin):
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
