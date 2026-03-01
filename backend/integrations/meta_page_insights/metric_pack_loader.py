from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings

from integrations.models import MetaMetricRegistry

BLOCKED_METRIC_PREFIXES = (
    "page_impressions",
    "post_impressions",
    "page_fans",
    "page_video_views_10s",
    "post_video_views_10s",
)


def is_blocked_metric(metric_key: str) -> bool:
    return any(metric_key.startswith(prefix) for prefix in BLOCKED_METRIC_PREFIXES)


def default_metric_pack_path() -> Path:
    configured = str(getattr(settings, "META_PAGE_INSIGHTS_METRIC_PACK_PATH", "") or "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "assets" / "meta_page_metric_pack_v1.json"


def load_metric_pack_v1(path: str | Path | None = None) -> int:
    pack_path = Path(path) if path is not None else default_metric_pack_path()
    if not pack_path.exists():
        return 0

    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics")
    if not isinstance(metrics, list):
        return 0

    upserted = 0
    for raw in metrics:
        if not isinstance(raw, dict):
            continue
        metric_name = str(raw.get("name") or "").strip()
        object_type = str(raw.get("object_type") or "").strip().lower()
        if not metric_name or is_blocked_metric(metric_name):
            continue
        if object_type not in {"page", "post"}:
            continue

        periods = raw.get("supported_periods")
        supported_periods = (
            sorted({str(period).strip() for period in periods if str(period).strip()})
            if isinstance(periods, list)
            else []
        )
        level = (
            MetaMetricRegistry.LEVEL_PAGE
            if object_type == "page"
            else MetaMetricRegistry.LEVEL_POST
        )
        supports_breakdown = bool(raw.get("supports_breakdown"))
        supports_breakdowns = list(raw.get("supports_breakdowns") or [])
        if supports_breakdown and not supports_breakdowns:
            supports_breakdowns = ["default"]
        status = str(raw.get("status") or MetaMetricRegistry.STATUS_ACTIVE).upper()
        if status not in {
            MetaMetricRegistry.STATUS_ACTIVE,
            MetaMetricRegistry.STATUS_DEPRECATED,
            MetaMetricRegistry.STATUS_INVALID,
            MetaMetricRegistry.STATUS_UNKNOWN,
        }:
            status = MetaMetricRegistry.STATUS_ACTIVE

        defaults: dict[str, Any] = {
            "supported_periods": supported_periods,
            "supports_breakdowns": supports_breakdowns,
            "status": status,
            "replacement_metric_key": str(raw.get("replacement_metric_key") or "").strip(),
            "is_default": bool(raw.get("is_default", True)),
            "title": str(raw.get("title") or "").strip(),
            "description": str(raw.get("description") or "").strip(),
            "metadata": {
                "provider": str(payload.get("provider") or "meta"),
                "object_type": object_type,
                "default_period": str(raw.get("default_period") or "").strip(),
                "metric_pack": str(payload.get("version") or "v1"),
            },
        }
        MetaMetricRegistry.objects.update_or_create(
            metric_key=metric_name,
            level=level,
            defaults=defaults,
        )
        upserted += 1

    # Hard-deprecate known blocked metrics if they already exist.
    for blocked in MetaMetricRegistry.objects.all():
        if not is_blocked_metric(blocked.metric_key):
            continue
        if blocked.status != MetaMetricRegistry.STATUS_DEPRECATED:
            blocked.status = MetaMetricRegistry.STATUS_DEPRECATED
            blocked.is_default = False
            blocked.save(update_fields=["status", "is_default", "updated_at"])

    return upserted

