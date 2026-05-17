from __future__ import annotations

from typing import Any


def get_accessible_space_summaries(api: Any, *, page_size: int = 50) -> list[dict[str, str]]:
    """
    Все пространства Confluence, видимые текущему пользователю API (постраничный обход).

    Возвращает отсортированный по ключу список словарей ``{"key", "name"}``.
    """
    start = 0
    summaries: list[dict[str, str]] = []
    while True:
        data = api.get_all_spaces(start=start, limit=page_size)
        results = data.get("results", []) if isinstance(data, dict) else []
        if not results:
            break
        for space in results:
            summaries.append(
                {
                    "key": str(space.get("key", "") or ""),
                    "name": str(space.get("name", "") or ""),
                }
            )
        if len(results) < page_size:
            break
        start += page_size

    summaries.sort(key=lambda s: s["key"].lower())
    return summaries
