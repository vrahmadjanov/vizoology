from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db.models import F
from pgvector.django import CosineDistance

from confluence.embeddings import LocalEmbeddingService
from confluence.models import ConfluencePageChunk


@dataclass(frozen=True)
class ConfluenceSearchResult:
    chunk: ConfluencePageChunk
    distance: float

    @property
    def score(self) -> float:
        return 1 - self.distance

    @property
    def page_title(self) -> str:
        return self.chunk.page.title

    @property
    def page_url(self) -> str:
        return self.chunk.page.url


def search_confluence_chunks(
    query: str,
    *,
    top_k: int = 5,
    embedding_service: LocalEmbeddingService | None = None,
) -> list[ConfluenceSearchResult]:
    query = query.strip()
    if not query:
        return []
    if top_k < 1:
        raise ValueError("top_k должен быть больше 0.")

    service = embedding_service or LocalEmbeddingService()
    query_embedding = service.embed_queries([query])[0].vector

    chunks = (
        ConfluencePageChunk.objects.select_related("page")
        .filter(
            embedding__isnull=False,
            embedding_model=settings.EMBEDDING_MODEL_NAME,
            embedded_text_hash=F("text_hash"),
        )
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .order_by("distance", "id")[:top_k]
    )

    return [
        ConfluenceSearchResult(chunk=chunk, distance=float(chunk.distance))
        for chunk in chunks
    ]


def search_result_excerpt(text: str, *, max_chars: int = 500) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    excerpt = text[:max_chars].rstrip()
    last_space = excerpt.rfind(" ")
    if last_space > 0:
        excerpt = excerpt[:last_space]
    return excerpt + "..."
