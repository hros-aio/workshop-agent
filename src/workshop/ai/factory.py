"""Provider factory: resolves an AIClient from a project's ai_provider setting."""

from __future__ import annotations

from workshop.ai.client import AIClient
from workshop.common.enums import AIProvider
from workshop.common.errors import DomainValidationError


def for_provider(provider: str) -> AIClient:
    if provider == AIProvider.OPENAI.value:
        from workshop.ai.providers.openai_client import OpenAIClient

        return OpenAIClient()
    if provider == AIProvider.LOCAL_QWEN.value:
        from workshop.ai.providers.local_qwen_client import LocalQwenClient

        return LocalQwenClient()
    raise DomainValidationError(f"Unsupported AI provider: {provider}")
