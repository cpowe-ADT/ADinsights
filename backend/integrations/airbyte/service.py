"""Scheduling helpers for Airbyte connections."""

from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone
from typing import Callable, Iterable

from django.utils import timezone

from integrations.models import AirbyteConnection, TenantAirbyteSyncStatus

logger = logging.getLogger(__name__)


class AirbyteSyncService:
    """Runs Airbyte syncs for configured connections."""

    def __init__(self, client, now_fn: Callable[[], datetime] | None = None) -> None:
        self.client = client
        self._now = now_fn or timezone.now

    def sync_due_connections(self) -> int:
        """Trigger syncs for all connections that are due."""

        now = self._now()
        connections = [
            connection
            for connection in AirbyteConnection.objects.filter(is_active=True).select_related("tenant")
            if connection.should_trigger(now)
        ]
        return self.sync_connections(connections, triggered_at=now)

    def sync_connections(
        self,
        connections: Iterable[AirbyteConnection],
        *,
        triggered_at: datetime | None = None,
    ) -> int:
        """Trigger syncs for a provided iterable of connections."""

        triggered = 0
        base_time = triggered_at or self._now()
        for connection in connections:
            logger.info(
                "Triggering Airbyte sync",
                extra={
                    "tenant_id": str(connection.tenant_id),
                    "connection_id": str(connection.connection_id),
                    "schedule_type": connection.schedule_type,
                    "provider": connection.provider,
                },
            )
            job_payload = self.client.trigger_sync(str(connection.connection_id))
            job_id = _extract_job_id(job_payload)
            job_status = "pending"
            job_created_at = base_time
            if job_id is not None:
                job_detail = self.client.get_job(job_id)
                job_status = _extract_job_status(job_detail) or job_status
                job_created_at = _extract_job_created_at(job_detail) or base_time
            connection.record_sync(job_id, job_status, job_created_at)
            TenantAirbyteSyncStatus.update_for_connection(connection)
            triggered += 1
        return triggered


def _extract_job_id(payload) -> int | None:
    if not payload:
        return None
    if isinstance(payload, dict):
        if "job" in payload and isinstance(payload["job"], dict):
            job = payload["job"]
            job_id = job.get("id") or job.get("jobId")
            return int(job_id) if job_id is not None else None
        job_id = payload.get("id") or payload.get("jobId")
        return int(job_id) if job_id is not None else None
    return None


def _extract_job_status(payload) -> str | None:
    if not payload:
        return None
    job = payload.get("job") if isinstance(payload, dict) else None
    if isinstance(job, dict) and job.get("status"):
        return job["status"]
    if isinstance(payload, dict) and payload.get("status"):
        return payload["status"]
    return None


def _extract_job_created_at(payload) -> datetime | None:
    if not payload:
        return None
    job = payload.get("job") if isinstance(payload, dict) else None
    candidate = None
    if isinstance(job, dict):
        candidate = job.get("createdAt") or job.get("created_at")
    elif isinstance(payload, dict):
        candidate = payload.get("createdAt") or payload.get("created_at")
    if candidate is None:
        return None
    if isinstance(candidate, (int, float)):
        return datetime.fromtimestamp(candidate, tz=dt_timezone.utc)
    if isinstance(candidate, str):
        cleaned = candidate.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt_timezone.utc)
        return parsed
    if isinstance(candidate, datetime):
        return candidate if candidate.tzinfo else candidate.replace(tzinfo=dt_timezone.utc)
    return None
