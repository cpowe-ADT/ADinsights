from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.db.utils import OperationalError, ProgrammingError

from integrations.meta_page_insights.metric_pack_loader import (
    is_blocked_metric,
    load_metric_pack_v1,
)
from integrations.models import MetaMetricRegistry
from integrations.services.meta_metric_catalog import load_metric_catalog

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
        "status": MetaMetricRegistry.STATUS_UNKNOWN,
        "replacement_metric_key": "",
        "is_default": False,
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
    (
        MetaMetricRegistry.LEVEL_PAGE,
        "page_impressions_unique",
    ): "page_total_media_view_unique",
    (MetaMetricRegistry.LEVEL_PAGE, "page_fans"): "page_follows",
    (MetaMetricRegistry.LEVEL_PAGE, "page_video_views_10s"): "page_video_views",
    (MetaMetricRegistry.LEVEL_POST, "post_impressions"): "post_media_view",
    (
        MetaMetricRegistry.LEVEL_POST,
        "post_impressions_unique",
    ): "post_total_media_view_unique",
    (MetaMetricRegistry.LEVEL_POST, "post_video_views_10s"): "post_video_views",
}

PAGE_PRODUCT_METRIC_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "page_reach": ("page_total_media_view_unique", "page_impressions_unique"),
    "page_impressions": ("page_media_view", "page_impressions"),
    "page_engagements": ("page_post_engagements",),
    "page_actions": ("page_total_actions",),
    "page_follows": ("page_daily_follows_unique", "page_follows"),
    "page_fans": ("page_follows", "page_fans"),
    "page_reactions_like": ("page_actions_post_reactions_like_total",),
    "page_reactions_love": ("page_actions_post_reactions_love_total",),
    "page_reactions_wow": ("page_actions_post_reactions_wow_total",),
}

POST_REACTION_PRODUCT_BREAKDOWN_KEYS: dict[str, str] = {
    "like": "post_reactions_like",
    "love": "post_reactions_love",
    "wow": "post_reactions_wow",
    "haha": "post_reactions_haha",
    "sorry": "post_reactions_sorry",
    "anger": "post_reactions_anger",
}

POST_REACTION_TOTAL_SOURCE_KEYS: tuple[str, ...] = (
    "post_reactions_like_total",
    "post_reactions_love_total",
    "post_reactions_wow_total",
    "post_reactions_haha_total",
    "post_reactions_sorry_total",
    "post_reactions_anger_total",
)

POST_PRODUCT_METRIC_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "post_impressions": ("post_media_view", "post_impressions"),
    "post_reach": (
        "post_total_media_view_unique",
        "post_impressions_unique",
        "post_impressions_organic_unique",
    ),
    "post_clicks": ("post_clicks",),
    "post_reactions": ("post_reactions_total",),
    "post_comments": ("post_comments_total", "post_comments"),
    "post_shares": ("post_shares_total", "post_shares"),
    "post_reactions_like": (
        "post_reactions_by_type_total",
        "post_reactions_like_total",
    ),
    "post_reactions_love": (
        "post_reactions_by_type_total",
        "post_reactions_love_total",
    ),
    "post_reactions_wow": ("post_reactions_by_type_total", "post_reactions_wow_total"),
    "post_reactions_haha": (
        "post_reactions_by_type_total",
        "post_reactions_haha_total",
    ),
    "post_reactions_sorry": (
        "post_reactions_by_type_total",
        "post_reactions_sorry_total",
    ),
    "post_reactions_anger": (
        "post_reactions_by_type_total",
        "post_reactions_anger_total",
    ),
}

CONTENT_OPS_POST_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "impressions": POST_PRODUCT_METRIC_SOURCE_KEYS["post_impressions"],
    "reach": POST_PRODUCT_METRIC_SOURCE_KEYS["post_reach"],
    "video_views": ("post_video_views", "post_video_views_organic"),
}


_metrics_seeded = False


