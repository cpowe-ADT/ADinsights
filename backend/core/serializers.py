from __future__ import annotations

from rest_framework import serializers

from integrations.models import (
    AirbyteConnection,
    AirbyteJobTelemetry,
    TenantAirbyteSyncStatus,
)


class AirbyteConnectionSummarySerializer(serializers.ModelSerializer):
    """Expose non-sensitive connection metadata alongside telemetry."""

    class Meta:
        model = AirbyteConnection
        fields = (
            "id",
            "name",
            "connection_id",
            "workspace_id",
            "provider",
        )
        read_only_fields = fields


class TenantAirbyteSyncStatusSerializer(serializers.ModelSerializer):
    """Serialise the latest tenant-level Airbyte sync status."""

    tenant_id = serializers.UUIDField(read_only=True)
    connection = AirbyteConnectionSummarySerializer(
        source="last_connection", read_only=True
    )

    class Meta:
        model = TenantAirbyteSyncStatus
        fields = (
            "tenant_id",
            "last_synced_at",
            "last_job_id",
            "last_job_status",
            "last_job_updated_at",
            "last_job_completed_at",
            "last_job_error",
            "connection",
        )
        read_only_fields = fields


class AirbyteJobTelemetrySerializer(serializers.ModelSerializer):
    """Expose individual Airbyte job telemetry records."""

    connection = AirbyteConnectionSummarySerializer(read_only=True)
    api_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
        coerce_to_string=False,
    )

    class Meta:
        model = AirbyteJobTelemetry
        fields = (
            "job_id",
            "status",
            "started_at",
            "duration_seconds",
            "records_synced",
            "bytes_synced",
            "api_cost",
            "connection",
        )
        read_only_fields = fields
