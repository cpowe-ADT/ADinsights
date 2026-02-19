from __future__ import annotations

from rest_framework import serializers
from django.utils import timezone
from croniter import croniter

from accounts.models import Tenant
from .models import (
    AirbyteConnection,
    AlertRuleDefinition,
    CampaignBudget,
    MetaAccountSyncState,
    PlatformCredential,
)


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
            "auth_mode",
            "granted_scopes",
            "declined_scopes",
            "issued_at",
            "last_validated_at",
            "last_refresh_attempt_at",
            "last_refreshed_at",
            "token_status",
            "token_status_reason",
            "expires_at",
            "created_at",
            "updated_at",
            "access_token",
            "refresh_token",
        ]
        read_only_fields = [
            "id",
            "auth_mode",
            "granted_scopes",
            "declined_scopes",
            "issued_at",
            "last_validated_at",
            "last_refresh_attempt_at",
            "last_refreshed_at",
            "token_status",
            "token_status_reason",
            "created_at",
            "updated_at",
        ]

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


class MetaOAuthExchangeSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, allow_blank=False)
    state = serializers.CharField(required=True, allow_blank=False)


class MetaSystemTokenSerializer(serializers.Serializer):
    account_id = serializers.CharField(required=True, allow_blank=False)
    access_token = serializers.CharField(required=True, allow_blank=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    granted_scopes = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
    )


class MetaOAuthStartSerializer(serializers.Serializer):
    auth_type = serializers.ChoiceField(
        choices=["rerequest"],
        required=False,
    )


class MetaPageConnectSerializer(serializers.Serializer):
    selection_token = serializers.CharField(required=True, allow_blank=False)
    page_id = serializers.CharField(required=True, allow_blank=False)
    ad_account_id = serializers.CharField(required=True, allow_blank=False)
    instagram_account_id = serializers.CharField(required=False, allow_blank=True)


class MetaProvisionSerializer(serializers.Serializer):
    external_account_id = serializers.CharField(required=False, allow_blank=True)
    workspace_id = serializers.UUIDField(required=False, allow_null=True)
    destination_id = serializers.UUIDField(required=False, allow_null=True)
    source_definition_id = serializers.UUIDField(required=False, allow_null=True)
    connection_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    schedule_type = serializers.ChoiceField(
        choices=AirbyteConnection.SCHEDULE_CHOICES,
        required=False,
    )
    interval_minutes = serializers.IntegerField(required=False, allow_null=True)
    cron_expression = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):  # type: ignore[override]
        attrs = super().validate(attrs)
        schedule_type = attrs.get("schedule_type", AirbyteConnection.SCHEDULE_CRON)
        interval_minutes = attrs.get("interval_minutes")
        cron_expression = (attrs.get("cron_expression") or "").strip()
        if schedule_type == AirbyteConnection.SCHEDULE_INTERVAL:
            if interval_minutes is None or int(interval_minutes) <= 0:
                raise serializers.ValidationError(
                    {"interval_minutes": "Interval minutes are required for interval schedules."}
                )
            attrs["cron_expression"] = ""
        elif schedule_type == AirbyteConnection.SCHEDULE_CRON:
            if not cron_expression:
                raise serializers.ValidationError(
                    {"cron_expression": "Cron expression is required for cron schedules."}
                )
            attrs["cron_expression"] = cron_expression
            attrs["interval_minutes"] = None
        else:
            attrs["interval_minutes"] = None
            attrs["cron_expression"] = ""
        return attrs


