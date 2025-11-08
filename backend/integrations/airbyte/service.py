"""Scheduling helpers for Airbyte connections."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any, Callable, Iterable

from django.utils import timezone

from accounts.tenant_context import tenant_context

from integrations.models import (
    AirbyteConnection,
    AirbyteJobTelemetry,
    ConnectionSyncUpdate,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttemptSnapshot:
    started_at: datetime | None
    duration_seconds: int | None
    records_synced: int | None
    bytes_synced: int | None
    api_cost: Decimal | None


class AirbyteSyncService:
    """Runs Airbyte syncs for configured connections."""

    def __init__(self, client, now_fn: Callable[[], datetime] | None = None) -> None:
        self.client = client
        self._now = now_fn or timezone.now

    def sync_due_connections(self) -> list[ConnectionSyncUpdate]:
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
    ) -> list[ConnectionSyncUpdate]:
        """Trigger syncs for a provided iterable of connections."""

        updates: list[ConnectionSyncUpdate] = []
        base_time = triggered_at or self._now()
        for connection in connections:
            tenant_id = str(connection.tenant_id)
            logger.info(
                "Triggering Airbyte sync",
                extra={
                    "tenant_id": tenant_id,
                    "connection_id": str(connection.connection_id),
                    "schedule_type": connection.schedule_type,
                    "provider": connection.provider,
                },
            )
            with tenant_context(tenant_id):
                job_payload = self.client.trigger_sync(str(connection.connection_id))
                job_id = extract_job_id(job_payload)
                job_status = "pending"
                job_created_at = base_time
                attempt_snapshot = AttemptSnapshot(
                    started_at=base_time,
                    duration_seconds=None,
                    records_synced=None,
                    bytes_synced=None,
                    api_cost=None,
                )
                job_detail: dict[str, Any] = {}
                if job_id is not None:
                    job_detail = self.client.get_job(job_id)
                    job_status = extract_job_status(job_detail) or job_status
                    job_created_at = extract_job_created_at(job_detail) or base_time
                    attempt_snapshot = extract_attempt_snapshot(job_detail) or attempt_snapshot
                job_context = job_detail or {}
                job_updated_at = extract_job_updated_at(job_context)
                completed_at = infer_completion_time(job_context, attempt_snapshot)
                error_message = extract_job_error(job_context)
                update = ConnectionSyncUpdate(
                    connection=connection,
                    job_id=str(job_id) if job_id is not None else None,
                    status=job_status,
                    created_at=job_created_at,
                    updated_at=job_updated_at,
                    completed_at=completed_at,
                    duration_seconds=attempt_snapshot.duration_seconds,
                    records_synced=attempt_snapshot.records_synced,
                    bytes_synced=attempt_snapshot.bytes_synced,
                    api_cost=attempt_snapshot.api_cost,
                    error=error_message,
                )
                updates.append(update)
                if job_id is not None:
                    _persist_job_snapshot(
                        connection=connection,
                        job_id=str(job_id),
                        status=job_status,
                        snapshot=attempt_snapshot,
                    )
        return updates


def extract_job_id(payload) -> int | None:
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


def extract_job_status(payload) -> str | None:
    if not payload:
        return None
    job = payload.get("job") if isinstance(payload, dict) else None
    if isinstance(job, dict) and job.get("status"):
        return job["status"]
    if isinstance(payload, dict) and payload.get("status"):
        return payload["status"]
    return None


def extract_job_created_at(payload) -> datetime | None:
    if not payload:
        return None
    job = payload.get("job") if isinstance(payload, dict) else None
    candidate = None
    if isinstance(job, dict):
        candidate = job.get("createdAt") or job.get("created_at")
    elif isinstance(payload, dict):
        candidate = payload.get("createdAt") or payload.get("created_at")
    return _coerce_timestamp(candidate)


def extract_attempt_snapshot(payload: dict[str, Any]) -> AttemptSnapshot | None:
    job = payload.get("job") if isinstance(payload, dict) else None
    if not isinstance(job, dict):
        return None
    attempts = job.get("attempts") or []
    if not attempts:
        return AttemptSnapshot(
            started_at=_coerce_timestamp(job.get("createdAt")),
            duration_seconds=None,
            records_synced=None,
            bytes_synced=None,
            api_cost=None,
        )
    latest = attempts[-1]
    metrics = (
        latest.get("metrics")
        or latest.get("attempt", {}).get("metrics")
        or {}
    )

    started_at = (
        _coerce_timestamp(latest.get("createdAt"))
        or _coerce_timestamp(latest.get("attempt", {}).get("createdAt"))
        or _coerce_timestamp(job.get("createdAt"))
    )

    ended_at = (
        _coerce_timestamp(latest.get("endedAt"))
        or _coerce_timestamp(latest.get("updatedAt"))
        or _coerce_timestamp(latest.get("attempt", {}).get("endedAt"))
        or _coerce_timestamp(latest.get("attempt", {}).get("updatedAt"))
    )

    time_in_millis = _coerce_int(
        metrics.get("timeInMillis")
        or metrics.get("processingTimeInMillis")
        or metrics.get("totalTimeInMillis")
    )

    duration_seconds = None
    if time_in_millis is not None:
        duration_seconds = max(int(time_in_millis / 1000), 0)
    elif started_at and ended_at:
        duration_seconds = max(int((ended_at - started_at).total_seconds()), 0)

    records_synced = _coerce_int(
        metrics.get("recordsEmitted")
        or metrics.get("recordsSynced")
        or metrics.get("recordsCommitted")
    )
    bytes_synced = _coerce_int(
        metrics.get("bytesEmitted")
        or metrics.get("bytesSynced")
    )

    api_cost_raw = metrics.get("apiCallCost") or metrics.get("apiCost")
    api_cost = _coerce_decimal(api_cost_raw)

    return AttemptSnapshot(
        started_at=started_at,
        duration_seconds=duration_seconds,
        records_synced=records_synced,
        bytes_synced=bytes_synced,
        api_cost=api_cost,
    )


def infer_completion_time(payload: dict[str, Any], snapshot: AttemptSnapshot) -> datetime | None:
    job = payload.get("job") if isinstance(payload, dict) else None
    candidates = []
    if isinstance(job, dict):
        candidates.append(job.get("updatedAt"))
        candidates.append(job.get("endedAt"))
    if isinstance(payload, dict):
        candidates.append(payload.get("updatedAt"))
        candidates.append(payload.get("endedAt"))
    for candidate in candidates:
        ts = _coerce_timestamp(candidate)
        if ts is not None:
            return ts
    if snapshot.started_at and snapshot.duration_seconds is not None:
        return snapshot.started_at + timedelta(seconds=snapshot.duration_seconds)
    return None


def extract_job_updated_at(payload) -> datetime | None:
    if not isinstance(payload, dict):
        return None
    job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
    if not isinstance(job, dict):
        return None
    return _coerce_timestamp(
        job.get("updatedAt")
        or job.get("updated_at")
        or job.get("endedAt")
        or job.get("ended_at")
    )


def extract_job_error(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
    if not isinstance(job, dict):
        return None
    failure_summary = job.get("failureSummary") or job.get("failure")
    if isinstance(failure_summary, dict):
        reason = failure_summary.get("failureReason") or failure_summary.get("stacktrace")
        if reason:
            return str(reason)
    error_message = job.get("errorMessage") or job.get("error")
    return str(error_message) if error_message else None


def _persist_job_snapshot(
    *,
    connection: AirbyteConnection,
    job_id: str,
    status: str,
    snapshot: AttemptSnapshot,
) -> None:
    defaults = {
        "tenant": connection.tenant,
        "status": status,
        "started_at": snapshot.started_at or timezone.now(),
        "duration_seconds": snapshot.duration_seconds,
        "records_synced": snapshot.records_synced,
        "bytes_synced": snapshot.bytes_synced,
        "api_cost": snapshot.api_cost,
    }
    AirbyteJobTelemetry.objects.update_or_create(
        connection=connection,
        job_id=job_id,
        defaults=defaults,
    )


def _coerce_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt_timezone.utc)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        # Airbyte often reports millisecond precision; normalise to seconds when needed.
        if timestamp > 1e12:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_timezone.utc)
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except (ValueError, ArithmeticError):
            return None
    if isinstance(value, dict):
        total = Decimal("0")
        seen = False
        for candidate in value.values():
            coerced = _coerce_decimal(candidate)
            if coerced is not None:
                total += coerced
                seen = True
        return total if seen else None
    return None
