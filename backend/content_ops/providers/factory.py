"""Caption provider selection.

Selection order:
1. A per-tenant override (enterprise bring-your-own-key) — seam reserved, not
   yet implemented; see :func:`_tenant_override`.
2. The platform-default provider chosen by ``CONTENT_OPS_TEXT_PROVIDER``.
3. The disabled provider, which fails closed (no live AI calls).
"""

from __future__ import annotations

from django.conf import settings

from ..generation import DisabledCaptionGenerationProvider
from .anthropic_caption import AnthropicCaptionProvider
from .openai_caption import OpenAICaptionProvider


def get_caption_provider(*, tenant=None):
    """Return the caption provider for a tenant, defaulting to disabled."""

    override = _tenant_override(tenant)
    if override is not None:
        return override

    provider_key = str(
        getattr(settings, "CONTENT_OPS_TEXT_PROVIDER", "disabled") or "disabled"
    ).strip().lower()
    timeout = float(getattr(settings, "CONTENT_OPS_TEXT_TIMEOUT", 30.0))

    if provider_key == "openai":
        return OpenAICaptionProvider(
            api_key=getattr(settings, "CONTENT_OPS_OPENAI_API_KEY", None),
            model=getattr(settings, "CONTENT_OPS_OPENAI_MODEL", ""),
            base_url=getattr(settings, "CONTENT_OPS_OPENAI_BASE_URL", ""),
            timeout=timeout,
        )
    if provider_key == "anthropic":
        return AnthropicCaptionProvider(
            api_key=getattr(settings, "CONTENT_OPS_ANTHROPIC_API_KEY", None),
            model=getattr(settings, "CONTENT_OPS_ANTHROPIC_MODEL", ""),
            base_url=getattr(settings, "CONTENT_OPS_ANTHROPIC_BASE_URL", ""),
            timeout=timeout,
            anthropic_version=getattr(
                settings, "CONTENT_OPS_ANTHROPIC_VERSION", "2023-06-01"
            ),
        )
    return DisabledCaptionGenerationProvider()


def _tenant_override(tenant):
    """Enterprise bring-your-own-key seam.

    Reserved for tenants that store their own encrypted provider key. Returns
    None today, so every tenant uses the metered platform-default provider.
    The encrypted per-tenant credential model is a follow-up increment.
    """

    return None


__all__ = ["get_caption_provider"]
