"""Anthropic (Claude) caption provider adapter."""

from __future__ import annotations

import httpx

from .base import BaseHTTPCaptionProvider, ProviderUsage

DEFAULT_MAX_TOKENS = 1200
DEFAULT_TEMPERATURE = 0.4


class AnthropicCaptionProvider(BaseHTTPCaptionProvider):
    """Caption provider backed by the Anthropic Messages API."""

    provider_name = "anthropic"

    def __init__(self, *, anthropic_version: str = "2023-06-01", **kwargs) -> None:
        super().__init__(**kwargs)
        self.anthropic_version = anthropic_version

    def _invoke(self, *, system: str, user: str) -> tuple[str, ProviderUsage]:
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "temperature": DEFAULT_TEMPERATURE,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        response = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        )
        usage_raw = data.get("usage") or {}
        usage = ProviderUsage(
            provider=self.provider_name,
            model=str(self.model or ""),
            input_tokens=int(usage_raw.get("input_tokens") or 0),
            output_tokens=int(usage_raw.get("output_tokens") or 0),
        )
        return text, usage


__all__ = ["AnthropicCaptionProvider"]
