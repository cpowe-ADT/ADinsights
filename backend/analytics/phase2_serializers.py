from __future__ import annotations

from rest_framework import serializers

from .models import AISummary, ReportDefinition, ReportExportJob


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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


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
