"""Сервисы Confluence: клиент API, чанкинг текста, синхронизация и векторизация."""

from confluence.services.core import (
    ConfluenceConnectionSettings,
    TextChunk,
    confluence_page_to_record,
    get_confluence_client,
    get_confluence_settings,
    html_to_plain_text,
    iter_confluence_pages,
    normalize_confluence_results,
    page_body_to_plain_text,
    split_text_into_chunks,
)

__all__ = [
    "ConfluenceConnectionSettings",
    "TextChunk",
    "confluence_page_to_record",
    "get_confluence_client",
    "get_confluence_settings",
    "html_to_plain_text",
    "iter_confluence_pages",
    "normalize_confluence_results",
    "page_body_to_plain_text",
    "split_text_into_chunks",
]
