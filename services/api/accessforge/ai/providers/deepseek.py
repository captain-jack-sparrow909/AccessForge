"""DeepSeek adapter using its OpenAI-compatible Chat Completions API."""

from __future__ import annotations

import httpx

from accessforge.ai.providers.models import CompletionRequest
from accessforge.ai.providers.openai_compatible import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek text/JSON-mode adapter that discards reasoning output."""

    provider_type = "deepseek"
    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
            provider_type=self.provider_type,
        )

    def _completion_payload(self, request: CompletionRequest) -> dict[str, object]:
        payload = super()._completion_payload(request)
        # AccessForge never persists or displays private reasoning traces.
        payload["thinking"] = {"type": "disabled"}
        return payload
