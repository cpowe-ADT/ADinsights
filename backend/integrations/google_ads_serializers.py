from __future__ import annotations

from rest_framework import serializers

from integrations.models import AirbyteConnection


class GoogleAdsOAuthStartSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=False, allow_blank=True)
    runtime_context = serializers.DictField(required=False)


class GoogleAdsOAuthExchangeSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, allow_blank=False)
    state = serializers.CharField(required=True, allow_blank=False)
    customer_id = serializers.CharField(required=True, allow_blank=False)
    login_customer_id = serializers.CharField(required=False, allow_blank=True)
    runtime_context = serializers.DictField(required=False)


class GoogleAdsProvisionSerializer(serializers.Serializer):
    external_account_id = serializers.CharField(required=False, allow_blank=True)
    login_customer_id = serializers.CharField(required=False, allow_blank=True)
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
    sync_engine = serializers.ChoiceField(
        choices=["sdk", "airbyte"],
        required=False,
    )

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


class GoogleAdsStatusResponseSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google_ads"])
    status = serializers.ChoiceField(
        choices=["not_connected", "started_not_complete", "complete", "active"]
    )
    reason = serializers.DictField()
    actions = serializers.ListField(child=serializers.CharField())
    last_checked_at = serializers.DateTimeField()
    last_synced_at = serializers.DateTimeField(allow_null=True)
    sync_engine = serializers.ChoiceField(choices=["sdk", "airbyte"], required=False)
    fallback_active = serializers.BooleanField(required=False)
    parity_state = serializers.ChoiceField(
        choices=["unknown", "pass", "fail"],
        required=False,
    )
    last_parity_passed_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.DictField()
