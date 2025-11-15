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
from core.metrics import observe_task

logger = logging.getLogger(__name__)

SNAPSHOT_STALE_TTL_SECONDS = 60 * 60  # 60 minutes


@dataclass
class SnapshotOutcome:
    tenant_id: str
    status: str
    generated_at: datetime


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
            outcomes.append(SnapshotOutcome(tenant_id=tenant_id, status=status, generated_at=generated_at))
            age_seconds = (timezone.now() - generated_at).total_seconds()
            if age_seconds > SNAPSHOT_STALE_TTL_SECONDS:
                logger.warning(
                    "metrics.snapshot.stale",
                    extra={
                        "tenant_id": tenant_id,
                        "status": status,
                        "generated_at": generated_at.isoformat(),
                        "age_seconds": age_seconds,
                    },
                )
            logger.info(
                "metrics.snapshot.persisted",
                extra={
                    "tenant_id": tenant_id,
                    "status": status,
                    "generated_at": generated_at.isoformat(),
                },
            )
    return outcomes


@shared_task(
    bind=True,
    name="analytics.sync_metrics_snapshots",
    autoretry_for=(Exception,),
    retry_backoff=2,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def sync_metrics_snapshots(self, tenant_ids: list[str] | None = None) -> dict:
    started = timezone.now()
    try:
        outcomes = generate_snapshots_for_tenants(tenant_ids)
    except Exception:  # pragma: no cover - surfaced via Celery retry mechanisms
        duration = (timezone.now() - started).total_seconds()
        observe_task(self.name, "failure", duration)
        logger.exception("metrics.snapshot.failed")
        raise

    duration = (timezone.now() - started).total_seconds()
    observe_task(self.name, "success", duration)
    return {
        "processed": len(outcomes),
        "duration_seconds": duration,
    }
