"""Image generation provider selection (mirrors the caption factory).

Selection order: per-tenant override (enterprise BYO key — seam reserved) →
the platform-default provider chosen by ``CONTENT_OPS_IMAGE_PROVIDER`` → the
disabled provider, which fails closed (no live render spend).
"""

from __future__ import annotations

from django.conf import settings

from ..image_generation import DisabledImageGenerationProvider
from .openai_image import OpenAIImageProvider


def get_image_provider(*, tenant=None):
    """Return the image provider for a tenant, defaulting to disabled."""

    override = _tenant_override(tenant)
    if override is not None:
        return override

    provider_key = str(
        getattr(settings, "CONTENT_OPS_IMAGE_PROVIDER", "disabled") or "disabled"
    ).strip().lower()
    if provider_key == "openai":
        return OpenAIImageProvider(
            api_key=getattr(settings, "CONTENT_OPS_OPENAI_API_KEY", None),
            model=getattr(settings, "CONTENT_OPS_OPENAI_IMAGE_MODEL", ""),
            base_url=getattr(settings, "CONTENT_OPS_OPENAI_BASE_URL", ""),
            timeout=float(getattr(settings, "CONTENT_OPS_IMAGE_TIMEOUT", 60.0)),
            default_size=getattr(settings, "CONTENT_OPS_OPENAI_IMAGE_SIZE", "1024x1024"),
        )
    return DisabledImageGenerationProvider()


def _tenant_override(tenant):
    """Enterprise bring-your-own-key seam (returns None today)."""

    return None


__all__ = ["get_image_provider"]
