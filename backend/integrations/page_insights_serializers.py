from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers

DATE_PRESET_CHOICES = ["last_7d", "last_28d", "last_90d"]


class DateRangeQuerySerializer(serializers.Serializer):
    date_preset = serializers.ChoiceField(choices=DATE_PRESET_CHOICES, required=False, default="last_28d")
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        since = attrs.get("since")
        until = attrs.get("until")
        if since is not None and until is not None and since > until:
            raise serializers.ValidationError({"since": "since must be <= until"})
        return attrs


class SyncTriggerSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["incremental", "backfill"], required=False, default="incremental")


class MetricTimeseriesQuerySerializer(serializers.Serializer):
    metric = serializers.CharField(required=True, allow_blank=False)
    period = serializers.ChoiceField(
        choices=["day", "week", "days_28", "lifetime", "month", "total_over_range"],
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