def _reporting_default_source_keys(level: str) -> tuple[str, ...]:
    if level == MetaMetricRegistry.LEVEL_PAGE:
        mappings = PAGE_PRODUCT_METRIC_SOURCE_KEYS.values()
    elif level == MetaMetricRegistry.LEVEL_POST:
        mappings = POST_PRODUCT_METRIC_SOURCE_KEYS.values()
    else:
        return ()

    keys: list[str] = []
    for source_keys in mappings:
        for source_key in source_keys:
            if (
                source_key
                and source_key not in keys
                and not is_blocked_metric(source_key)
            ):
                keys.append(source_key)
    return tuple(keys)


def get_reporting_metric_source_map(
    dataset: str,
    level: str | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return provider metric keys used to hydrate stable product metrics."""

    if dataset == "organic_facebook_page":
        normalized_level = (level or "").strip().lower()
        if normalized_level == MetaMetricRegistry.LEVEL_POST.lower():
            return dict(POST_PRODUCT_METRIC_SOURCE_KEYS)
        if normalized_level == MetaMetricRegistry.LEVEL_PAGE.lower():
            return dict(PAGE_PRODUCT_METRIC_SOURCE_KEYS)
        return {**PAGE_PRODUCT_METRIC_SOURCE_KEYS, **POST_PRODUCT_METRIC_SOURCE_KEYS}
    if dataset == "content_ops":
        return {
            "content_ops_impressions": CONTENT_OPS_POST_SOURCE_KEYS["impressions"],
            "content_ops_reach": CONTENT_OPS_POST_SOURCE_KEYS["reach"],
            "content_ops_engagements": (
                "post_clicks",
                "post_reactions_by_type_total",
                *POST_REACTION_TOTAL_SOURCE_KEYS,
            ),
        }
    return {}


def get_reporting_metric_source_keys(
    dataset: str,
    product_metric: str,
    *,
    level: str | None = None,
) -> tuple[str, ...]:
    return get_reporting_metric_source_map(dataset, level=level).get(product_metric, ())


def get_content_ops_post_source_keys(field: str) -> tuple[str, ...]:
    return CONTENT_OPS_POST_SOURCE_KEYS.get(field, ())


def map_reporting_source_metric_to_product_metric(
    dataset: str,
    source_metric: str,
    *,
    breakdown_key: str | None = None,
    level: str | None = None,
) -> str | None:
    if source_metric in get_reporting_metric_source_map(dataset, level=level):
        return source_metric
    if (
        dataset == "organic_facebook_page"
        and source_metric == "post_reactions_by_type_total"
    ):
        normalized_breakdown = (breakdown_key or "").strip().lower()
        return POST_REACTION_PRODUCT_BREAKDOWN_KEYS.get(normalized_breakdown)

    for product_metric, source_keys in get_reporting_metric_source_map(
        dataset, level=level
    ).items():
        if (
            source_metric in source_keys
            and source_metric != "post_reactions_by_type_total"
        ):
            return product_metric
    return None


def ensure_default_metrics_seeded() -> None:
    global _metrics_seeded  # noqa: PLW0603
    if _metrics_seeded:
        return
    try:
        seed_default_metrics()
    except (OperationalError, ProgrammingError):
        return
    _metrics_seeded = True


def seed_default_metrics() -> None:
    loaded = _sync_canonical_metric_catalog()
    if loaded <= 0:
        loaded = load_metric_pack_v1()
    if loaded <= 0:
        _sync_fallback_metric_definitions()

    for metric in MetaMetricRegistry.objects.all():
        if not is_blocked_metric(metric.metric_key):
            continue
        replacement = REPLACEMENT_CANDIDATES.get((metric.level, metric.metric_key), "")
        metric.status = MetaMetricRegistry.STATUS_DEPRECATED
        metric.is_default = False
        if replacement:
            metric.replacement_metric_key = replacement
        metric.save(
            update_fields=[
                "status",
                "is_default",
                "replacement_metric_key",
                "updated_at",
            ]
        )


def _sync_canonical_metric_catalog() -> int:
    try:
        catalog = load_metric_catalog()
    except (OSError, ValueError):
        return 0

    synced = 0
    for definition in catalog:
        MetaMetricRegistry.objects.update_or_create(
            metric_key=definition["metric_key"],
            level=definition["level"],
            defaults={
                "supported_periods": definition["supported_periods"],
                "supports_breakdowns": definition["supports_breakdowns"],
                "status": definition["status"],
                "replacement_metric_key": definition["replacement_metric_key"],
                "is_default": definition["is_default"],
                "metadata": {
                    "provider": "meta",
                    "metric_catalog": "canonical",
                    **(
                        {"deprecated_on": definition["deprecated_on"]}
                        if definition.get("deprecated_on")
                        else {}
                    ),
                },
            },
        )
        synced += 1
    return synced


def _sync_fallback_metric_definitions() -> None:
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


def get_default_metric_keys(level: str) -> list[str]:
    ensure_default_metrics_seeded()
    reporting_source_keys = _reporting_default_source_keys(level)
    rows = (
        MetaMetricRegistry.objects.filter(
            level=level,
        )
        .exclude(
            status__in=[
                MetaMetricRegistry.STATUS_INVALID,
                MetaMetricRegistry.STATUS_DEPRECATED,
            ]
        )
        .filter(is_default=True)
        .order_by("metric_key")
        .values_list("metric_key", flat=True)
    )
    reporting_rows = set(
        MetaMetricRegistry.objects.filter(
            level=level, metric_key__in=reporting_source_keys
        )
        .exclude(
            status__in=[
                MetaMetricRegistry.STATUS_INVALID,
                MetaMetricRegistry.STATUS_DEPRECATED,
            ]
        )
        .values_list("metric_key", flat=True)
    )
    keys = [row for row in rows if not is_blocked_metric(row)]
    for source_key in reporting_source_keys:
        if source_key in reporting_rows and source_key not in keys:
            keys.append(source_key)
    return keys


def get_active_metric_keys(level: str, *, include_all: bool = False) -> list[str]:
    ensure_default_metrics_seeded()
    queryset = MetaMetricRegistry.objects.filter(level=level)
    if not include_all:
        queryset = queryset.exclude(
            status__in=[
                MetaMetricRegistry.STATUS_INVALID,
                MetaMetricRegistry.STATUS_DEPRECATED,
            ]
        )
    return [
        row
        for row in queryset.values_list("metric_key", flat=True)
        if not is_blocked_metric(row)
    ]


def resolve_metric_key(level: str, metric_key: str) -> str:
    if is_blocked_metric(metric_key):
        replacement = REPLACEMENT_CANDIDATES.get((level, metric_key))
        return replacement or metric_key
    ensure_default_metrics_seeded()
    metric = MetaMetricRegistry.objects.filter(
        level=level, metric_key=metric_key
    ).first()
    if metric is None:
        return metric_key
    if metric.status in {
        MetaMetricRegistry.STATUS_INVALID,
        MetaMetricRegistry.STATUS_DEPRECATED,
    }:
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
    metric.save(
        update_fields=["status", "is_default", "replacement_metric_key", "updated_at"]
    )
    return metric


def mark_metric_deprecated(
    level: str, metric_key: str, replacement_metric_key: str | None = None
) -> None:
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
    metric.save(
        update_fields=["status", "is_default", "replacement_metric_key", "updated_at"]
    )


def mark_metric_unknown(level: str, metric_key: str) -> None:
    metric, _ = MetaMetricRegistry.objects.get_or_create(
        metric_key=metric_key,
        level=level,
        defaults={
            "supported_periods": [],
            "supports_breakdowns": [],
        },
    )
    if metric.status in {
        MetaMetricRegistry.STATUS_INVALID,
        MetaMetricRegistry.STATUS_DEPRECATED,
    }:
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
        mark_metric_deprecated(
            level, metric_key, REPLACEMENT_CANDIDATES.get((level, metric_key))
        )
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
        normalized = sorted(
            {str(period).strip() for period in periods if str(period).strip()}
        )
        if normalized and sorted(metric.supported_periods or []) != normalized:
            metric.supported_periods = normalized
            changed.append("supported_periods")
    if metric.status == MetaMetricRegistry.STATUS_UNKNOWN:
        metric.status = MetaMetricRegistry.STATUS_ACTIVE
        changed.append("status")
    if changed:
        metric.save(update_fields=sorted(set(changed + ["updated_at"])))
