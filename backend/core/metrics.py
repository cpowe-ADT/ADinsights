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

CELERY_TASK_RETRY_TOTAL = Counter(
    "celery_task_retries_total",
    "Total number of Celery retries partitioned by task and failure reason.",
    ("task_name", "reason"),
)

CELERY_TASK_QUEUE_START_TOTAL = Counter(
    "celery_task_queue_starts_total",
    "Total number of Celery task starts partitioned by task and queue.",
    ("task_name", "queue_name"),
)

CELERY_TASK_QUEUE_WAIT = Histogram(
    "celery_task_queue_wait_seconds",
    "Observed wait time between task publish and worker start.",
    ("task_name", "queue_name"),
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

DBT_RUN_DURATION = Histogram(
    "dbt_run_duration_seconds",
    "Observed runtime of dbt invocations in seconds.",
    ("status",),
    buckets=(
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
        1200,
    ),
)

COMBINED_METRICS_REQUEST_TOTAL = Counter(
    "combined_metrics_requests_total",
    "Combined metrics endpoint requests by source, cache outcome, and status.",
    ("source", "cache_outcome", "status", "has_filters"),
)

COMBINED_METRICS_REQUEST_DURATION = Histogram(
    "combined_metrics_request_duration_seconds",
    "Latency of combined metrics endpoint requests.",
    ("source", "cache_outcome"),
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
    ),
)

COMBINED_METRICS_QUERY_COUNT = Histogram(
    "combined_metrics_query_count",
    "Database query count observed per combined metrics request.",
    ("source", "cache_outcome"),
    buckets=(0, 1, 2, 3, 5, 8, 13, 21, 34),
)

COMBINED_METRICS_SNAPSHOT_WRITES_TOTAL = Counter(
    "combined_metrics_snapshot_writes_total",
    "Snapshot write outcomes for combined metrics requests.",
    ("source", "result"),
)

META_TOKEN_VALIDATIONS_TOTAL = Counter(
    "meta_token_validations_total",
    "Meta token validation attempts partitioned by status.",
    ("status",),
)

META_TOKEN_REFRESH_ATTEMPTS_TOTAL = Counter(
    "meta_token_refresh_attempts_total",
    "Meta token refresh attempts partitioned by auth mode and status.",
    ("auth_mode", "status"),
)

META_GRAPH_RETRY_TOTAL = Counter(
    "meta_graph_retry_total",
    "Retry events triggered while calling Meta Graph API.",
    ("reason",),
)

META_GRAPH_THROTTLE_EVENTS_TOTAL = Counter(
    "meta_graph_throttle_events_total",
    "Throttle warning events from Meta Graph usage headers.",
    ("header_name",),
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


def observe_task_retry(*, task_name: str, reason: str | None) -> None:
    """Record a task retry event with a failure-reason label."""

    reason_label = (reason or "unknown").strip().lower() or "unknown"
    CELERY_TASK_RETRY_TOTAL.labels(task_name=task_name, reason=reason_label).inc()


def observe_task_queue_start(
    *,
    task_name: str,
    queue_name: str | None,
    queue_wait_seconds: float | None,
) -> None:
    """Record queue-level start and wait metrics for Celery tasks."""

    queue_label = (queue_name or "unknown").strip().lower() or "unknown"
    CELERY_TASK_QUEUE_START_TOTAL.labels(task_name=task_name, queue_name=queue_label).inc()
    if queue_wait_seconds is not None:
        CELERY_TASK_QUEUE_WAIT.labels(task_name=task_name, queue_name=queue_label).observe(
            queue_wait_seconds
        )


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


def observe_dbt_run(status: str, duration_seconds: float | None) -> None:
    """Record metrics for dbt runs when duration is available."""

    if duration_seconds is None:
        return
    status_label = (status or "unknown").lower()
    DBT_RUN_DURATION.labels(status=status_label).observe(duration_seconds)


def observe_combined_metrics_request(
    *,
    source: str | None,
    cache_outcome: str | None,
    status: str | None,
    duration_seconds: float | None,
    query_count: int | None,
    snapshot_written: bool,
    has_filters: bool,
) -> None:
    source_label = (source or "unknown").strip().lower()
    cache_label = (cache_outcome or "unknown").strip().lower()
    status_label = (status or "unknown").strip().lower()
    filters_label = "true" if has_filters else "false"
    COMBINED_METRICS_REQUEST_TOTAL.labels(
        source=source_label,
        cache_outcome=cache_label,
        status=status_label,
        has_filters=filters_label,
    ).inc()
    if duration_seconds is not None:
        COMBINED_METRICS_REQUEST_DURATION.labels(
            source=source_label,
            cache_outcome=cache_label,
        ).observe(duration_seconds)
    if query_count is not None:
        COMBINED_METRICS_QUERY_COUNT.labels(
            source=source_label,
            cache_outcome=cache_label,
        ).observe(query_count)
    write_result = "written" if snapshot_written else "skipped"
    COMBINED_METRICS_SNAPSHOT_WRITES_TOTAL.labels(
        source=source_label,
        result=write_result,
    ).inc()


def observe_meta_token_validation(status: str) -> None:
    """Record a token validation event for Meta credentials."""

    META_TOKEN_VALIDATIONS_TOTAL.labels(status=(status or "unknown").lower()).inc()


def observe_meta_token_refresh_attempt(*, auth_mode: str, status: str) -> None:
    """Record a token refresh attempt outcome for Meta credentials."""

    META_TOKEN_REFRESH_ATTEMPTS_TOTAL.labels(
        auth_mode=(auth_mode or "unknown").lower(),
        status=(status or "unknown").lower(),
    ).inc()


def observe_meta_graph_retry(*, reason: str) -> None:
    """Record a Meta Graph retry event."""

    META_GRAPH_RETRY_TOTAL.labels(reason=(reason or "unknown").lower()).inc()


def observe_meta_graph_throttle_event(*, header_name: str) -> None:
    """Record a Meta Graph throttle warning event."""

    META_GRAPH_THROTTLE_EVENTS_TOTAL.labels(
        header_name=(header_name or "unknown").lower()
    ).inc()


def render_metrics() -> tuple[bytes, str]:
    """Return the current registry contents and content type."""

    return generate_latest(), CONTENT_TYPE_LATEST


def reset_metrics(registries: Iterable[Histogram | Counter] | None = None) -> None:
    """Reset Prometheus collectors for deterministic tests."""

    collectors = registries or (
        CELERY_TASK_TOTAL,
        CELERY_TASK_DURATION,
        CELERY_TASK_RETRY_TOTAL,
        CELERY_TASK_QUEUE_START_TOTAL,
        CELERY_TASK_QUEUE_WAIT,
        AIRBYTE_SYNC_LATENCY,
        AIRBYTE_ROWS_SYNCED,
        AIRBYTE_SYNC_ERRORS,
        DBT_RUN_DURATION,
        COMBINED_METRICS_REQUEST_TOTAL,
        COMBINED_METRICS_REQUEST_DURATION,
        COMBINED_METRICS_QUERY_COUNT,
        COMBINED_METRICS_SNAPSHOT_WRITES_TOTAL,
        META_TOKEN_VALIDATIONS_TOTAL,
        META_TOKEN_REFRESH_ATTEMPTS_TOTAL,
        META_GRAPH_RETRY_TOTAL,
        META_GRAPH_THROTTLE_EVENTS_TOTAL,
    )
    for collector in collectors:
        collector.clear()
