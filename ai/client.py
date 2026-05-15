from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from google import genai


@dataclass(frozen=True)
class GeminiResponse:
    text: str
    model: str


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        self.api_key = (api_key or settings.GEMINI_API_KEY).strip()
        self.model_name = (model_name or settings.GEMINI_MODEL_NAME).strip()

        if not self.api_key:
            raise ImproperlyConfigured("Заполните GEMINI_API_KEY в .env.")
        if not self.model_name:
            raise ImproperlyConfigured("Заполните GEMINI_MODEL_NAME в .env.")

        self.client = genai.Client(api_key=self.api_key)

    def generate_text(self, prompt: str) -> GeminiResponse:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt не может быть пустым.")

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return GeminiResponse(text=(response.text or "").strip(), model=self.model_name)