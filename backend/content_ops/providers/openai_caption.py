"""OpenAI (ChatGPT) caption provider adapter."""

from __future__ import annotations

import httpx

from .base import BaseHTTPCaptionProvider, ProviderUsage

DEFAULT_MAX_TOKENS = 1200
DEFAULT_TEMPERATURE = 0.4


class OpenAICaptionProvider(BaseHTTPCaptionProvider):
    """Caption provider backed by the OpenAI chat completions API."""

    provider_name = "openai"

    def _invoke(self, *, system: str, user: str) -> tuple[str, ProviderUsage]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }
        response = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage_raw = data.get("usage") or {}
        usage = ProviderUsage(
            provider=self.provider_name,
            model=str(self.model or ""),
            input_tokens=int(usage_raw.get("prompt_tokens") or 0),
            output_tokens=int(usage_raw.get("completion_tokens") or 0),
        )
        return text, usage


__all__ = ["OpenAICaptionProvider"]
