"""Celery tasks for integrations."""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import List

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from alerts.models import AlertRun
from accounts.tenant_context import tenant_context

from integrations.airbyte import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
    AirbyteSyncService,
)
from integrations.models import AirbyteConnection, PlatformCredential

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(AirbyteClientError,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def trigger_scheduled_airbyte_syncs(self):  # noqa: ANN001
    """Trigger due Airbyte syncs using the shared scheduling service."""

    triggered = 0
    with tenant_context(None):
        try:
            with AirbyteClient.from_settings() as client:
                service = AirbyteSyncService(client)
                updates = service.sync_due_connections()
                AirbyteConnection.persist_sync_updates(updates)
                triggered = len(updates)
        except AirbyteClientConfigurationError as exc:
            logger.error("Airbyte client misconfigured", exc_info=exc)
            raise self.retry(exc=exc, countdown=60)
    return triggered


@shared_task(bind=True)
def remind_expiring_credentials(self):  # noqa: ANN001
    """Create alert runs for credentials nearing expiry."""

    window_days = getattr(settings, "CREDENTIAL_ROTATION_REMINDER_DAYS", 7)
    now = timezone.now()
    window_end = now + timedelta(days=window_days)

    with tenant_context(None):
        credentials = list(
            PlatformCredential.all_objects.filter(
                expires_at__isnull=False,
                expires_at__lte=window_end,
            ).select_related("tenant")
        )

    if not credentials:
        return {"processed": 0}

    rows: List[dict[str, object]] = []
    for credential in credentials:
        expires_at = credential.expires_at
        if expires_at is None:
            continue
        tenant_id = str(credential.tenant_id)
        with tenant_context(tenant_id):
            delta = (expires_at - now).days
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "provider": credential.provider,
                    "credential_ref": _mask_identifier(credential.account_id),
                    "expires_at": expires_at.isoformat(),
                    "days_until_expiry": delta,
                    "status": "expired" if expires_at <= now else "expiring",
                }
            )

    AlertRun.objects.create(
        rule_slug="credential_rotation_due",
        status=AlertRun.Status.SUCCESS,
        row_count=len(rows),
        raw_results=rows,
        llm_summary=f"{len(rows)} credential(s) require rotation.",
        error_message="",
    )

    return {"processed": len(rows)}


def _mask_identifier(value: str | None) -> str:
    if not value:
        return "ref_unknown"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"ref_{digest}"
