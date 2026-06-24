"""Vendor-neutral image/video generation provider boundary.

Concrete adapters subclass :class:`BaseHTTPImageProvider` and implement
:meth:`_invoke` for their wire protocol. The interface is media-agnostic — a
future video adapter slots in the same way — and returns raw bytes plus the
mime type so the storage layer can validate and quarantine output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..image_generation import (
    IMAGE_FAILURE_PROVIDER_ERROR,
    IMAGE_FAILURE_PROVIDER_NOT_CONFIGURED,
    ImageGenerationError,
)
from .base import ProviderUsage


@dataclass
class GeneratedImage:
    """One generated media item returned by a provider."""

    content: bytes
    mime_type: str = "image/png"
    width: int | None = None
    height: int | None = None
    seed: str = ""


class BaseHTTPImageProvider:
    """Shared HTTP image provider; subclasses implement :meth:`_invoke`."""

    provider_name = "base"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        base_url: str | None,
        timeout: float,
        default_size: str = "1024x1024",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = float(timeout)
        self.default_size = default_size
        self.last_usage: ProviderUsage | None = None

    def is_enabled(self) -> bool:
        return bool(self.api_key and self.model and self.base_url)

    def generate(self, payload: dict[str, Any]) -> list[GeneratedImage]:
        if not self.is_enabled():
            raise ImageGenerationError(
                code=IMAGE_FAILURE_PROVIDER_NOT_CONFIGURED,
                detail_safe="Image generation provider is not configured.",
            )
        prompt = str(payload.get("prompt") or "").strip()
        count = int(payload.get("count") or 1)
        size = str(payload.get("size") or self.default_size)
        try:
            images, usage = self._invoke(prompt=prompt, count=count, size=size)
        except ImageGenerationError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise ImageGenerationError(
                code=IMAGE_FAILURE_PROVIDER_ERROR,
                detail_safe="Image provider request failed.",
            ) from exc
        self.last_usage = usage
        return images

    def _invoke(
        self, *, prompt: str, count: int, size: str
    ) -> tuple[list[GeneratedImage], ProviderUsage]:
        raise NotImplementedError


__all__ = ["BaseHTTPImageProvider", "GeneratedImage"]