class AirbyteConnectionSerializer(serializers.ModelSerializer):
    connection_id = serializers.UUIDField()
    workspace_id = serializers.UUIDField(required=False, allow_null=True)
    schedule_type = serializers.ChoiceField(
        choices=AirbyteConnection.SCHEDULE_CHOICES, required=False
    )
    interval_minutes = serializers.IntegerField(required=False, allow_null=True)
    cron_expression = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = AirbyteConnection
        fields = [
            "id",
            "name",
            "connection_id",
            "workspace_id",
            "provider",
            "schedule_type",
            "interval_minutes",
            "cron_expression",
            "is_active",
            "last_synced_at",
            "last_job_id",
            "last_job_status",
            "last_job_created_at",
            "last_job_updated_at",
            "last_job_completed_at",
            "last_job_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_synced_at",
            "last_job_id",
            "last_job_status",
            "last_job_created_at",
            "last_job_updated_at",
            "last_job_completed_at",
            "last_job_error",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        attrs = super().validate(attrs)

        schedule_type = attrs.get("schedule_type")
        if schedule_type is None and self.instance is not None:
            schedule_type = self.instance.schedule_type
        if schedule_type is None:
            schedule_type = AirbyteConnection.SCHEDULE_INTERVAL

        interval_minutes = (
            attrs.get("interval_minutes")
            if "interval_minutes" in attrs
            else getattr(self.instance, "interval_minutes", None)
        )
        cron_expression = (
            attrs.get("cron_expression")
            if "cron_expression" in attrs
            else getattr(self.instance, "cron_expression", "")
        )
        cron_expression_value = cron_expression.strip() if isinstance(cron_expression, str) else ""

        if schedule_type == AirbyteConnection.SCHEDULE_INTERVAL:
            if interval_minutes is None:
                raise serializers.ValidationError(
                    {"interval_minutes": "Interval minutes are required for interval schedules."}
                )
            if interval_minutes <= 0:
                raise serializers.ValidationError(
                    {"interval_minutes": "Interval minutes must be positive."}
                )
            if "cron_expression" in attrs:
                if cron_expression_value:
                    raise serializers.ValidationError(
                        {"cron_expression": "Cron expression is only valid for cron schedules."}
                    )
                attrs["cron_expression"] = ""
            elif "schedule_type" in attrs:
                attrs["cron_expression"] = ""

        elif schedule_type == AirbyteConnection.SCHEDULE_CRON:
            if not cron_expression_value:
                raise serializers.ValidationError(
                    {"cron_expression": "Cron expression is required for cron schedules."}
                )
            try:
                croniter(cron_expression_value, timezone.now())
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    {"cron_expression": "Cron expression is invalid."}
                ) from exc
            attrs["cron_expression"] = cron_expression_value
            if "interval_minutes" in attrs and attrs["interval_minutes"] is not None:
                raise serializers.ValidationError(
                    {"interval_minutes": "Interval minutes are only valid for interval schedules."}
                )
            if "schedule_type" in attrs:
                attrs["interval_minutes"] = None

        elif schedule_type == AirbyteConnection.SCHEDULE_MANUAL:
            if "interval_minutes" in attrs and attrs["interval_minutes"] is not None:
                raise serializers.ValidationError(
                    {"interval_minutes": "Interval minutes are not allowed for manual schedules."}
                )
            if "cron_expression" in attrs and cron_expression_value:
                raise serializers.ValidationError(
                    {"cron_expression": "Cron expression is not allowed for manual schedules."}
                )
            if "schedule_type" in attrs:
                attrs.setdefault("interval_minutes", None)
                attrs.setdefault("cron_expression", "")

        return attrs


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


class SocialPlatformStatusSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=["meta", "instagram"])
    display_name = serializers.CharField()
    status = serializers.ChoiceField(
        choices=["not_connected", "started_not_complete", "complete", "active"]
    )
    reason = serializers.DictField()
    last_checked_at = serializers.DateTimeField(allow_null=True)
    last_synced_at = serializers.DateTimeField(allow_null=True)
    actions = serializers.ListField(child=serializers.CharField())
    metadata = serializers.DictField()


class SocialConnectionStatusResponseSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    platforms = SocialPlatformStatusSerializer(many=True)


class MetaAccountSyncStateSerializer(serializers.ModelSerializer):
    connection_id = serializers.SerializerMethodField()

    class Meta:
        model = MetaAccountSyncState
        fields = [
            "account_id",
            "connection_id",
            "last_job_id",
            "last_job_status",
            "last_job_error",
            "last_sync_started_at",
            "last_sync_completed_at",
            "last_success_at",
            "last_window_start",
            "last_window_end",
            "updated_at",
        ]
        read_only_fields = fields

    def get_connection_id(self, obj: MetaAccountSyncState) -> str | None:
        if obj.connection_id is None:
            return None
        return str(obj.connection.connection_id)
