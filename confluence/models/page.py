from django.contrib.postgres.indexes import OpClass
from django.db import models
from django.utils import timezone
from pgvector.django import HnswIndex, VectorField


class ConfluencePage(models.Model):
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


class ConfluencePageChunk(models.Model):
    page = models.ForeignKey(
        ConfluencePage,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    position = models.PositiveIntegerField()
    text = models.TextField()
    text_hash = models.CharField(max_length=64, db_index=True)
    char_start = models.PositiveIntegerField()
    char_end = models.PositiveIntegerField()
    embedding = VectorField(dimensions=384, null=True, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True, db_index=True)
    embedded_text_hash = models.CharField(max_length=64, blank=True, db_index=True)
    embedded_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page_id", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "position"],
                name="unique_confluence_chunk_position",
            ),
        ]
        indexes = [
            models.Index(fields=["page", "position"]),
            models.Index(fields=["text_hash"]),
            HnswIndex(
                OpClass("embedding", name="vector_cosine_ops"),
                name="confluence_chunk_embedding_hnsw",
                m=16,
                ef_construction=64,
            ),
        ]

    def __str__(self) -> str:
        return f"{self.page_id} #{self.position}"
