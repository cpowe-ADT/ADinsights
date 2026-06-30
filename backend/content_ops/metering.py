"""Tenant AI usage metering and monthly token caps for Content Operations.

Tokens are the billable unit. This module records one ``AIUsageRecord`` per
provider call that reports usage, and enforces an optional per-tenant monthly
token cap before a live provider is invoked. Metering must never break the
generation flow, so callers treat recording as best-effort.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import AIUsageRecord

logger = logging.getLogger(__name__)


def monthly_token_cap() -> int:
    """Return the configured per-tenant monthly token cap (0 = unlimited)."""

    try:
        return max(int(getattr(settings, "CONTENT_OPS_TENANT_MONTHLY_TOKEN_CAP", 0) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _month_start(now=None):
    now = now or timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def tenant_month_token_usage(*, tenant, now=None) -> int:
    """Total tokens billed to a tenant for the current calendar month."""

    aggregate = AIUsageRecord.all_objects.filter(
        tenant=tenant,
        created_at__gte=_month_start(now),
    ).aggregate(total=Sum("total_tokens"))
    return int(aggregate["total"] or 0)


def tenant_over_token_cap(*, tenant, now=None) -> bool:
    """Return True when a tenant has reached the configured monthly token cap."""

    cap = monthly_token_cap()
    if cap <= 0:
        return False
    return tenant_month_token_usage(tenant=tenant, now=now) >= cap


def _decimal_setting(name: str) -> Decimal:
    try:
        rate = Decimal(str(getattr(settings, name, "0") or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return rate if rate > 0 else Decimal("0")


def _token_rate(provider: str) -> Decimal:
    if provider == "openai":
        return _decimal_setting("CONTENT_OPS_OPENAI_USD_PER_1K_TOKENS")
    if provider == "anthropic":
        return _decimal_setting("CONTENT_OPS_ANTHROPIC_USD_PER_1K_TOKENS")
    return Decimal("0")


def _image_rate(provider: str) -> Decimal:
    if provider == "openai":
        return _decimal_setting("CONTENT_OPS_OPENAI_USD_PER_IMAGE")
    return Decimal("0")


def estimate_cost(*, provider: str, total_tokens: int, images: int = 0) -> Decimal:
    """Best-effort USD cost from configured per-1k-token and per-image rates."""

    cost = Decimal("0")
    token_rate = _token_rate(provider)
    if token_rate > 0 and total_tokens > 0:
        cost += (Decimal(int(total_tokens)) / Decimal(1000)) * token_rate
    image_rate = _image_rate(provider)
    if image_rate > 0 and images > 0:
        cost += Decimal(int(images)) * image_rate
    return cost


def record_ai_usage(*, job, usage: Any) -> AIUsageRecord | None:
    """Persist a usage record for one provider call. Returns None when no usage."""

    if usage is None:
        return None
    provider = str(getattr(usage, "provider", "") or "")[:64]
    model_name = str(getattr(usage, "model", "") or "")[:128]
    input_tokens = max(int(getattr(usage, "input_tokens", 0) or 0), 0)
    output_tokens = max(int(getattr(usage, "output_tokens", 0) or 0), 0)
    images = max(int(getattr(usage, "images", 0) or 0), 0)
    total_tokens = input_tokens + output_tokens
    return AIUsageRecord.all_objects.create(
        tenant=job.tenant,
        generation_job=job,
        provider=provider,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        images=images,
        estimated_cost=estimate_cost(
            provider=provider, total_tokens=total_tokens, images=images
        ),
    )


__all__ = [
    "estimate_cost",
    "monthly_token_cap",
    "record_ai_usage",
    "tenant_month_token_usage",
    "tenant_over_token_cap",
]
