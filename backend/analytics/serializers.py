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


class CampaignSummarySerializer(serializers.Serializer):
    currency = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    totalSpend = serializers.FloatField()
    totalImpressions = serializers.IntegerField()
    totalClicks = serializers.IntegerField()
    totalConversions = serializers.IntegerField()
    averageRoas = serializers.FloatField()


class CampaignTrendPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    spend = serializers.FloatField()
    impressions = serializers.IntegerField()
    clicks = serializers.IntegerField()
    conversions = serializers.IntegerField()


class CampaignRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    platform = serializers.CharField()
    status = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    parish = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    spend = serializers.FloatField()
    impressions = serializers.IntegerField()
    clicks = serializers.IntegerField()
    conversions = serializers.IntegerField()
    roas = serializers.FloatField()


class CampaignPerformanceSerializer(serializers.Serializer):
    summary = CampaignSummarySerializer()
    trend = CampaignTrendPointSerializer(many=True)
    rows = CampaignRowSerializer(many=True)


class CreativePerformanceRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    campaignId = serializers.CharField()
    campaignName = serializers.CharField()
    platform = serializers.CharField()
    parish = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    spend = serializers.FloatField()
    impressions = serializers.IntegerField()
    clicks = serializers.IntegerField()
    conversions = serializers.IntegerField()
    roas = serializers.FloatField()


class BudgetPacingRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    campaignName = serializers.CharField()
    parishes = serializers.ListField(
        child=serializers.CharField(), allow_empty=True
    )
    monthlyBudget = serializers.FloatField()
    spendToDate = serializers.FloatField()
    projectedSpend = serializers.FloatField()
    pacingPercent = serializers.FloatField()


class ParishAggregateSerializer(serializers.Serializer):
    parish = serializers.CharField()
    spend = serializers.FloatField()
    impressions = serializers.IntegerField()
    clicks = serializers.IntegerField()
    conversions = serializers.IntegerField()
    roas = serializers.FloatField()
    campaignCount = serializers.IntegerField()
    currency = serializers.CharField(allow_blank=True, allow_null=True, required=False)


class AggregateMetricsSerializer(serializers.Serializer):
    campaign_metrics = CampaignPerformanceSerializer()
    creative_metrics = CreativePerformanceRowSerializer(many=True)
    budget_metrics = BudgetPacingRowSerializer(many=True)
    parish_metrics = ParishAggregateSerializer(many=True)


class AggregateSnapshotSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    generated_at = serializers.DateTimeField()
    metrics = AggregateMetricsSerializer()
