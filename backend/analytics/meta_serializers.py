"""Serializers for tenant-scoped Meta read APIs."""

from __future__ import annotations

from rest_framework import serializers

from .models import Ad, AdAccount, AdSet, Campaign, RawPerformanceRecord


class MetaAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdAccount
        fields = [
            "id",
            "external_id",
            "account_id",
            "name",
            "currency",
            "status",
            "business_name",
            "metadata",
            "created_time",
            "updated_time",
            "created_at",
            "updated_at",
        ]


class MetaCampaignSerializer(serializers.ModelSerializer):
    ad_account_external_id = serializers.CharField(source="ad_account.external_id", read_only=True)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "external_id",
            "name",
            "platform",
            "status",
            "objective",
            "currency",
            "account_external_id",
            "ad_account_external_id",
            "metadata",
            "created_time",
            "updated_time",
            "created_at",
            "updated_at",
        ]


class MetaAdSetSerializer(serializers.ModelSerializer):
    campaign_external_id = serializers.CharField(source="campaign.external_id", read_only=True)

    class Meta:
        model = AdSet
        fields = [
            "id",
            "external_id",
            "name",
            "status",
            "bid_strategy",
            "daily_budget",
            "start_time",
            "end_time",
            "targeting",
            "campaign_external_id",
            "created_at",
            "updated_at",
        ]


class MetaAdSerializer(serializers.ModelSerializer):
    adset_external_id = serializers.CharField(source="adset.external_id", read_only=True)

    class Meta:
        model = Ad
        fields = [
            "id",
            "external_id",
            "name",
            "status",
            "creative",
            "preview_url",
            "adset_external_id",
            "created_at",
            "updated_at",
        ]


class MetaInsightSerializer(serializers.ModelSerializer):
    campaign_external_id = serializers.CharField(source="campaign.external_id", read_only=True)
    adset_external_id = serializers.CharField(source="adset.external_id", read_only=True)
    ad_external_id = serializers.CharField(source="ad.external_id", read_only=True)
    account_external_id = serializers.CharField(source="ad_account.external_id", read_only=True)

    class Meta:
        model = RawPerformanceRecord
        fields = [
            "id",
            "external_id",
            "date",
            "source",
            "level",
            "impressions",
            "reach",
            "clicks",
            "spend",
            "cpc",
            "cpm",
            "conversions",
            "currency",
            "actions",
            "campaign_external_id",
            "adset_external_id",
            "ad_external_id",
            "account_external_id",
            "raw_payload",
            "ingested_at",
            "updated_at",
        ]


class MetaInsightsQuerySerializer(serializers.Serializer):
    account_id = serializers.CharField(required=False, allow_blank=False)
    level = serializers.ChoiceField(
        required=False,
        choices=["account", "campaign", "adset", "ad"],
    )
    since = serializers.DateField(required=False)
    until = serializers.DateField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        attrs = super().validate(attrs)
        since = attrs.get("since")
        until = attrs.get("until")
        if since and until and since > until:
            raise serializers.ValidationError({"until": "until must be on or after since"})
        return attrs
