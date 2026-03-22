from __future__ import annotations

from rest_framework import serializers
from integrations.models import GoogleAnalyticsConnection


class GoogleAnalyticsOAuthStartSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=False, allow_blank=True)
    runtime_context = serializers.DictField(required=False)


class GoogleAnalyticsOAuthExchangeSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, allow_blank=False)
    state = serializers.CharField(required=True, allow_blank=False)
    runtime_context = serializers.DictField(required=False)


class GoogleAnalyticsPropertiesQuerySerializer(serializers.Serializer):
    credential_id = serializers.UUIDField(required=False)


class GoogleAnalyticsProvisionSerializer(serializers.Serializer):
    credential_id = serializers.UUIDField(required=True)
    property_id = serializers.CharField(required=True, allow_blank=False)
    property_name = serializers.CharField(required=True, allow_blank=False)
    is_active = serializers.BooleanField(required=False, default=True)
    sync_frequency = serializers.CharField(required=False, default="daily")


class GoogleAnalyticsConnectionSerializer(serializers.ModelSerializer):
    credential_id = serializers.UUIDField(source="credentials_id", read_only=True)

    class Meta:
        model = GoogleAnalyticsConnection
        fields = [
            "id",
            "credential_id",
            "property_id",
            "property_name",
            "is_active",
            "sync_frequency",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "last_synced_at", "created_at", "updated_at"]


class GoogleAnalyticsStatusResponseSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google_analytics"])
    status = serializers.ChoiceField(
        choices=["not_connected", "started_not_complete", "complete", "active"]
    )
    reason = serializers.DictField()
    actions = serializers.ListField(child=serializers.CharField())
    last_checked_at = serializers.DateTimeField()
    last_synced_at = serializers.DateTimeField(allow_null=True)
    metadata = serializers.DictField()
