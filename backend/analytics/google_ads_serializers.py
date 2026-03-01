from __future__ import annotations

from datetime import date, timedelta

from rest_framework import serializers

from analytics.models import GoogleAdsExportJob, GoogleAdsSavedView
from integrations.models import GoogleAdsAccountAssignment


class GoogleAdsDateRangeQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    customer_id = serializers.CharField(required=False, allow_blank=False)
    campaign_id = serializers.CharField(required=False, allow_blank=False)
    compare = serializers.ChoiceField(
        choices=["none", "dod", "wow", "mom", "yoy"],
        required=False,
        default="none",
    )

    def validate(self, attrs):
        today = date.today()
        end_date = attrs.get("end_date", today)
        start_date = attrs.get("start_date", end_date - timedelta(days=29))
        if start_date > end_date:
            raise serializers.ValidationError("start_date must be before or equal to end_date")
        attrs["start_date"] = start_date
        attrs["end_date"] = end_date
        return attrs


class GoogleAdsListQuerySerializer(GoogleAdsDateRangeQuerySerializer):
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    sort = serializers.CharField(required=False, default="-spend")
    q = serializers.CharField(required=False, allow_blank=True, default="")


class GoogleAdsExecutiveQuerySerializer(GoogleAdsDateRangeQuerySerializer):
    budget_status = serializers.CharField(required=False, allow_blank=True)
    campaign_type = serializers.CharField(required=False, allow_blank=True)
    brand_only = serializers.BooleanField(required=False, default=False)


class GoogleAdsBreakdownQuerySerializer(GoogleAdsDateRangeQuerySerializer):
    dimension = serializers.ChoiceField(
        choices=["location", "device", "time_of_day", "audience", "demographic"],
        required=False,
        default="location",
    )


class GoogleAdsSavedViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAdsSavedView
        fields = [
            "id",
            "name",
            "description",
            "filters",
            "columns",
            "is_shared",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GoogleAdsExportCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, default="")
    export_format = serializers.ChoiceField(
        choices=[GoogleAdsExportJob.FORMAT_CSV, GoogleAdsExportJob.FORMAT_PDF],
        default=GoogleAdsExportJob.FORMAT_CSV,
    )
    filters = serializers.JSONField(required=False)


class GoogleAdsExportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAdsExportJob
        fields = [
            "id",
            "name",
            "export_format",
            "filters",
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
            "status",
            "artifact_path",
            "error_message",
            "metadata",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class GoogleAdsAccountAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAdsAccountAssignment
        fields = [
            "id",
            "user",
            "customer_id",
            "access_level",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
