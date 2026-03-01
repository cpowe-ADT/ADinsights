from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from integrations.meta_page_insights.metric_pack_loader import (
    is_blocked_metric,
    load_metric_pack_v1,
)
from integrations.models import MetaMetricRegistry

FALLBACK_METRIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "metric_key": "page_media_view",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": ["default"],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "page_total_media_view_unique",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "page_post_engagements",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "page_total_actions",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "page_views_total",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "page_daily_follows_unique",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "page_daily_unfollows_unique",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "page_follows",
        "level": MetaMetricRegistry.LEVEL_PAGE,
        "supported_periods": ["day", "week", "days_28"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "post_media_view",
        "level": MetaMetricRegistry.LEVEL_POST,
        "supported_periods": ["lifetime"],
        "supports_breakdowns": ["default"],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "post_total_media_view_unique",
        "level": MetaMetricRegistry.LEVEL_POST,
        "supported_periods": ["lifetime"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "post_clicks",
        "level": MetaMetricRegistry.LEVEL_POST,
        "supported_periods": ["lifetime"],
        "supports_breakdowns": [],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
    {
        "metric_key": "post_reactions_by_type_total",
        "level": MetaMetricRegistry.LEVEL_POST,
        "supported_periods": ["lifetime"],
        "supports_breakdowns": ["default"],
        "status": MetaMetricRegistry.STATUS_ACTIVE,
        "replacement_metric_key": "",
        "is_default": True,
    },
]

REPLACEMENT_CANDIDATES: dict[tuple[str, str], str] = {
    (MetaMetricRegistry.LEVEL_PAGE, "page_impressions"): "page_media_view",
    (MetaMetricRegistry.LEVEL_PAGE, "page_impressions_unique"): "page_total_media_view_unique",
    (MetaMetricRegistry.LEVEL_PAGE, "page_fans"): "page_follows",
    (MetaMetricRegistry.LEVEL_PAGE, "page_video_views_10s"): "page_video_views",
    (MetaMetricRegistry.LEVEL_POST, "post_impressions"): "post_media_view",
    (MetaMetricRegistry.LEVEL_POST, "post_impressions_unique"): "post_total_media_view_unique",
    (MetaMetricRegistry.LEVEL_POST, "post_video_views_10s"): "post_video_views",
}


def seed_default_metrics() -> None:
    loaded = load_metric_pack_v1()
    if loaded <= 0:
        for definition in FALLBACK_METRIC_DEFINITIONS:
            MetaMetricRegistry.objects.update_or_create(
                metric_key=definition["metric_key"],
                level=definition["level"],
                defaults={
                    "supported_periods": definition["supported_periods"],
                    "supports_breakdowns": definition["supports_breakdowns"],
                    "status": definition["status"],
                    "replacement_metric_key": definition["replacement_metric_key"],
                    "is_default": definition["is_default"],
                },
            )

    for metric in MetaMetricRegistry.objects.all():
        if not is_blocked_metric(metric.metric_key):
            continue
        replacement = REPLACEMENT_CANDIDATES.get((metric.level, metric.metric_key), "")
        metric.status = MetaMetricRegistry.STATUS_DEPRECATED
        metric.is_default = False
        if replacement and not metric.replacement_metric_key:
            metric.replacement_metric_key = replacement
        metric.save(update_fields=["status", "is_default", "replacement_metric_key", "updated_at"])


def get_default_metric_keys(level: str) -> list[str]:
    rows = (
        MetaMetricRegistry.objects.filter(
            level=level,
            is_default=True,
        )
        .exclude(status__in=[MetaMetricRegistry.STATUS_INVALID, MetaMetricRegistry.STATUS_DEPRECATED])
        .values_list("metric_key", flat=True)
    )
    return [row for row in rows if not is_blocked_metric(row)]


def get_active_metric_keys(level: str, *, include_all: bool = False) -> list[str]:
    queryset = MetaMetricRegistry.objects.filter(level=level)
    if not include_all:
        queryset = queryset.exclude(
            status__in=[MetaMetricRegistry.STATUS_INVALID, MetaMetricRegistry.STATUS_DEPRECATED]
        )
    return [row for row in queryset.values_list("metric_key", flat=True) if not is_blocked_metric(row)]


def resolve_metric_key(level: str, metric_key: str) -> str:
    if is_blocked_metric(metric_key):
        replacement = REPLACEMENT_CANDIDATES.get((level, metric_key))
        return replacement or metric_key
    metric = MetaMetricRegistry.objects.filter(level=level, metric_key=metric_key).first()
    if metric is None:
        return metric_key
    if metric.status in {MetaMetricRegistry.STATUS_INVALID, MetaMetricRegistry.STATUS_DEPRECATED}:
        replacement = (metric.replacement_metric_key or "").strip()
        if replacement:
            return replacement
    return metric.metric_key


def mark_metric_invalid(level: str, metric_key: str) -> MetaMetricRegistry:
    replacement = REPLACEMENT_CANDIDATES.get((level, metric_key), "")
    metric, _ = MetaMetricRegistry.objects.get_or_create(
        metric_key=metric_key,
        level=level,
        defaults={
            "supported_periods": [],
            "supports_breakdowns": [],
            "status": MetaMetricRegistry.STATUS_INVALID,
            "replacement_metric_key": replacement,
            "is_default": False,
        },
    )
    metric.status = MetaMetricRegistry.STATUS_INVALID
    metric.is_default = False
    if replacement and not metric.replacement_metric_key:
        metric.replacement_metric_key = replacement
    metric.save(update_fields=["status", "is_default", "replacement_metric_key", "updated_at"])
    return metric


def mark_metric_deprecated(level: str, metric_key: str, replacement_metric_key: str | None = None) -> None:
    metric, _ = MetaMetricRegistry.objects.get_or_create(
        metric_key=metric_key,
        level=level,
        defaults={
            "supported_periods": [],
            "supports_breakdowns": [],
        },
    )
    metric.status = MetaMetricRegistry.STATUS_DEPRECATED
    metric.is_default = False
    if replacement_metric_key:
        metric.replacement_metric_key = replacement_metric_key
    metric.save(update_fields=["status", "is_default", "replacement_metric_key", "updated_at"])


def mark_metric_unknown(level: str, metric_key: str) -> None:
    metric, _ = MetaMetricRegistry.objects.get_or_create(
        metric_key=metric_key,
        level=level,
        defaults={
            "supported_periods": [],
            "supports_breakdowns": [],
        },
    )
    if metric.status in {MetaMetricRegistry.STATUS_INVALID, MetaMetricRegistry.STATUS_DEPRECATED}:
        return
    metric.status = MetaMetricRegistry.STATUS_UNKNOWN
    metric.save(update_fields=["status", "updated_at"])


def update_metric_metadata(
    *,
    level: str,
    metric_key: str,
    title: str | None,
    description: str | None,
    periods: Iterable[str] | None = None,
) -> None:
    if is_blocked_metric(metric_key):
        mark_metric_deprecated(level, metric_key, REPLACEMENT_CANDIDATES.get((level, metric_key)))
        return

    metric, _ = MetaMetricRegistry.objects.get_or_create(
        metric_key=metric_key,
        level=level,
        defaults={
            "supported_periods": list(periods or []),
            "supports_breakdowns": [],
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "is_default": False,
        },
    )
    changed: list[str] = []
    if title and title != metric.title:
        metric.title = title
        changed.append("title")
    if description and description != metric.description:
        metric.description = description
        changed.append("description")
    if periods:
        normalized = sorted({str(period).strip() for period in periods if str(period).strip()})
        if normalized and sorted(metric.supported_periods or []) != normalized:
            metric.supported_periods = normalized
            changed.append("supported_periods")
    if metric.status == MetaMetricRegistry.STATUS_UNKNOWN:
        metric.status = MetaMetricRegistry.STATUS_ACTIVE
        changed.append("status")
    if changed:
        metric.save(update_fields=sorted(set(changed + ["updated_at"])))

