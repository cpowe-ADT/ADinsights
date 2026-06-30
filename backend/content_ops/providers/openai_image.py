"""OpenAI image generation adapter."""

from __future__ import annotations

import base64
import binascii

import httpx

from .base import ProviderUsage
from .image_base import BaseHTTPImageProvider, GeneratedImage


def _sniff_image_mime(content: bytes) -> str:
    """Detect the real image mime from magic bytes (providers vary the format)."""

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/png"


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
        model_name = str(self.model or "").lower()
        body = {
            "model": self.model,
            "prompt": prompt,
            # dall-e-3 only supports n=1; other models accept the requested count.
            "n": 1 if model_name.startswith("dall-e-3") else max(int(count), 1),
            "size": size,
        }
        # dall-e-* needs response_format to return base64; gpt-image-1 returns
        # b64_json natively and rejects the parameter (HTTP 400).
        if model_name.startswith("dall-e"):
            body["response_format"] = "b64_json"
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
                    mime_type=_sniff_image_mime(content),
                    seed=str(item.get("seed") or ""),
                )
            )
        # Image generation is metered as images, not tokens, so it never counts
        # against the text token cap. Per-image cost is applied from settings.
        usage = ProviderUsage(
            provider=self.provider_name,
            model=str(self.model or ""),
            input_tokens=0,
            output_tokens=0,
            images=len(images),
        )
        return images, usage


__all__ = ["OpenAIImageProvider"]
