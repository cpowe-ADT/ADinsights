from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers


DATE_PRESET_CHOICES = [
    "today",
    "yesterday",
    "last_7d",
    "last_14d",
    "last_28d",
    "last_30d",
    "last_90d",
]


class MetaOAuthCallbackSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, allow_blank=False)
    state = serializers.CharField(required=True, allow_blank=False)
    runtime_context = serializers.DictField(required=False)


class MetaPageResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="pk")
    page_id = serializers.CharField()
    name = serializers.CharField()
    can_analyze = serializers.BooleanField()
    is_default = serializers.BooleanField()
    tasks = serializers.ListField(child=serializers.CharField(), required=False)
    perms = serializers.ListField(child=serializers.CharField(), required=False)


class MetaPageSelectResponseSerializer(serializers.Serializer):
    page_id = serializers.CharField()
    selected = serializers.BooleanField()


class MetaRefreshSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["incremental", "backfill"], required=False)
    metrics = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=False,
    )


class MetaOverviewQuerySerializer(serializers.Serializer):
    date_preset = serializers.ChoiceField(choices=DATE_PRESET_CHOICES, required=False)
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        if attrs.get("since") and attrs.get("until") and attrs["since"] > attrs["until"]:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


class MetaTimeseriesQuerySerializer(serializers.Serializer):
    metric = serializers.CharField(required=True, allow_blank=False)
    period = serializers.ChoiceField(
        choices=["day", "week", "days_28", "lifetime", "month", "total_over_range"],
        required=False,
    )
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        if attrs.get("since") and attrs.get("until") and attrs["since"] > attrs["until"]:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


class MetaPostsQuerySerializer(serializers.Serializer):
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        if attrs.get("since") and attrs.get("until") and attrs["since"] > attrs["until"]:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


class MetaPostTimeseriesQuerySerializer(serializers.Serializer):
    metric = serializers.CharField(required=True, allow_blank=False)
    period = serializers.ChoiceField(
        choices=["day", "week", "days_28", "lifetime", "month", "total_over_range"],
        required=False,
    )
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        if attrs.get("since") and attrs.get("until") and attrs["since"] > attrs["until"]:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


class MetaMetricOptionSerializer(serializers.Serializer):
    metric_key = serializers.CharField()
    level = serializers.CharField()
    status = serializers.CharField()
    replacement_metric_key = serializers.CharField(allow_blank=True)
    title = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)


class MetaOverviewCardSerializer(serializers.Serializer):
    metric_key = serializers.CharField()
    display_metric_key = serializers.CharField(required=False)
    status = serializers.CharField()
    replacement_metric_key = serializers.CharField(allow_blank=True)
    value_today = serializers.DecimalField(max_digits=20, decimal_places=6, allow_null=True)
    value_range = serializers.DecimalField(max_digits=20, decimal_places=6, allow_null=True)


class MetaTimeseriesPointSerializer(serializers.Serializer):
    end_time = serializers.DateTimeField()
    value = serializers.DecimalField(max_digits=20, decimal_places=6, allow_null=True)


class MetaPostsItemSerializer(serializers.Serializer):
    post_id = serializers.CharField()
    created_time = serializers.DateTimeField(allow_null=True)
    permalink_url = serializers.CharField(allow_blank=True)
    message = serializers.CharField(allow_blank=True)
    metrics = serializers.DictField(required=False)


class MetaDefaultDateRangeSerializer(serializers.Serializer):
    since = serializers.DateField()
    until = serializers.DateField()


def resolve_date_range(
    *,
    preset: str | None,
    since: date | None,
    until: date | None,
) -> tuple[date, date]:
    if since and until:
        return since, until

    today = timezone.localdate()
    if preset == "today":
        return today, today
    if preset == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if preset == "last_7d":
        return today - timedelta(days=7), today
    if preset == "last_14d":
        return today - timedelta(days=14), today
    if preset == "last_30d":
        return today - timedelta(days=30), today
    if preset == "last_90d":
        return today - timedelta(days=90), today
    # Default last_28d
    return today - timedelta(days=28), today
