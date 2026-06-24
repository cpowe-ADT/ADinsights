"""OpenAI (ChatGPT) caption provider adapter."""

from __future__ import annotations

import httpx

from .base import BaseHTTPCaptionProvider, ProviderUsage

DEFAULT_MAX_TOKENS = 1200
DEFAULT_TEMPERATURE = 0.4


def _is_reasoning_model(model: str) -> bool:
    """GPT-5 / o-series models require max_completion_tokens and reject custom
    temperature (the chat completions API 400s on max_tokens / temperature!=1)."""

    name = str(model or "").lower()
    return name.startswith(("gpt-5", "o1", "o3", "o4"))


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
            "response_format": {"type": "json_object"},
        }
        if _is_reasoning_model(self.model):
            body["max_completion_tokens"] = DEFAULT_MAX_TOKENS
        else:
            body["max_tokens"] = DEFAULT_MAX_TOKENS
            body["temperature"] = DEFAULT_TEMPERATURE
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
