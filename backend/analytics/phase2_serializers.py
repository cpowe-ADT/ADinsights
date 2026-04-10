from __future__ import annotations

from rest_framework import serializers

from .models import AISummary, DashboardDefinition, ReportDefinition, ReportExportJob


class ReportDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportDefinition
        fields = [
            "id",
            "name",
            "description",
            "filters",
            "layout",
            "is_active",
            "schedule_enabled",
            "schedule_cron",
            "delivery_emails",
            "last_scheduled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "last_scheduled_at", "created_at", "updated_at"]


class DashboardDefinitionSerializer(serializers.ModelSerializer):
    owner_email = serializers.SerializerMethodField()

    class Meta:
        model = DashboardDefinition
        fields = [
            "id",
            "name",
            "description",
            "template_key",
            "filters",
            "layout",
            "default_metric",
            "is_active",
            "owner_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner_email", "created_at", "updated_at"]

    def get_owner_email(self, obj: DashboardDefinition) -> str | None:
        if obj.updated_by and obj.updated_by.email:
            return obj.updated_by.email
        if obj.created_by and obj.created_by.email:
            return obj.created_by.email
        return None


class ReportExportJobSerializer(serializers.ModelSerializer):
    report_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ReportExportJob
        fields = [
            "id",
            "report_id",
            "export_format",
            "status",
            "artifact_path",
            "error_message",
            "metadata",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "report_id",
            "status",
            "artifact_path",
            "error_message",
            "metadata",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class ReportExportCreateSerializer(serializers.Serializer):
    export_format = serializers.ChoiceField(
        choices=[
            ReportExportJob.FORMAT_CSV,
            ReportExportJob.FORMAT_PDF,
            ReportExportJob.FORMAT_PNG,
        ],
        default=ReportExportJob.FORMAT_CSV,
    )


class AISummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AISummary
        fields = [
            "id",
            "title",
            "summary",
            "payload",
            "source",
            "model_name",
            "status",
            "generated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
