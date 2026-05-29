"""Notification delivery for analytics workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from django.utils import timezone

from accounts.audit import log_audit_event
from accounts.email import EmailPayload, send_email
from accounts.models import AuditLog, Tenant
from integrations.models import NotificationChannel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailySummaryDelivery:
    outcome: str
    recipient_count: int
    provider_result: str = ""


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _summary_recipients(tenant: Tenant) -> list[str]:
    recipients: set[str] = set()
    channels = NotificationChannel.objects.filter(
        tenant=tenant,
        channel_type=NotificationChannel.CHANNEL_EMAIL,
        is_active=True,
    )
    for channel in channels:
        config = channel.config or {}
        recipients.update(_as_string_list(config.get("emails") or config.get("to")))
    return sorted(recipients)


def _delivery_already_succeeded(*, tenant: Tenant, generated_at: datetime) -> bool:
    return AuditLog.all_objects.filter(
        tenant=tenant,
        action="daily_summary_email_delivery",
        resource_type="daily_summary",
        metadata__generated_at=generated_at.isoformat(),
        metadata__delivery="delivered",
    ).exists()


def send_daily_summary_email(
    *,
    tenant: Tenant,
    summary: str,
    generated_at: datetime,
    status: str,
) -> DailySummaryDelivery:
    """Deliver one aggregate summary to active tenant email channels."""

    generated_at = (
        timezone.make_aware(generated_at)
        if timezone.is_naive(generated_at)
        else generated_at
    )
    recipients = _summary_recipients(tenant)
    provider_result = ""
    if _delivery_already_succeeded(tenant=tenant, generated_at=generated_at):
        outcome = "delivered"
        provider_result = "already_delivered"
    elif not recipients:
        outcome = "skipped_no_recipients"
    else:
        try:
            provider_result = send_email(
                EmailPayload(
                    subject=f"[ADinsights] Daily summary - {generated_at.date().isoformat()}",
                    body=summary,
                    to=recipients,
                )
            )
        except Exception:  # pragma: no cover - defensive provider isolation
            logger.exception(
                "metrics.daily_summary.email_failed",
                extra={"tenant_id": str(tenant.id), "recipient_count": len(recipients)},
            )
            provider_result = "error"
        outcome = "delivered" if provider_result in {"sent", "logged"} else "failed"

    logger.info(
        "metrics.daily_summary.email_delivery",
        extra={
            "tenant_id": str(tenant.id),
            "generated_at": generated_at.isoformat(),
            "status": status,
            "delivery": outcome,
            "recipient_count": len(recipients),
            "provider_result": provider_result,
        },
    )

    log_audit_event(
        tenant=tenant,
        user=None,
        action="daily_summary_email_delivery",
        resource_type="daily_summary",
        resource_id=str(tenant.id),
        metadata={
            "generated_at": generated_at.isoformat(),
            "status": status,
            "delivery": outcome,
            "recipient_count": len(recipients),
            "provider_result": provider_result,
        },
    )
    return DailySummaryDelivery(
        outcome=outcome,
        recipient_count=len(recipients),
        provider_result=provider_result,
    )


__all__ = ["DailySummaryDelivery", "send_daily_summary_email"]
