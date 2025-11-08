from __future__ import annotations

import logging
from typing import Optional

from celery import shared_task
from django.utils import timezone

from core.crypto.dek_manager import rotate_all_tenant_deks
from accounts.tenant_context import tenant_context
from accounts.audit import log_audit_event
from accounts.models import Tenant, User
from integrations.airbyte import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
    AirbyteSyncService,
)
from integrations.models import AirbyteConnection, PlatformCredential
from core.metrics import observe_airbyte_sync

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
    with tenant_context(tenant_id_str):
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
                updates = service.sync_connections(due_connections, triggered_at=now)
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

        if not updates:
            logger.info(
                "Airbyte sync service returned without triggering connections",
                extra=base_extra,
            )
            return "no_due_connections"

        persisted_connections = AirbyteConnection.persist_sync_updates(updates)
        triggered = len(updates)

        connections_meta = []
        for update in updates:
            connection = update.connection
            connections_meta.append(
                {
                    "connection_id": str(connection.connection_id),
                    "name": connection.name,
                    "job_id": update.job_id,
                    "job_status": update.status,
                    "duration_seconds": update.duration_seconds,
                    "records_synced": update.records_synced,
                    "error": update.error,
                }
            )
            observe_airbyte_sync(
                tenant_id=str(connection.tenant_id),
                provider=connection.provider,
                connection_id=str(connection.connection_id),
                duration_seconds=float(update.duration_seconds)
                if update.duration_seconds is not None
                else None,
                records_synced=update.records_synced,
                status=update.status,
            )

        if persisted_connections:
            last_updated = persisted_connections[-1]
            logger.debug(
                "Airbyte connections persisted",
                extra={
                    **base_extra,
                    "persisted_count": len(persisted_connections),
                    "last_connection_id": str(last_updated.connection_id),
                },
            )

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
                "error_count": sum(1 for meta in connections_meta if meta["error"]),
                "duration_seconds": [meta["duration_seconds"] for meta in connections_meta if meta["duration_seconds"] is not None],
                "task_id": str(task_id) if task_id else None,
            },
        )
        return f"triggered {triggered} {provider.lower()} connection(s)"


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
