"""Serializers for analytics endpoints."""

from __future__ import annotations

from rest_framework import serializers

from .models import Ad, AdSet, Campaign, RawPerformanceRecord


class TenantScopedSerializerMixin:
    """Helpers for enforcing tenant scoping on related objects."""

    def _get_request_tenant_id(self) -> str | None:
        request = self.context.get("request")
        if not request:
            return None
        user = getattr(request, "user", None)
        if user is None:
            return None
        tenant_id = getattr(user, "tenant_id", None)
        return str(tenant_id) if tenant_id is not None else None

    def _ensure_tenant_match(self, value, field_name: str):
        tenant_id = self._get_request_tenant_id()
        if tenant_id is None or value is None:
            return value
        if str(value.tenant_id) != tenant_id:
            raise serializers.ValidationError(
                {field_name: "Object does not belong to this tenant."}
            )
        return value


class CampaignSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            "id",
            "external_id",
            "name",
            "platform",
            "account_external_id",
            "status",
            "objective",
            "currency",
            "metadata",
            "created_time",
            "updated_time",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AdSetSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = AdSet
        fields = [
            "id",
            "campaign",
            "external_id",
            "name",
            "status",
            "bid_strategy",
            "daily_budget",
            "start_time",
            "end_time",
            "targeting",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_campaign(self, campaign: Campaign) -> Campaign:
        return self._ensure_tenant_match(campaign, "campaign")


class AdSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = [
            "id",
            "adset",
            "external_id",
            "name",
            "status",
            "creative",
            "preview_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_adset(self, adset: AdSet) -> AdSet:
        return self._ensure_tenant_match(adset, "adset")


class RawPerformanceRecordSerializer(
    TenantScopedSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RawPerformanceRecord
        fields = [
            "id",
            "external_id",
            "date",
            "source",
            "campaign",
            "adset",
            "ad",
            "impressions",
            "clicks",
            "spend",
            "currency",
            "conversions",
            "raw_payload",
            "ingested_at",
            "updated_at",
        ]
        read_only_fields = ["id", "ingested_at", "updated_at"]

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        attrs = super().validate(attrs)

        campaign = attrs.get("campaign") or getattr(self.instance, "campaign", None)
        adset = attrs.get("adset") or getattr(self.instance, "adset", None)
        ad = attrs.get("ad") or getattr(self.instance, "ad", None)

        if campaign is not None:
            self._ensure_tenant_match(campaign, "campaign")
        if adset is not None:
            self._ensure_tenant_match(adset, "adset")
        if ad is not None:
            self._ensure_tenant_match(ad, "ad")

        if campaign is not None and adset is not None:
            if adset.campaign_id != campaign.id:
                raise serializers.ValidationError(
                    {"adset": "Ad set does not belong to the provided campaign."}
                )
        if ad is not None and adset is not None:
            if ad.adset_id != adset.id:
                raise serializers.ValidationError(
                    {"ad": "Ad does not belong to the provided ad set."}
                )
        if ad is not None and campaign is not None:
            if ad.adset.campaign_id != campaign.id:
                raise serializers.ValidationError(
                    {"ad": "Ad does not belong to the provided campaign."}
                )

        return attrs


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
    campaign = CampaignPerformanceSerializer()
    creative = CreativePerformanceRowSerializer(many=True)
    budget = BudgetPacingRowSerializer(many=True)
    parish = ParishAggregateSerializer(many=True)


class AggregateSnapshotSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    generated_at = serializers.DateTimeField()
    metrics = AggregateMetricsSerializer()
