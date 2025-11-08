"""Utilities for generating and normalising warehouse snapshot payloads."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import DatabaseError, OperationalError, ProgrammingError, connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SnapshotMetrics:
    tenant_id: str
    generated_at: datetime
    campaign_metrics: dict[str, Any]
    creative_metrics: list[dict[str, Any]]
    budget_metrics: list[dict[str, Any]]
    parish_metrics: list[dict[str, Any]]


def _coerce_json_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "tobytes"):
        value = value.tobytes()
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return json.loads(value)
    return value


def _default_campaign_metrics() -> dict[str, Any]:
    return {
        "summary": {
            "currency": "USD",
            "totalSpend": 0.0,
            "totalImpressions": 0,
            "totalClicks": 0,
            "totalConversions": 0,
            "averageRoas": 0.0,
        },
        "trend": [],
        "rows": [],
    }


def _default_parish_metrics() -> list[dict[str, Any]]:
    return [
        {
            "parish": "Unknown",
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "roas": 0.0,
            "campaignCount": 0,
            "currency": "USD",
        }
    ]


def default_snapshot_metrics(*, tenant_id: str) -> SnapshotMetrics:
    generated_at = timezone.now()
    return SnapshotMetrics(
        tenant_id=tenant_id,
        generated_at=generated_at,
        campaign_metrics=_default_campaign_metrics(),
        creative_metrics=[],
        budget_metrics=[],
        parish_metrics=_default_parish_metrics(),
    )


def _parse_generated_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    return timezone.now()


def fetch_snapshot_metrics(*, tenant_id: str) -> SnapshotMetrics | None:
    sql = (
        "select tenant_id, generated_at, campaign_metrics, creative_metrics, "
        "budget_metrics, parish_metrics "
        "from vw_dashboard_aggregate_snapshot "
        "where tenant_id = %(tenant_id)s "
        "order by generated_at desc limit 1"
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"tenant_id": tenant_id})
            row = cursor.fetchone()
            if not row:
                return None
            columns = [col[0] for col in cursor.description]
            record = dict(zip(columns, row))
    except (ProgrammingError, OperationalError) as exc:
        logger.warning(
            "aggregate snapshot view unavailable; returning default payload",
            extra={"tenant_id": tenant_id},
            exc_info=exc,
        )
        return None
    except DatabaseError:
        logger.warning(
            "vw_dashboard_aggregate_snapshot unavailable; returning empty payload",
            extra={"tenant_id": tenant_id},
        )
        return None

    campaign_metrics = _coerce_json_payload(record.get("campaign_metrics"))
    creative_metrics = _coerce_json_payload(record.get("creative_metrics")) or []
    budget_metrics = _coerce_json_payload(record.get("budget_metrics")) or []
    parish_metrics = _coerce_json_payload(record.get("parish_metrics")) or []

    metrics = SnapshotMetrics(
        tenant_id=tenant_id,
        generated_at=_parse_generated_at(record.get("generated_at")),
        campaign_metrics=campaign_metrics or _default_campaign_metrics(),
        creative_metrics=list(creative_metrics),
        budget_metrics=list(budget_metrics),
        parish_metrics=list(parish_metrics) or _default_parish_metrics(),
    )
    return metrics


def snapshot_metrics_to_serializer_payload(metrics: SnapshotMetrics) -> dict[str, Any]:
    return {
        "tenant_id": metrics.tenant_id,
        "generated_at": metrics.generated_at,
        "metrics": {
            "campaign_metrics": metrics.campaign_metrics,
            "creative_metrics": metrics.creative_metrics,
            "budget_metrics": metrics.budget_metrics,
            "parish_metrics": metrics.parish_metrics,
        },
    }


def snapshot_metrics_to_combined_payload(metrics: SnapshotMetrics) -> dict[str, Any]:
    return {
        "campaign": metrics.campaign_metrics,
        "creative": metrics.creative_metrics,
        "budget": metrics.budget_metrics,
        "parish": metrics.parish_metrics,
        "snapshot_generated_at": metrics.generated_at.isoformat(),
    }
