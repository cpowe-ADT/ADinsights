from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from celery import shared_task
from django.utils import timezone

from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from analytics.models import TenantMetricsSnapshot
from analytics.snapshots import (
    default_snapshot_metrics,
    fetch_snapshot_metrics,
    snapshot_metrics_to_combined_payload,
)
from analytics.summaries import build_daily_summary_payload, summarize_daily_metrics
from analytics.notifications import send_daily_summary_email
from core.metrics import observe_task
from core.tasks import BaseAdInsightsTask

logger = logging.getLogger(__name__)

SNAPSHOT_STALE_TTL_SECONDS = 60 * 60  # 60 minutes


@dataclass
class SnapshotOutcome:
    tenant_id: str
    status: str
    generated_at: datetime
    stale: bool
    row_counts: dict[str, int]


@dataclass
class DailySummaryOutcome:
    tenant_id: str
    status: str
    generated_at: datetime
    summary: str


def _ensure_aware(dt: datetime | None) -> datetime:
    """Return an aware datetime, defaulting to now if missing."""
    if dt is None:
        return timezone.now()
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def _snapshot_payload_for_tenant(tenant_id: str) -> tuple[dict, datetime, str]:
    metrics = fetch_snapshot_metrics(tenant_id=tenant_id)
    if metrics is None:
        metrics = default_snapshot_metrics(tenant_id=tenant_id)
        status = "default"
    else:
        status = "fetched"
    generated_at = _ensure_aware(metrics.generated_at)
    payload = snapshot_metrics_to_combined_payload(metrics)
    payload["snapshot_generated_at"] = generated_at.isoformat()
    return payload, generated_at, status


def _daily_summary_for_tenant(tenant_id: str) -> DailySummaryOutcome:
    metrics = fetch_snapshot_metrics(tenant_id=tenant_id)
    if metrics is None:
        metrics = default_snapshot_metrics(tenant_id=tenant_id)
        status = "default"
    else:
        status = "fetched"

    payload = build_daily_summary_payload(metrics)
    summary = summarize_daily_metrics(payload)
    return DailySummaryOutcome(
        tenant_id=tenant_id,
        status=status,
        generated_at=_ensure_aware(metrics.generated_at),
        summary=summary,
    )


