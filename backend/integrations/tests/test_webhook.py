from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from accounts.models import AuditLog
from integrations.models import (
    AirbyteConnection,
    AirbyteJobTelemetry,
    ConnectionSyncUpdate,
    PlatformCredential,
    TenantAirbyteSyncStatus,
)


@pytest.mark.django_db
def test_airbyte_webhook_updates_status_and_telemetry(api_client, tenant, settings):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Daily Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=1440,
    )

    now = timezone.now()
    settings.AIRBYTE_WEBHOOK_SECRET = "shared-secret"
    payload = {
        "connectionId": str(connection.connection_id),
        "job": {
            "id": 99,
            "status": "succeeded",
            "createdAt": int(now.timestamp()),
            "updatedAt": int((now + timedelta(seconds=20)).timestamp()),
            "attempts": [
                {
                    "createdAt": int(now.timestamp()),
                    "updatedAt": int((now + timedelta(seconds=20)).timestamp()),
                    "metrics": {
                        "recordsEmitted": 120,
                        "bytesEmitted": 4096,
                        "timeInMillis": 20000,
                    },
                }
            ],
        },
    }

    response = api_client.post(
        reverse("airbyte-webhook"),
        payload,
        format="json",
        HTTP_X_AIRBYTE_WEBHOOK_SECRET="shared-secret",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "99"
    assert data["status"] == "succeeded"

    connection.refresh_from_db()
    assert connection.last_job_id == "99"
    assert connection.last_job_status == "succeeded"
    assert connection.last_job_error == ""
    assert connection.last_job_completed_at is not None
    assert connection.last_job_updated_at is not None

    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)
    assert status.last_job_id == "99"
    assert status.last_job_status == "succeeded"
    assert status.last_job_error == ""

    telemetry = AirbyteJobTelemetry.all_objects.get(connection=connection, job_id="99")
    assert telemetry.records_synced == 120
    assert telemetry.bytes_synced == 4096
    assert telemetry.duration_seconds == 20

    audit = AuditLog.all_objects.get(action="airbyte_job_webhook", resource_id=str(connection.id))
    assert audit.metadata["status"] == "succeeded"
    assert audit.metadata["job_id"] == "99"


@pytest.mark.django_db
def test_airbyte_webhook_secret_required(api_client, tenant, settings):
    settings.AIRBYTE_WEBHOOK_SECRET = "expected"
    settings.AIRBYTE_WEBHOOK_SECRET_REQUIRED = True
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_MANUAL,
    )

    payload = {"connectionId": str(connection.connection_id), "job": {"id": 1, "status": "succeeded"}}

    response = api_client.post(reverse("airbyte-webhook"), payload, format="json")
    assert response.status_code == 403
    assert response.json()["detail"] == "invalid webhook secret"


@pytest.mark.django_db
def test_airbyte_webhook_rejects_when_secret_missing(api_client, tenant, settings):
    settings.AIRBYTE_WEBHOOK_SECRET = None
    settings.AIRBYTE_WEBHOOK_SECRET_REQUIRED = True
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_MANUAL,
    )

    payload = {"connectionId": str(connection.connection_id), "job": {"id": 1, "status": "succeeded"}}

    response = api_client.post(reverse("airbyte-webhook"), payload, format="json")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "webhook secret not configured"


@pytest.mark.django_db
def test_persist_sync_updates_records_failure(tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Failure Case",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_MANUAL,
    )

    now = timezone.now()
    update = ConnectionSyncUpdate(
        connection=connection,
        job_id="77",
        status="failed",
        created_at=now,
        updated_at=now,
        completed_at=None,
        duration_seconds=5,
        records_synced=0,
        bytes_synced=0,
        api_cost=None,
        error="upstream error",
    )

    AirbyteConnection.persist_sync_updates([update])

    connection.refresh_from_db()
    assert connection.last_job_status == "failed"
    assert connection.last_job_error == "upstream error"
    assert connection.last_synced_at is None

    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)
    assert status.last_job_status == "failed"
    assert status.last_job_error == "upstream error"
