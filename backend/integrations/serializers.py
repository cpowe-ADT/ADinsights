from __future__ import annotations

from rest_framework import serializers

from accounts.models import Tenant
from .models import AlertRuleDefinition, CampaignBudget, PlatformCredential


class PlatformCredentialSerializer(serializers.ModelSerializer):
    access_token = serializers.CharField(write_only=True, required=True)
    refresh_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    class Meta:
        model = PlatformCredential
        fields = [
            "id",
            "provider",
            "account_id",
            "expires_at",
            "created_at",
            "updated_at",
            "access_token",
            "refresh_token",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        access_token = validated_data.pop("access_token")
        refresh_token = validated_data.pop("refresh_token", None)
        tenant: Tenant = self.context["request"].user.tenant
        credential = PlatformCredential(tenant=tenant, **validated_data)
        if refresh_token is None:
            credential.mark_refresh_token_for_clear()
        credential.set_raw_tokens(access_token, refresh_token)
        credential.save()
        return credential

    def update(self, instance, validated_data):
        access_token = validated_data.pop("access_token", serializers.empty)
        refresh_token = validated_data.pop("refresh_token", serializers.empty)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if refresh_token is None:
            instance.mark_refresh_token_for_clear()
        if access_token is not serializers.empty or refresh_token is not serializers.empty:
            instance.set_raw_tokens(
                None if access_token is serializers.empty else access_token,
                None if refresh_token is serializers.empty else refresh_token,
            )
        instance.save()
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep.pop("access_token", None)
        rep.pop("refresh_token", None)
        return rep


class CampaignBudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignBudget
        fields = [
            "id",
            "name",
            "monthly_target",
            "currency",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_monthly_target(self, value):  # type: ignore[override]
        if value <= 0:
            raise serializers.ValidationError("Monthly target must be positive.")
        return value

    def validate_currency(self, value):  # type: ignore[override]
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Currency must be a 3 letter code.")
        return value.upper()

    def create(self, validated_data):
        tenant = validated_data.pop("tenant", None)
        if tenant is None:
            request = self.context.get("request")
            if request is None or not hasattr(request, "user"):
                raise serializers.ValidationError("Request context is required.")
            tenant = request.user.tenant
        return CampaignBudget.objects.create(tenant=tenant, **validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AlertRuleDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRuleDefinition
        fields = [
            "id",
            "name",
            "metric",
            "comparison_operator",
            "threshold",
            "lookback_hours",
            "severity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_threshold(self, value):  # type: ignore[override]
        if value <= 0:
            raise serializers.ValidationError("Threshold must be positive.")
        return value

    def validate_lookback_hours(self, value):  # type: ignore[override]
        if value <= 0:
            raise serializers.ValidationError("Lookback hours must be positive.")
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        if request is None or not hasattr(request, "user"):
            raise serializers.ValidationError("Request context is required.")
        tenant = request.user.tenant
        return AlertRuleDefinition.objects.create(
            tenant=tenant, **validated_data
        )

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
