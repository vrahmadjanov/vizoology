from __future__ import annotations

"""
Подключение к Confluence: клиент REST API (atlassian-python-api).
"""

from atlassian import Confluence
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ConfluenceClient:
    """Точка входа для работы с Confluence"""

    def __init__(self, *, require_space_key: bool = False) -> None:
        missing = []
        if not settings.CONFLUENCE_BASE_URL:
            missing.append("CONFLUENCE_BASE_URL")
        if not settings.CONFLUENCE_USERNAME:
            missing.append("CONFLUENCE_USERNAME")
        if not settings.CONFLUENCE_API_TOKEN:
            missing.append("CONFLUENCE_API_TOKEN")
        if require_space_key and not settings.CONFLUENCE_SPACE_KEY:
            missing.append("CONFLUENCE_SPACE_KEY")

        if missing:
            raise ImproperlyConfigured(
                "Не настроено подключение к Confluence. Заполните переменные: "
                + ", ".join(missing)
                + "."
            )

        self._api = Confluence(
            url=settings.CONFLUENCE_BASE_URL,
            username=settings.CONFLUENCE_USERNAME,
            password=settings.CONFLUENCE_API_TOKEN,
        )

    @property
    def api(self) -> Confluence:
        """Низкоуровневый клиент ``atlassian.Confluence`` (REST-вызовы)."""
        return self._api
