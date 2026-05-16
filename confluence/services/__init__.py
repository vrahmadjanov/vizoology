"""Сервисы Confluence: клиент API, чанкинг текста, синхронизация и векторизация."""

from confluence.client import ConfluenceClient
from confluence.services.chunks import TextChunk, split_text_into_chunks
from confluence.services.pages import (
    confluence_page_to_record,
    iter_confluence_pages,
    normalize_confluence_results,
)
from confluence.utils import html_to_plain_text, page_body_to_plain_text

__all__ = [
    "ConfluenceClient",
    "TextChunk",
    "confluence_page_to_record",
    "html_to_plain_text",
    "iter_confluence_pages",
    "normalize_confluence_results",
    "page_body_to_plain_text",
    "split_text_into_chunks",
]
