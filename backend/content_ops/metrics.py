"""Organic metric refresh helpers for Content Operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from integrations.models import MetaPost, MetaPostInsightPoint
from integrations.services.metric_registry import (
    POST_REACTION_PRODUCT_BREAKDOWN_KEYS,
    POST_REACTION_TOTAL_SOURCE_KEYS,
    get_content_ops_post_source_keys,
)

from .models import OrganicPostMetricSnapshot, PublishedPost

METRIC_SOURCE_META_POST_INSIGHTS = "meta_post_insights"

REACTION_METRIC_KEYS = (
    *POST_REACTION_TOTAL_SOURCE_KEYS,
)
REACTION_BREAKDOWN_KEYS = set(POST_REACTION_PRODUCT_BREAKDOWN_KEYS)
IMPRESSION_METRIC_KEYS = get_content_ops_post_source_keys("impressions")
REACH_METRIC_KEYS = get_content_ops_post_source_keys("reach")
VIDEO_VIEW_METRIC_KEYS = get_content_ops_post_source_keys("video_views")


@dataclass(frozen=True)
class OrganicMetricSnapshotPayload:
    metric_date: date
    impressions: int = 0
    reach: int = 0
    engagements: int = 0
    clicks: int = 0
    saves: int = 0
    shares: int = 0
    video_views: int = 0
    source: str = METRIC_SOURCE_META_POST_INSIGHTS


@dataclass(frozen=True)
class OrganicMetricRefreshResult:
    status: str
    published_post_id: str = ""
    snapshot_id: str = ""
    reporting_link_state: str = ""
    reason: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "published_post_id": self.published_post_id,
            "snapshot_id": self.snapshot_id,
            "reporting_link_state": self.reporting_link_state,
            "reason": self.reason,
        }


class OrganicMetricsProvider(Protocol):
    def fetch_snapshot(self, post: PublishedPost) -> OrganicMetricSnapshotPayload | None:
        """Return one aggregate snapshot for a Content Ops published post."""


class SyncedMetaPostInsightsProvider:
    """Bridge already-synced Meta post insight rows into Content Ops aggregates."""

    def fetch_snapshot(self, post: PublishedPost) -> OrganicMetricSnapshotPayload | None:
        if post.channel != PublishedPost.CHANNEL_FACEBOOK_PAGE:
            return None
        meta_post = (
            MetaPost.all_objects.filter(
                tenant=post.tenant,
                post_id=post.meta_post_id,
            )
            .order_by("-updated_at")
            .first()
        )
        if meta_post is None:
            return None

        points = MetaPostInsightPoint.all_objects.filter(
            tenant=post.tenant,
            post=meta_post,
        )
        latest_end_time = points.order_by("-end_time").values_list("end_time", flat=True).first()
        if latest_end_time is None:
            return None
        metric_date = latest_end_time.date()
        current_points = points.filter(end_time=latest_end_time)
        clicks = _metric_sum(current_points, "post_clicks")
        reactions = _reaction_sum(current_points)
        return OrganicMetricSnapshotPayload(
            metric_date=metric_date,
            impressions=_first_metric_sum(current_points, IMPRESSION_METRIC_KEYS),
            reach=_first_metric_sum(current_points, REACH_METRIC_KEYS),
            engagements=clicks + reactions,
            clicks=clicks,
            video_views=_first_metric_sum(current_points, VIDEO_VIEW_METRIC_KEYS),
            source=METRIC_SOURCE_META_POST_INSIGHTS,
        )


def refresh_published_post_metrics(
    *,
    tenant,
    published_post_id,
    provider: OrganicMetricsProvider | None = None,
    now=None,
) -> OrganicMetricRefreshResult:
    """Refresh one Content Ops published post from a fakeable metric provider."""

    now = now or timezone.now()
    post = (
        PublishedPost.all_objects.select_related("tenant")
        .filter(tenant=tenant, id=published_post_id)
        .first()
    )
    if post is None:
        return OrganicMetricRefreshResult(status="noop", reason="published_post_missing")

    selected_provider = provider or SyncedMetaPostInsightsProvider()
    payload = selected_provider.fetch_snapshot(post)
    if payload is None:
        _mark_reporting_state(
            post=post,
            state=PublishedPost.REPORTING_UNAVAILABLE,
            refreshed_at=now,
        )
        return OrganicMetricRefreshResult(
            status="unavailable",
            published_post_id=str(post.id),
            reporting_link_state=PublishedPost.REPORTING_UNAVAILABLE,
            reason="organic_metrics_unavailable",
        )

    with transaction.atomic():
        snapshot, _ = OrganicPostMetricSnapshot.all_objects.update_or_create(
            tenant=tenant,
            published_post=post,
            metric_date=payload.metric_date,
            channel=post.channel,
            source=payload.source,
            defaults={
                "impressions": payload.impressions,
                "reach": payload.reach,
                "engagements": payload.engagements,
                "clicks": payload.clicks,
                "saves": payload.saves,
                "shares": payload.shares,
                "video_views": payload.video_views,
                "fetched_at": now,
            },
        )
        post.reporting_link_state = PublishedPost.REPORTING_LINKED
        post.last_metrics_refresh_at = now
        post.save(update_fields=["reporting_link_state", "last_metrics_refresh_at", "updated_at"])
    return OrganicMetricRefreshResult(
        status="refreshed",
        published_post_id=str(post.id),
        snapshot_id=str(snapshot.id),
        reporting_link_state=PublishedPost.REPORTING_LINKED,
    )


def _mark_reporting_state(*, post: PublishedPost, state: str, refreshed_at) -> None:
    post.reporting_link_state = state
    post.last_metrics_refresh_at = refreshed_at
    post.save(update_fields=["reporting_link_state", "last_metrics_refresh_at", "updated_at"])


def _metric_sum(queryset, metric_key: str) -> int:
    total = queryset.filter(metric_key=metric_key).aggregate(total=Sum("value_num"))["total"]
    if total is None:
        return 0
    if isinstance(total, Decimal):
        return int(total)
    return int(total or 0)


def _first_metric_sum(queryset, metric_keys: tuple[str, ...]) -> int:
    for metric_key in metric_keys:
        total = _metric_sum(queryset, metric_key)
        if total:
            return total
    return 0


def _reaction_sum(queryset) -> int:
    total = sum(_metric_sum(queryset, key) for key in REACTION_METRIC_KEYS)
    if total:
        return total

    by_type_total = queryset.filter(metric_key="post_reactions_by_type_total")
    total = by_type_total.filter(
        breakdown_key_normalized__in=REACTION_BREAKDOWN_KEYS,
    ).aggregate(total=Sum("value_num"))["total"]
    if total is None:
        total = by_type_total.filter(
            breakdown_key__in=REACTION_BREAKDOWN_KEYS,
        ).aggregate(total=Sum("value_num"))["total"]
    if total is None:
        return 0
    if isinstance(total, Decimal):
        return int(total)
    return int(total or 0)
