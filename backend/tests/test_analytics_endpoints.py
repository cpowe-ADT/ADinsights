from __future__ import annotations

import uuid

import pytest
from django.utils import timezone

from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from adapters.warehouse import WarehouseAdapter
from analytics.models import Campaign, TenantMetricsSnapshot
from integrations.models import AirbyteConnection, AirbyteJobTelemetry, TenantAirbyteSyncStatus, PlatformCredential


@pytest.mark.django_db
def test_campaign_list_scoped_to_tenant(api_client, tenant, user):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    Campaign.objects.create(
        tenant=tenant,
        external_id="camp-tenant-a",
        name="Tenant A Campaign",
        platform="META",
    )
    Campaign.objects.create(
        tenant=other_tenant,
        external_id="camp-tenant-b",
        name="Tenant B Campaign",
        platform="META",
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/analytics/campaigns/")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    external_ids = {record["external_id"] for record in payload}
    assert external_ids == {"camp-tenant-a"}


@pytest.mark.django_db
def test_airbyte_telemetry_list_scoped_to_tenant(api_client, tenant, user):
    other_tenant = Tenant.objects.create(name="Airbyte Tenant B")

    connection_a = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Conn A",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        is_active=True,
    )
    TenantAirbyteSyncStatus.all_objects.update_or_create(
        tenant=tenant,
        defaults={"last_connection": connection_a, "last_synced_at": timezone.now()},
    )
    AirbyteJobTelemetry.all_objects.create(
        tenant=tenant,
        connection=connection_a,
        job_id="job-tenant-a",
        status="succeeded",
        started_at=timezone.now(),
    )

    connection_b = AirbyteConnection.objects.create(
        tenant=other_tenant,
        name="Conn B",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        is_active=True,
    )
    TenantAirbyteSyncStatus.all_objects.update_or_create(
        tenant=other_tenant,
        defaults={"last_connection": connection_b, "last_synced_at": timezone.now()},
    )
    AirbyteJobTelemetry.all_objects.create(
        tenant=other_tenant,
        connection=connection_b,
        job_id="job-tenant-b",
        status="succeeded",
        started_at=timezone.now(),
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/telemetry/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["connection"]["id"] == str(connection_a.id)
    assert payload["sync_status"]["tenant_id"] == str(tenant.id)


@pytest.mark.django_db
def test_warehouse_adapter_returns_tenant_snapshot(tenant):
    other_tenant = Tenant.objects.create(name="Warehouse Tenant B")

    snapshot_a_payload = {
        "campaign": {"summary": {"currency": "JMD"}, "trend": [], "rows": []},
        "creative": [],
        "budget": [],
        "parish": [],
    }
    snapshot_b_payload = {
        "campaign": {"summary": {"currency": "EUR"}, "trend": [], "rows": []},
        "creative": [],
        "budget": [],
        "parish": [],
    }

    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        payload={**snapshot_a_payload, "snapshot_generated_at": timezone.now().isoformat()},
        generated_at=timezone.now(),
    )
    TenantMetricsSnapshot.objects.create(
        tenant=other_tenant,
        source="warehouse",
        payload={**snapshot_b_payload, "snapshot_generated_at": timezone.now().isoformat()},
        generated_at=timezone.now(),
    )

    adapter = WarehouseAdapter()
    with tenant_context(str(tenant.id)):
        payload = adapter.fetch_metrics(tenant_id=str(tenant.id))

    assert payload["campaign"]["summary"]["currency"] == "JMD"
    assert payload != snapshot_b_payload
