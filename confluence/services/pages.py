from __future__ import annotations

"""
Загрузка и разбор страниц Confluence через REST API.

Содержит пагинированный обход пространства, загрузку полной страницы по id,
нормализацию ответов списка, сбор полей для модели БД и синхронизацию
в ``ConfluencePage``.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from atlassian import Confluence
from django.db import transaction
from django.utils import timezone

from confluence.models import ConfluencePage
from confluence.utils import page_body_to_plain_text

logger = logging.getLogger(__name__)


def iter_confluence_pages(
    client: Confluence,
    space_key: str,
    *,
    batch_size: int = 25,
    start: int = 0,
    max_pages: int = 0,
    retries: int = 2,
):
    fetched = 0
    list_expand = "version,space,ancestors,_links"
    page_expand = "body.view,body.storage,version,space,ancestors,_links"

    while True:
        response = _get_confluence_page_batch(
            client,
            space_key,
            start=start,
            limit=batch_size,
            expand=list_expand,
            retries=retries,
        )
        results = normalize_confluence_results(response)
        if not results:
            break

        for page_summary in results:
            if max_pages and fetched >= max_pages:
                return
            page = _get_confluence_page_by_id(
                client,
                page_id=page_summary["id"],
                expand=page_expand,
                retries=retries,
            )
            fetched += 1
            yield page

        if len(results) < batch_size:
            break
        start += batch_size


def _get_confluence_page_batch(
    client: Confluence,
    space_key: str,
    *,
    start: int,
    limit: int,
    expand: str,
    retries: int,
):
    """Запрашивает одну страницу списка страниц пространства (пагинация) через API.

    Возвращает сырой ответ ``get_all_pages_from_space_raw`` (словарь с ``results`` и т.д.).
    При временных ошибках повторяет запрос до ``retries`` раз с экспоненциальной паузой.
    """
    for attempt in range(retries + 1):
        try:
            return client.get_all_pages_from_space_raw(
                space=space_key,
                start=start,
                limit=limit,
                expand=expand,
            )
        except Exception as exc:
            if attempt >= retries:
                logger.error(
                    "Confluence API: список страниц пространства %s (start=%s) "
                    "не удалось получить после %s попыток: %s",
                    space_key,
                    start,
                    retries + 1,
                    exc,
                    exc_info=True,
                )
                raise
            logger.warning(
                "Confluence API: повтор запроса списка страниц space=%s start=%s (%s/%s): %s",
                space_key,
                start,
                attempt + 1,
                retries + 1,
                exc,
            )
            time.sleep(2**attempt)


def _get_confluence_page_by_id(
    client: Confluence,
    *,
    page_id: str,
    expand: str,
    retries: int,
):
    for attempt in range(retries + 1):
        try:
            return client.get_page_by_id(page_id, expand=expand)
        except Exception as exc:
            if attempt >= retries:
                logger.error(
                    "Confluence API: страница id=%s не загружена после %s попыток: %s",
                    page_id,
                    retries + 1,
                    exc,
                    exc_info=True,
                )
                raise
            logger.warning(
                "Confluence API: повтор загрузки страницы id=%s (%s/%s): %s",
                page_id,
                attempt + 1,
                retries + 1,
                exc,
            )
            time.sleep(2**attempt)


def confluence_page_to_record(page: dict[str, Any], base_url: str) -> dict[str, Any]:
    body_text = page_body_to_plain_text(page)
    space = page.get("space") or {}
    version = page.get("version") or {}
    ancestors = page.get("ancestors") or []
    links = page.get("_links") or {}
    webui = links.get("webui", "")
    parent = ancestors[-1] if ancestors else {}

    return {
        "confluence_id": str(page["id"]),
        "space_key": space.get("key", ""),
        "title": page.get("title", ""),
        "url": urljoin(base_url.rstrip("/") + "/", webui.lstrip("/")) if webui else "",
        "version_number": int(version.get("number") or 0),
        "parent_confluence_id": str(parent.get("id") or ""),
        "body_text": body_text,
        "body_hash": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
        "raw_payload": page,
    }


def normalize_confluence_results(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        results = response.get("results", [])
        return results if isinstance(results, list) else list(results)
    if isinstance(response, list):
        return response
    if hasattr(response, "__iter__") and not isinstance(response, (str, bytes)):
        return list(response)
    return []


@dataclass(frozen=True)
class SyncPagesResult:
    seen_count: int
    created_count: int
    updated_count: int
    skipped_empty_count: int


def validate_sync_pages_options(
    batch_size: int, start: int, retries: int, max_pages: int
) -> None:
    if batch_size < 1:
        raise ValueError("--batch-size должен быть больше 0.")
    if start < 0:
        raise ValueError("--start не может быть отрицательным.")
    if retries < 0:
        raise ValueError("--retries не может быть отрицательным.")
    if max_pages < 0:
        raise ValueError("--max-pages не может быть отрицательным.")


def sync_pages_from_confluence(
    client: Confluence,
    *,
    base_url: str,
    space_key: str,
    batch_size: int,
    start: int,
    retries: int,
    max_pages: int,
    on_batch_progress: Callable[[int], None] | None = None,
) -> SyncPagesResult:
    validate_sync_pages_options(batch_size, start, retries, max_pages)

    created_count = 0
    updated_count = 0
    skipped_empty_count = 0
    seen_count = 0

    pages = iter_confluence_pages(
        client,
        space_key,
        batch_size=batch_size,
        start=start,
        max_pages=max_pages,
        retries=retries,
    )
    for page in pages:
        seen_count += 1

        record = confluence_page_to_record(page, base_url)
        if not record["body_text"]:
            skipped_empty_count += 1

        defaults = {
            key: value for key, value in record.items() if key != "confluence_id"
        }
        defaults["synced_at"] = timezone.now()

        with transaction.atomic():
            _, created = ConfluencePage.objects.update_or_create(
                confluence_id=record["confluence_id"],
                defaults=defaults,
            )

        if created:
            created_count += 1
        else:
            updated_count += 1

        if on_batch_progress and seen_count % batch_size == 0:
            on_batch_progress(seen_count)

    return SyncPagesResult(
        seen_count=seen_count,
        created_count=created_count,
        updated_count=updated_count,
        skipped_empty_count=skipped_empty_count,
    )
