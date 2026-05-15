from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from atlassian import Confluence
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class ConfluenceConnectionSettings:
    base_url: str
    username: str
    api_token: str
    space_key: str = ""


@dataclass(frozen=True)
class TextChunk:
    position: int
    text: str
    char_start: int
    char_end: int
    text_hash: str


def get_confluence_settings(*, require_space_key: bool = False) -> ConfluenceConnectionSettings:
    connection_settings = ConfluenceConnectionSettings(
        base_url=settings.CONFLUENCE_BASE_URL,
        username=settings.CONFLUENCE_USERNAME,
        api_token=settings.CONFLUENCE_API_TOKEN,
        space_key=settings.CONFLUENCE_SPACE_KEY,
    )
    missing = []
    if not connection_settings.base_url:
        missing.append("CONFLUENCE_BASE_URL")
    if not connection_settings.username:
        missing.append("CONFLUENCE_USERNAME")
    if not connection_settings.api_token:
        missing.append("CONFLUENCE_API_TOKEN")
    if require_space_key and not connection_settings.space_key:
        missing.append("CONFLUENCE_SPACE_KEY")

    if missing:
        raise ImproperlyConfigured(
            "Не настроено подключение к Confluence. Заполните переменные: "
            + ", ".join(missing)
            + "."
        )
    return connection_settings


def get_confluence_client() -> Confluence:
    connection_settings = get_confluence_settings()
    return Confluence(
        url=connection_settings.base_url,
        username=connection_settings.username,
        password=connection_settings.api_token,
    )


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
    for attempt in range(retries + 1):
        try:
            return client.get_all_pages_from_space_raw(
                space=space_key,
                start=start,
                limit=limit,
                expand=expand,
            )
        except Exception:
            if attempt >= retries:
                raise
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
        except Exception:
            if attempt >= retries:
                raise
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


def split_text_into_chunks(text: str, *, max_chars: int = 1800) -> list[TextChunk]:
    if max_chars < 200:
        raise ValueError("max_chars должен быть не меньше 200.")

    blocks = _text_blocks_with_offsets(text)
    chunks: list[TextChunk] = []
    current_parts: list[tuple[str, int, int]] = []

    for block in blocks:
        block_text, _, _ = block
        current_text = _join_chunk_parts(current_parts)
        separator_len = 2 if current_text else 0
        projected_len = len(current_text) + separator_len + len(block_text)

        if current_parts and projected_len > max_chars:
            chunks.append(_make_text_chunk(len(chunks), current_parts))
            current_parts = []

        if len(block_text) <= max_chars:
            current_parts.append(block)
            continue

        for part in _split_large_block(block, max_chars=max_chars):
            if current_parts:
                chunks.append(_make_text_chunk(len(chunks), current_parts))
                current_parts = []
            chunks.append(_make_text_chunk(len(chunks), [part]))

    if current_parts:
        chunks.append(_make_text_chunk(len(chunks), current_parts))

    return chunks


def _text_blocks_with_offsets(text: str) -> list[tuple[str, int, int]]:
    blocks = []
    cursor = 0
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            cursor += len(raw_line) + 1
            continue

        start = text.find(stripped, cursor)
        if start == -1:
            start = cursor
        end = start + len(stripped)
        blocks.append((stripped, start, end))
        cursor = end
    return blocks


def _split_large_block(
    block: tuple[str, int, int],
    *,
    max_chars: int,
) -> list[tuple[str, int, int]]:
    block_text, block_start, _ = block
    parts = []
    offset = 0

    while offset < len(block_text):
        end = min(offset + max_chars, len(block_text))
        if end < len(block_text):
            whitespace_at = block_text.rfind(" ", offset, end)
            if whitespace_at > offset:
                end = whitespace_at

        part_text = block_text[offset:end].strip()
        if part_text:
            part_start = block_start + offset + len(block_text[offset:end]) - len(block_text[offset:end].lstrip())
            parts.append((part_text, part_start, part_start + len(part_text)))
        offset = end
        while offset < len(block_text) and block_text[offset].isspace():
            offset += 1

    return parts


def _join_chunk_parts(parts: list[tuple[str, int, int]]) -> str:
    return "\n\n".join(part[0] for part in parts).strip()


def _make_text_chunk(position: int, parts: list[tuple[str, int, int]]) -> TextChunk:
    chunk_text = _join_chunk_parts(parts)
    return TextChunk(
        position=position,
        text=chunk_text,
        char_start=parts[0][1],
        char_end=parts[-1][2],
        text_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
    )


def page_body_to_plain_text(page: dict[str, Any]) -> str:
    body = page.get("body") or {}
    for key in ("view", "storage"):
        block = body.get(key) or {}
        raw_html = block.get("value")
        if raw_html:
            return html_to_plain_text(raw_html)
    return ""


def html_to_plain_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_confluence_results(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        results = response.get("results", [])
        return results if isinstance(results, list) else list(results)
    if isinstance(response, list):
        return response
    if hasattr(response, "__iter__") and not isinstance(response, (str, bytes)):
        return list(response)
    return []
