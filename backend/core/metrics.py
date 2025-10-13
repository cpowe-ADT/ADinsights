"""Prometheus helpers for application metrics."""

from __future__ import annotations

from typing import Iterable

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


def observe_task(task_name: str, status: str, duration_seconds: float | None) -> None:
    """Record a single task completion event."""

    CELERY_TASK_TOTAL.labels(task_name=task_name, status=status.lower()).inc()
    if duration_seconds is not None:
        CELERY_TASK_DURATION.labels(task_name=task_name).observe(duration_seconds)


def render_metrics() -> tuple[bytes, str]:
    """Return the current registry contents and content type."""

    return generate_latest(), CONTENT_TYPE_LATEST


def reset_metrics(registries: Iterable[Histogram | Counter] | None = None) -> None:
    """Reset Prometheus collectors for deterministic tests."""

    collectors = registries or (CELERY_TASK_TOTAL, CELERY_TASK_DURATION)
    for collector in collectors:
        collector.clear()
