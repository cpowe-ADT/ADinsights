"""OpenAI image generation adapter."""

from __future__ import annotations

import base64
import binascii

import httpx

from .base import ProviderUsage
from .image_base import BaseHTTPImageProvider, GeneratedImage


class OpenAIImageProvider(BaseHTTPImageProvider):
    """Image provider backed by the OpenAI images API (b64_json responses)."""

    provider_name = "openai"

    def _invoke(
        self, *, prompt: str, count: int, size: str
    ) -> tuple[list[GeneratedImage], ProviderUsage]:
        url = f"{self.base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "prompt": prompt,
            "n": max(int(count), 1),
            "size": size,
            "response_format": "b64_json",
        }
        response = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        images: list[GeneratedImage] = []
        for item in data.get("data", []):
            encoded = item.get("b64_json") if isinstance(item, dict) else None
            if not encoded:
                continue
            try:
                content = base64.b64decode(encoded)
            except (binascii.Error, ValueError):
                continue
            images.append(
                GeneratedImage(
                    content=content,
                    mime_type="image/png",
                    seed=str(item.get("seed") or ""),
                )
            )
        usage_raw = data.get("usage") or {}
        usage = ProviderUsage(
            provider=self.provider_name,
            model=str(self.model or ""),
            input_tokens=int(usage_raw.get("input_tokens") or 0),
            output_tokens=int(usage_raw.get("output_tokens") or 0),
            images=len(images),
        )
        return images, usage


__all__ = ["OpenAIImageProvider"]
