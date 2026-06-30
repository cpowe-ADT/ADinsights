from __future__ import annotations

from uuid import UUID

from rest_framework import serializers

from app.alerts import get_rule
from integrations.models import AlertRuleDefinition

from .models import AlertRun

_DB_RULE_SLUG_PREFIX = "tenant_alert:"


def _get_rule_definition(slug: str) -> AlertRuleDefinition | None:
    if not slug.startswith(_DB_RULE_SLUG_PREFIX):
        return None
    raw_id = slug.removeprefix(_DB_RULE_SLUG_PREFIX)
    try:
        rule_id = UUID(raw_id)
    except ValueError:
        return None
    return AlertRuleDefinition.all_objects.filter(id=rule_id).first()


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
            definition = _get_rule_definition(obj.rule_slug)
            return definition.name if definition else None

    def get_rule_description(self, obj: AlertRun) -> str | None:
        try:
            return get_rule(obj.rule_slug).description
        except ValueError:
            definition = _get_rule_definition(obj.rule_slug)
            if definition is None:
                return None
            return (
                f"Tenant-defined threshold alert for {definition.metric} "
                f"{definition.comparison_operator} {definition.threshold} "
                f"over {definition.lookback_hours}h."
            )

    def get_severity(self, obj: AlertRun) -> str | None:
        try:
            return get_rule(obj.rule_slug).severity
        except ValueError:
            definition = _get_rule_definition(obj.rule_slug)
            return definition.severity if definition else None
