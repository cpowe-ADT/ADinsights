from __future__ import annotations

from rest_framework import serializers


class GoogleAnalyticsOAuthStartSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=False, allow_blank=True)
    runtime_context = serializers.DictField(required=False)


class GoogleAnalyticsOAuthExchangeSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, allow_blank=False)
    state = serializers.CharField(required=True, allow_blank=False)
    runtime_context = serializers.DictField(required=False)


class GoogleAnalyticsProvisionSerializer(serializers.Serializer):
    credential_id = serializers.UUIDField(required=False)
    property_id = serializers.CharField(required=True, allow_blank=False)
    property_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    sync_frequency = serializers.CharField(required=False, allow_blank=True)