def _safe_len(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


def _count_payload_rows(payload: dict) -> dict[str, int]:
    campaign = payload.get("campaign") or {}
    return {
        "campaign_rows": _safe_len(campaign.get("rows")),
        "campaign_trend": _safe_len(campaign.get("trend")),
        "creative": _safe_len(payload.get("creative")),
        "budget": _safe_len(payload.get("budget")),
        "parish": _safe_len(payload.get("parish")),
    }


def generate_snapshots_for_tenants(tenant_ids: Sequence[str] | None = None) -> list[SnapshotOutcome]:
    tenants: Iterable[Tenant]
    queryset = Tenant.objects.all().order_by("created_at")
    if tenant_ids:
        queryset = queryset.filter(id__in=tenant_ids)
    tenants = queryset

    outcomes: list[SnapshotOutcome] = []
    for tenant in tenants:
        tenant_id = str(tenant.id)
        with tenant_context(tenant_id):
            payload, generated_at, status = _snapshot_payload_for_tenant(tenant_id)
            generated_at = _ensure_aware(generated_at)
            TenantMetricsSnapshot.objects.update_or_create(
                tenant=tenant,
                source="warehouse",
                defaults={
                    "payload": payload,
                    "generated_at": generated_at,
                },
            )
            row_counts = _count_payload_rows(payload)
            age_seconds = (timezone.now() - generated_at).total_seconds()
            is_stale = age_seconds > SNAPSHOT_STALE_TTL_SECONDS
            outcomes.append(
                SnapshotOutcome(
                    tenant_id=tenant_id,
                    status=status,
                    generated_at=generated_at,
                    stale=is_stale,
                    row_counts=row_counts,
                )
            )
            if is_stale:
                logger.warning(
                    "metrics.snapshot.stale",
                    extra={
                        "tenant_id": tenant_id,
                        "status": status,
                        "generated_at": generated_at.isoformat(),
                        "age_seconds": age_seconds,
                        "row_counts": row_counts,
                    },
                )
            logger.info(
                "metrics.snapshot.persisted",
                extra={
                    "tenant_id": tenant_id,
                    "status": status,
                    "generated_at": generated_at.isoformat(),
                    "age_seconds": age_seconds,
                    "row_counts": row_counts,
                },
            )
    return outcomes


def generate_daily_summaries_for_tenants(
    tenant_ids: Sequence[str] | None = None,
) -> list[DailySummaryOutcome]:
    tenants: Iterable[Tenant]
    queryset = Tenant.objects.all().order_by("created_at")
    if tenant_ids:
        queryset = queryset.filter(id__in=tenant_ids)
    tenants = queryset

    outcomes: list[DailySummaryOutcome] = []
    for tenant in tenants:
        tenant_id = str(tenant.id)
        with tenant_context(tenant_id):
            outcome = _daily_summary_for_tenant(tenant_id)
            summary_length = len(outcome.summary or "")
            send_daily_summary_email(
                tenant=tenant,
                summary=outcome.summary,
                generated_at=outcome.generated_at,
                status=outcome.status,
            )
            logger.info(
                "metrics.daily_summary.generated",
                extra={
                    "tenant_id": tenant_id,
                    "status": outcome.status,
                    "generated_at": outcome.generated_at.isoformat(),
                    "summary_length": summary_length,
                },
            )
            outcomes.append(outcome)
    return outcomes


@shared_task(
    bind=True,
    name="analytics.sync_metrics_snapshots",
    base=BaseAdInsightsTask,
    max_retries=5,
)
def sync_metrics_snapshots(self, tenant_ids: list[str] | None = None) -> dict:
    started = timezone.now()
    try:
        outcomes = generate_snapshots_for_tenants(tenant_ids)
    except Exception as exc:  # pragma: no cover - surfaced via Celery retry mechanisms
        duration = (timezone.now() - started).total_seconds()
        observe_task(self.name, "failure", duration)
        logger.exception(
            "metrics.snapshot.failed",
            extra={
                "task_id": getattr(getattr(self, "request", None), "id", None),
                "tenant_count": len(tenant_ids) if tenant_ids else None,
            },
        )
        raise self.retry_with_backoff(exc=exc, base_delay=60, max_delay=900)

    duration = (timezone.now() - started).total_seconds()
    observe_task(self.name, "success", duration)
    stale_tenant_ids = [outcome.tenant_id for outcome in outcomes if outcome.stale]
    status_counts = {
        "default": sum(outcome.status == "default" for outcome in outcomes),
        "fetched": sum(outcome.status == "fetched" for outcome in outcomes),
    }
    row_totals = {
        "campaign_rows": sum(outcome.row_counts.get("campaign_rows", 0) for outcome in outcomes),
        "campaign_trend": sum(outcome.row_counts.get("campaign_trend", 0) for outcome in outcomes),
        "creative": sum(outcome.row_counts.get("creative", 0) for outcome in outcomes),
        "budget": sum(outcome.row_counts.get("budget", 0) for outcome in outcomes),
        "parish": sum(outcome.row_counts.get("parish", 0) for outcome in outcomes),
    }
    generated_at_values = [outcome.generated_at for outcome in outcomes]
    logger.info(
        "metrics.snapshot.completed",
        extra={
            "task_id": getattr(getattr(self, "request", None), "id", None),
            "processed": len(outcomes),
            "duration_seconds": duration,
            "status_counts": status_counts,
            "stale_count": len(stale_tenant_ids),
            "stale_tenants_sample": stale_tenant_ids[:10],
            "row_totals": row_totals,
            "oldest_snapshot_generated_at": min(generated_at_values).isoformat()
            if generated_at_values
            else None,
            "newest_snapshot_generated_at": max(generated_at_values).isoformat()
            if generated_at_values
            else None,
        },
    )
    return {
        "processed": len(outcomes),
        "duration_seconds": duration,
        "status_counts": status_counts,
        "stale_count": len(stale_tenant_ids),
        "row_totals": row_totals,
        "oldest_snapshot_generated_at": min(generated_at_values).isoformat()
        if generated_at_values
        else None,
        "newest_snapshot_generated_at": max(generated_at_values).isoformat()
        if generated_at_values
        else None,
    }


@shared_task(
    bind=True,
    name="analytics.ai_daily_summary",
    base=BaseAdInsightsTask,
    max_retries=5,
)
def ai_daily_summary(self, tenant_ids: list[str] | None = None) -> dict:
    started = timezone.now()
    try:
        outcomes = generate_daily_summaries_for_tenants(tenant_ids)
    except Exception as exc:  # pragma: no cover - surfaced via Celery retry mechanisms
        duration = (timezone.now() - started).total_seconds()
        observe_task(self.name, "failure", duration)
        logger.exception(
            "metrics.daily_summary.failed",
            extra={
                "task_id": getattr(getattr(self, "request", None), "id", None),
                "tenant_count": len(tenant_ids) if tenant_ids else None,
            },
        )
        raise self.retry_with_backoff(exc=exc, base_delay=60, max_delay=900)

    duration = (timezone.now() - started).total_seconds()
    observe_task(self.name, "success", duration)
    summary_lengths = [len(outcome.summary or "") for outcome in outcomes]
    logger.info(
        "metrics.daily_summary.completed",
        extra={
            "task_id": getattr(getattr(self, "request", None), "id", None),
            "processed": len(outcomes),
            "duration_seconds": duration,
            "summary_length_avg": (sum(summary_lengths) / len(summary_lengths))
            if summary_lengths
            else 0,
        },
    )
    return {
        "processed": len(outcomes),
        "duration_seconds": duration,
    }
