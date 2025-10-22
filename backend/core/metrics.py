"""Prometheus helpers for application metrics."""

from __future__ import annotations

from typing import Iterable, Mapping

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

CELERY_TASK_TOTAL = Counter(
    "celery_task_executions_total",
    "Total number of Celery task executions partitioned by task name and status.",
    ("task_name", "status"),
)

CELERY_TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Observed runtime of Celery tasks in seconds.",
    ("task_name",),
    buckets=(
        0.01,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2,
        5,
        10,
        30,
        60,
        120,
        300,
        600,
    ),
)

AIRBYTE_SYNC_LATENCY = Histogram(
    "airbyte_sync_latency_seconds",
    "Latency for Airbyte sync attempts partitioned by tenant and provider.",
    ("tenant_id", "provider"),
    buckets=(
        1,
        2,
        5,
        10,
        15,
        30,
        60,
        120,
        300,
        600,
    ),
)

AIRBYTE_ROWS_SYNCED = Counter(
    "airbyte_sync_rows_total",
    "Rows processed during Airbyte sync jobs partitioned by tenant, provider, and connection.",
    ("tenant_id", "provider", "connection_id"),
)

AIRBYTE_SYNC_ERRORS = Counter(
    "airbyte_sync_errors_total",
    "Number of Airbyte sync attempts that returned an error status.",
    ("tenant_id", "provider"),
)

_AIRBYTE_FAILURE_STATUSES = {
    "failed",
    "error",
    "errored",
    "cancelled",
    "canceled",
}

try:
    from opentelemetry import metrics as otel_metrics  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    _OTEL_METER = None
    _OTEL_SYNC_LATENCY = None
    _OTEL_SYNC_ROWS = None
    _OTEL_SYNC_ERRORS = None
else:  # pragma: no cover - exercised indirectly in environments with OpenTelemetry
    _OTEL_METER = otel_metrics.get_meter(__name__)
    _OTEL_SYNC_LATENCY = _OTEL_METER.create_histogram(
        "airbyte.sync.latency",
        unit="s",
        description="Observed Airbyte sync latency in seconds.",
    )
    _OTEL_SYNC_ROWS = _OTEL_METER.create_counter(
        "airbyte.sync.rows",
        unit="rows",
        description="Rows processed by Airbyte sync jobs.",
    )
    _OTEL_SYNC_ERRORS = _OTEL_METER.create_counter(
        "airbyte.sync.errors",
        description="Count of Airbyte sync failures.",
    )


def observe_task(task_name: str, status: str, duration_seconds: float | None) -> None:
    """Record a single task completion event."""

    CELERY_TASK_TOTAL.labels(task_name=task_name, status=status.lower()).inc()
    if duration_seconds is not None:
        CELERY_TASK_DURATION.labels(task_name=task_name).observe(duration_seconds)


def observe_airbyte_sync(
    *,
    tenant_id: str,
    provider: str | None,
    connection_id: str | None,
    duration_seconds: float | None,
    records_synced: int | None,
    status: str | None,
) -> None:
    """Record metrics for a completed (or in-flight) Airbyte sync attempt."""

    provider_label = provider or "unknown"

    attributes: Mapping[str, str] = {
        "tenant_id": tenant_id,
        "provider": provider_label,
    }

    if duration_seconds is not None:
        AIRBYTE_SYNC_LATENCY.labels(tenant_id=tenant_id, provider=provider_label).observe(
            duration_seconds
        )
        if _OTEL_SYNC_LATENCY is not None:
            _OTEL_SYNC_LATENCY.record(duration_seconds, attributes=dict(attributes))

    if records_synced is not None and connection_id:
        AIRBYTE_ROWS_SYNCED.labels(
            tenant_id=tenant_id, provider=provider_label, connection_id=connection_id
        ).inc(records_synced)
        if _OTEL_SYNC_ROWS is not None:
            otel_attrs = dict(attributes)
            otel_attrs["connection_id"] = connection_id
            _OTEL_SYNC_ROWS.add(records_synced, attributes=otel_attrs)

    status_normalized = (status or "").strip().lower()
    if status_normalized in _AIRBYTE_FAILURE_STATUSES:
        AIRBYTE_SYNC_ERRORS.labels(tenant_id=tenant_id, provider=provider_label).inc()
        if _OTEL_SYNC_ERRORS is not None:
            _OTEL_SYNC_ERRORS.add(1, attributes=dict(attributes))


def render_metrics() -> tuple[bytes, str]:
    """Return the current registry contents and content type."""

    return generate_latest(), CONTENT_TYPE_LATEST


def reset_metrics(registries: Iterable[Histogram | Counter] | None = None) -> None:
    """Reset Prometheus collectors for deterministic tests."""

    collectors = registries or (
        CELERY_TASK_TOTAL,
        CELERY_TASK_DURATION,
        AIRBYTE_SYNC_LATENCY,
        AIRBYTE_ROWS_SYNCED,
        AIRBYTE_SYNC_ERRORS,
    )
    for collector in collectors:
        collector.clear()
