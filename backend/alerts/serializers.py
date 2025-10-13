from __future__ import annotations

from rest_framework import serializers

from app.alerts import get_rule

from .models import AlertRun


class AlertRunSerializer(serializers.ModelSerializer):
    rule_name = serializers.SerializerMethodField()
    rule_description = serializers.SerializerMethodField()
    severity = serializers.SerializerMethodField()

    class Meta:
        model = AlertRun
        fields = [
            "id",
            "rule_slug",
            "rule_name",
            "rule_description",
            "severity",
            "status",
            "row_count",
            "llm_summary",
            "raw_results",
            "error_message",
            "duration_ms",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_rule_name(self, obj: AlertRun) -> str | None:
        try:
            return get_rule(obj.rule_slug).name
        except ValueError:
            return None

    def get_rule_description(self, obj: AlertRun) -> str | None:
        try:
            return get_rule(obj.rule_slug).description
        except ValueError:
            return None

    def get_severity(self, obj: AlertRun) -> str | None:
        try:
            return get_rule(obj.rule_slug).severity
        except ValueError:
            return None
