from __future__ import annotations

import logging
from typing import Optional

from celery import shared_task
from django.utils import timezone

from core.crypto.dek_manager import rotate_all_tenant_deks
from accounts.tenant_context import (
    set_current_tenant_id,
    clear_current_tenant,
)
from accounts.audit import log_audit_event
from accounts.models import Tenant, User
from integrations.airbyte import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
    AirbyteSyncService,
)
from integrations.models import AirbyteConnection, PlatformCredential

logger = logging.getLogger(__name__)


@shared_task
def rotate_deks() -> str:
    rotated = rotate_all_tenant_deks()
    return f"rotated {rotated} tenant keys"


def _resolve_user(user_id: Optional[str]) -> Optional[User]:
    if not user_id:
        return None
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def _sync_provider_connections(
    task,
    *,
    tenant: Tenant,
    user: Optional[User],
    provider: str,
) -> str:
    task_id = getattr(getattr(task, "request", None), "id", None)
    tenant_id_str = str(tenant.id)
    base_extra = {
        "tenant_id": tenant_id_str,
        "provider": provider,
        "task_id": str(task_id) if task_id else None,
    }
    set_current_tenant_id(tenant_id_str)
    try:
        connections = list(
            AirbyteConnection.objects.filter(
                tenant=tenant,
                provider=provider,
                is_active=True,
            ).select_related("tenant")
        )
        if not connections:
            logger.info(
                "No Airbyte connections configured for provider",
                extra={**base_extra, "connection_count": 0},
            )
            return "no_connections"

        now = timezone.now()
        due_connections = [connection for connection in connections if connection.should_trigger(now)]
        if not due_connections:
            logger.info(
                "No Airbyte connections due for sync",
                extra={
                    **base_extra,
                    "connection_count": len(connections),
                    "connection_ids": [str(connection.connection_id) for connection in connections],
                },
            )
            return "no_due_connections"

        try:
            with AirbyteClient.from_settings() as client:
                service = AirbyteSyncService(client)
                triggered = service.sync_connections(due_connections, triggered_at=now)
        except AirbyteClientConfigurationError as exc:
            logger.error(
                "Airbyte client misconfigured",
                extra=base_extra,
                exc_info=exc,
            )
            raise task.retry(exc=exc, countdown=300)
        except AirbyteClientError as exc:
            logger.warning(
                "Airbyte sync failed",
                extra={
                    **base_extra,
                    "connection_ids": [str(connection.connection_id) for connection in due_connections],
                },
                exc_info=exc,
            )
            raise task.retry(exc=exc)

        if triggered == 0:
            logger.info(
                "Airbyte sync service returned without triggering connections",
                extra=base_extra,
            )
            return "no_due_connections"

        connections_meta = [
            {
                "connection_id": str(connection.connection_id),
                "name": connection.name,
                "job_id": connection.last_job_id or None,
                "job_status": connection.last_job_status or None,
            }
            for connection in due_connections
        ]

        logger.info(
            "Airbyte connections triggered",
            extra={
                **base_extra,
                "triggered": triggered,
                "connection_ids": [meta["connection_id"] for meta in connections_meta],
            },
        )

        log_audit_event(
            tenant=tenant,
            user=user,
            action="sync_triggered",
            resource_type="sync",
            resource_id=provider,
            metadata={
                "provider": provider,
                "triggered": triggered,
                "connection_ids": [meta["connection_id"] for meta in connections_meta],
                "job_ids": [meta["job_id"] for meta in connections_meta if meta["job_id"]],
                "task_id": str(task_id) if task_id else None,
            },
        )
        return f"triggered {triggered} {provider.lower()} connection(s)"
    finally:
        clear_current_tenant()


@shared_task(bind=True, max_retries=5)
def sync_meta_metrics(self, tenant_id: str, triggered_by_user_id: Optional[str] = None) -> str:
    tenant = Tenant.objects.get(id=tenant_id)
    user = _resolve_user(triggered_by_user_id)
    return _sync_provider_connections(self, tenant=tenant, user=user, provider=PlatformCredential.META)


@shared_task(bind=True, max_retries=5)
def sync_google_metrics(self, tenant_id: str, triggered_by_user_id: Optional[str] = None) -> str:
    tenant = Tenant.objects.get(id=tenant_id)
    user = _resolve_user(triggered_by_user_id)
    return _sync_provider_connections(self, tenant=tenant, user=user, provider=PlatformCredential.GOOGLE)
