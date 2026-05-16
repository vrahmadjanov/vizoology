"""
Страницы Confluence, синхронизированные в локальную БД.
"""

from django.db import models
from django.utils import timezone


class ConfluencePage(models.Model):
    """Одна wiki-страница: id в Confluence, space, заголовок, URL и извлеченный текст."""

    confluence_id = models.CharField(max_length=64, unique=True, db_index=True)
    space_key = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000, blank=True)
    version_number = models.PositiveIntegerField(default=0)
    parent_confluence_id = models.CharField(max_length=64, blank=True, db_index=True)
    body_text = models.TextField(blank=True)
    body_hash = models.CharField(max_length=64, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["space_key", "title"]
        indexes = [
            models.Index(fields=["space_key", "title"]),
            models.Index(fields=["space_key", "version_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.space_key}: {self.title}"
