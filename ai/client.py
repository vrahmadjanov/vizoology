from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from openai import OpenAI


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model: str


class DeepSeekClient:
    """Клиент генерации через DeepSeek OpenAI-compatible API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = (api_key or settings.DEEPSEEK_API_KEY).strip()
        self.model_name = (model_name or settings.DEEPSEEK_MODEL_NAME).strip()
        self.base_url = (base_url or settings.DEEPSEEK_API_BASE).strip()

        if not self.api_key:
            raise ImproperlyConfigured("Заполните DEEPSEEK_API_KEY в .env.")
        if not self.model_name:
            raise ImproperlyConfigured("Заполните DEEPSEEK_MODEL_NAME в .env.")
        if not self.base_url:
            raise ImproperlyConfigured("Заполните DEEPSEEK_API_BASE в .env.")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate_text(self, prompt: str) -> LlmResponse:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt не может быть пустым.")

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content
        text = (raw or "").strip()
        model_label = getattr(response, "model", "") or ""
        model_label = model_label.strip() or self.model_name
        return LlmResponse(text=text, model=model_label)
