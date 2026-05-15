from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from atlassian import Confluence
from django.db import transaction
from django.utils import timezone

from confluence.models import ConfluencePage
from confluence.services.core import confluence_page_to_record, iter_confluence_pages


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
