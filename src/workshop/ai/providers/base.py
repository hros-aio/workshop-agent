"""Shared OpenAI-compatible structured-output helper.

OpenAI and local Qwen (vLLM OpenAI-compatible endpoint) differ only by base_url
and credentials, so both adapters share this implementation. instructor coerces
the response into a pydantic schema and raises if the model cannot comply; the
orchestrator treats that exactly like a provider failure.
"""

from __future__ import annotations

from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from workshop.settings import get_settings

ModelT = TypeVar("ModelT", bound=BaseModel)


class OpenAICompatibleClient:
    def __init__(self, *, model: str, api_key: str, base_url: str | None = None) -> None:
        self.model = model
        self._client: Any = None
        self._api_key = api_key
        self._base_url = base_url

    def _get_client(self) -> Any:
        if self._client is None:
            import instructor

            raw = OpenAI(api_key=self._api_key, base_url=self._base_url)
            self._client = instructor.from_openai(raw)
        return self._client

    def _complete(self, *, response_model: type[ModelT], system: str, user: str) -> ModelT:
        settings = get_settings()
        client = self._get_client()
        last_error: Exception | None = None
        for _attempt in range(settings.ai_max_retries + 1):
            try:
                result: ModelT = client.chat.completions.create(
                    model=self.model,
                    response_model=response_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return result
            except Exception as exc:  # provider or schema failure
                last_error = exc
        raise RuntimeError(f"AI request failed after retries: {last_error}") from last_error
