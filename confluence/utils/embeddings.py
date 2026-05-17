from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from django.conf import settings


PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


@dataclass(frozen=True)
class EmbeddingResult:
    text: str
    vector: list[float]

    @property
    def dimensions(self) -> int:
        return len(self.vector)


class LocalEmbeddingService:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME

    @cached_property
    def model(self):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.model_name)

    def embed_passages(self, texts: list[str], *, batch_size: int | None = None) -> list[EmbeddingResult]:
        return self._embed(texts, prefix=PASSAGE_PREFIX, batch_size=batch_size)

    def embed_queries(self, texts: list[str], *, batch_size: int | None = None) -> list[EmbeddingResult]:
        return self._embed(texts, prefix=QUERY_PREFIX, batch_size=batch_size)

    def _embed(
        self,
        texts: list[str],
        *,
        prefix: str,
        batch_size: int | None = None,
    ) -> list[EmbeddingResult]:
        clean_texts = [text.strip() for text in texts if text.strip()]
        if not clean_texts:
            return []

        prepared_texts = [format_e5_text(text, prefix=prefix) for text in clean_texts]
        vectors = self.model.encode(
            prepared_texts,
            batch_size=batch_size or settings.EMBEDDING_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return [
            EmbeddingResult(text=text, vector=vector.astype(float).tolist())
            for text, vector in zip(clean_texts, vectors, strict=True)
        ]


def format_e5_text(text: str, *, prefix: str) -> str:
    return prefix + " ".join(text.split())
