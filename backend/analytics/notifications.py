"""Notification stubs for analytics workflows."""

from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from accounts.audit import log_audit_event
from accounts.models import Tenant

logger = logging.getLogger(__name__)


def send_daily_summary_email(
    *,
    tenant: Tenant,
    summary: str,
    generated_at: datetime,
    status: str,
) -> None:
    """Stubbed delivery for daily summaries (no external email provider yet)."""

    generated_at = (
        timezone.make_aware(generated_at)
        if timezone.is_naive(generated_at)
        else generated_at
    )

    logger.info(
        "metrics.daily_summary.email_stubbed",
        extra={
            "tenant_id": str(tenant.id),
            "generated_at": generated_at.isoformat(),
            "summary_length": len(summary or ""),
            "status": status,
        },
    )

    log_audit_event(
        tenant=tenant,
        user=None,
        action="daily_summary_email_stubbed",
        resource_type="daily_summary",
        resource_id=str(tenant.id),
        metadata={
            "generated_at": generated_at.isoformat(),
            "summary_length": len(summary or ""),
            "status": status,
            "delivery": "stub",
        },
    )


__all__ = ["send_daily_summary_email"]
