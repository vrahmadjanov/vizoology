"""
Текстовые чанки страниц для разбиения документации и семантического поиска.
"""

from django.contrib.postgres.indexes import OpClass
from django.db import models
from pgvector.django import HnswIndex, VectorField

from confluence.models.pages import ConfluencePage


class Chunk(models.Model):
    """Кусок текста одной страницы: позиция в разбиении, хэш, вектор (pgvector) при индексации."""

    page = models.ForeignKey(ConfluencePage, on_delete=models.CASCADE, related_name="chunks")
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
        db_table = "confluence_confluencepagechunk"
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
