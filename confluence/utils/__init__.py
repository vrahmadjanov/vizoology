"""
Вспомогательный слой Confluence: HTML → текст, embeddings, векторный поиск по чанкам.
"""

from confluence.utils.embeddings import (
    PASSAGE_PREFIX,
    QUERY_PREFIX,
    EmbeddingResult,
    LocalEmbeddingService,
    format_e5_text,
)
from confluence.utils.html import html_to_plain_text, page_body_to_plain_text
from confluence.utils.search import (
    ConfluenceSearchResult,
    search_confluence_chunks,
    search_result_excerpt,
)

__all__ = [
    "PASSAGE_PREFIX",
    "QUERY_PREFIX",
    "ConfluenceSearchResult",
    "EmbeddingResult",
    "LocalEmbeddingService",
    "format_e5_text",
    "html_to_plain_text",
    "page_body_to_plain_text",
    "search_confluence_chunks",
    "search_result_excerpt",
]
