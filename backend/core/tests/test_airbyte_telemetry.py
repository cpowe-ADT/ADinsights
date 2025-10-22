from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.utils import timezone

from accounts.models import AuditLog, Tenant
from integrations.models import (
    AirbyteConnection,
    AirbyteJobTelemetry,
    TenantAirbyteSyncStatus,
)


@pytest.mark.django_db
def test_airbyte_telemetry_requires_auth(api_client):
    response = api_client.get("/api/airbyte/telemetry/")
    assert response.status_code == 401
    assert response.json()["detail"].lower().startswith("authentication credentials")
    assert not AuditLog.all_objects.filter(action="airbyte_telemetry_viewed").exists()


@pytest.mark.django_db
def test_airbyte_telemetry_filters_by_tenant(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")

    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Primary Sync",
        provider=None,
        connection_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
    )
    other_connection = AirbyteConnection.objects.create(
        tenant=other_tenant,
        name="Other Sync",
        provider=None,
        connection_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
    )

    now = timezone.now()
    TenantAirbyteSyncStatus.all_objects.create(
        tenant=tenant,
        last_connection=connection,
        last_synced_at=now,
        last_job_id="job-123",
        last_job_status="succeeded",
    )
    TenantAirbyteSyncStatus.all_objects.create(
        tenant=other_tenant,
        last_connection=other_connection,
        last_synced_at=now - timedelta(hours=1),
        last_job_id="job-999",
        last_job_status="failed",
    )

    AirbyteJobTelemetry.all_objects.create(
        tenant=tenant,
        connection=connection,
        job_id="job-123",
        status="succeeded",
        started_at=now - timedelta(minutes=5),
        duration_seconds=60,
        records_synced=100,
        bytes_synced=1024,
        api_cost=Decimal("1.23"),
    )
    AirbyteJobTelemetry.all_objects.create(
        tenant=other_tenant,
        connection=other_connection,
        job_id="job-999",
        status="failed",
        started_at=now - timedelta(minutes=10),
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/telemetry/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    payload = response.json()

    assert payload["count"] == 1
    assert payload["previous"] is None
    assert payload["next"] is None
    assert len(payload["results"]) == 1

    telemetry = payload["results"][0]
    assert telemetry["job_id"] == "job-123"
    assert telemetry["connection"]["id"] == str(connection.id)
    assert telemetry["connection"]["name"] == connection.name

    sync_status = payload["sync_status"]
    assert sync_status["last_job_id"] == "job-123"
    assert sync_status["last_job_status"] == "succeeded"
    assert sync_status["connection"]["id"] == str(connection.id)

    audit_entry = AuditLog.all_objects.get(action="airbyte_telemetry_viewed")
    assert audit_entry.tenant_id == tenant.id
    assert audit_entry.resource_type == "airbyte_telemetry"
    assert audit_entry.resource_id == "list"


@pytest.mark.django_db
def test_airbyte_telemetry_paginates_results(api_client, user, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Primary Sync",
        provider=None,
        connection_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
    )

    TenantAirbyteSyncStatus.all_objects.create(
        tenant=tenant,
        last_connection=connection,
        last_synced_at=timezone.now(),
        last_job_id="job-0",
        last_job_status="succeeded",
    )

    for index in range(6):
        AirbyteJobTelemetry.all_objects.create(
            tenant=tenant,
            connection=connection,
            job_id=f"job-{index}",
            status="succeeded",
            started_at=timezone.now() - timedelta(minutes=index),
            duration_seconds=30 + index,
        )

    api_client.force_authenticate(user=user)
    first_page = api_client.get("/api/airbyte/telemetry/")
    assert first_page.status_code == 200
    first_payload = first_page.json()

    assert first_payload["count"] == 6
    assert len(first_payload["results"]) == 5
    assert first_payload["next"] is not None
    assert first_payload["previous"] is None

    second_page = api_client.get(first_payload["next"])
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(second_payload["results"]) == 1
    assert second_payload["previous"] is not None
    assert second_payload["count"] == 6

    audit_events = AuditLog.all_objects.filter(action="airbyte_telemetry_viewed", tenant=tenant)
    assert audit_events.count() == 2
