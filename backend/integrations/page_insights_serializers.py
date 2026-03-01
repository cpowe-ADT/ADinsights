from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers

DATE_PRESET_CHOICES = ["last_7d", "last_28d", "last_90d"]
PAGE_TREND_PERIOD_CHOICES = ["day", "week", "days_28"]
POST_PERIOD_CHOICES = ["day", "week", "days_28", "lifetime", "month", "total_over_range"]


class DateRangeQuerySerializer(serializers.Serializer):
    date_preset = serializers.ChoiceField(choices=DATE_PRESET_CHOICES, required=False, default="last_28d")
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500)
    offset = serializers.IntegerField(required=False, min_value=0)
    q = serializers.CharField(required=False, allow_blank=True)
    media_type = serializers.CharField(required=False, allow_blank=True)
    sort = serializers.ChoiceField(
        choices=["created_desc", "created_asc", "metric_desc", "metric_asc"],
        required=False,
        default="created_desc",
    )
    sort_metric = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        since = attrs.get("since")
        until = attrs.get("until")
        if since is not None and until is not None and since > until:
            raise serializers.ValidationError({"since": "since must be <= until"})
        sort = attrs.get("sort") or "created_desc"
        if sort.startswith("metric_") and not attrs.get("sort_metric"):
            raise serializers.ValidationError({"sort_metric": "sort_metric is required when sort is metric_asc/metric_desc"})
        return attrs


class SyncTriggerSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["incremental", "backfill"], required=False, default="incremental")


class MetricTimeseriesQuerySerializer(serializers.Serializer):
    metric = serializers.CharField(required=True, allow_blank=False)
    period = serializers.ChoiceField(
        choices=POST_PERIOD_CHOICES,
        required=False,
    )
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        since = attrs.get("since")
        until = attrs.get("until")
        if since is not None and until is not None and since > until:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


class PageTimeseriesQuerySerializer(serializers.Serializer):
    metric = serializers.CharField(required=True, allow_blank=False)
    period = serializers.ChoiceField(choices=PAGE_TREND_PERIOD_CHOICES, required=False, default="day")
    date_preset = serializers.ChoiceField(choices=DATE_PRESET_CHOICES, required=False, default="last_28d")
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        since = attrs.get("since")
        until = attrs.get("until")
        if since is not None and until is not None and since > until:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


class MetaPageExportCreateSerializer(serializers.Serializer):
    export_format = serializers.ChoiceField(choices=["csv", "pdf", "png"], required=False, default="csv")
    date_preset = serializers.ChoiceField(choices=DATE_PRESET_CHOICES, required=False, default="last_28d")
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)
    trend_metric = serializers.CharField(required=False, allow_blank=False)
    trend_period = serializers.ChoiceField(choices=PAGE_TREND_PERIOD_CHOICES, required=False, default="day")
    posts_metric = serializers.CharField(required=False, allow_blank=False)
    posts_sort = serializers.ChoiceField(
        choices=["created_desc", "metric_desc"],
        required=False,
        default="created_desc",
    )
    q = serializers.CharField(required=False, allow_blank=True)
    media_type = serializers.CharField(required=False, allow_blank=True)
    posts_limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=10)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        since = attrs.get("since")
        until = attrs.get("until")
        if since is not None and until is not None and since > until:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


def resolve_date_range(
    *,
    date_preset: str,
    since: date | None,
    until: date | None,
) -> tuple[date, date]:
    if since is not None and until is not None:
        return since, until

    anchor = timezone.localdate() - timedelta(days=1)
    if date_preset == "last_7d":
        return anchor - timedelta(days=6), anchor
    if date_preset == "last_90d":
        return anchor - timedelta(days=89), anchor
    # default: last_28d
    return anchor - timedelta(days=27), anchor
