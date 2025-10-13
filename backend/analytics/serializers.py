"""Serializers for analytics endpoints."""

from __future__ import annotations

from rest_framework import serializers


class MetricsQueryParamsSerializer(serializers.Serializer):
    """Validate metrics query parameters."""

    start_date = serializers.DateField()
    end_date = serializers.DateField()
    parish = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"non_field_errors": ["start_date must be before or equal to end_date."]}
            )
        return attrs


class MetricRecordSerializer(serializers.Serializer):
    """Serialize a campaign metric record."""

    date = serializers.DateField()
    platform = serializers.CharField()
    campaign = serializers.CharField()
    parish = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    impressions = serializers.IntegerField()
    clicks = serializers.IntegerField()
    spend = serializers.FloatField()
    conversions = serializers.IntegerField()
    roas = serializers.FloatField()
