from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

from accounts.models import Tenant
from integrations.models import (
    AirbyteConnection,
    AirbyteJobTelemetry,
    PlatformCredential,
    TenantAirbyteSyncStatus,
)


@pytest.mark.django_db
def test_airbyte_webhook_scopes_updates_to_connection_tenant(api_client, settings):
    settings.AIRBYTE_WEBHOOK_SECRET_REQUIRED = True
    settings.AIRBYTE_WEBHOOK_SECRET = "test-secret"

    tenant_a = Tenant.objects.create(name="Tenant A")
    tenant_b = Tenant.objects.create(name="Tenant B")

    connection_a = AirbyteConnection.objects.create(
        tenant=tenant_a,
        name="Conn A",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
    )
    AirbyteConnection.objects.create(
        tenant=tenant_b,
        name="Conn B",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.GOOGLE,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
    )

    payload = {
        "connectionId": str(connection_a.connection_id),
        "job": {
            "id": 101,
            "status": "succeeded",
            "createdAt": int(datetime.now(tz=timezone.utc).timestamp()),
        },
    }

    response = api_client.post(
        "/api/airbyte/webhook/",
        payload,
        format="json",
        HTTP_X_AIRBYTE_WEBHOOK_SECRET="test-secret",
        HTTP_X_TENANT_ID=str(tenant_b.id),
    )

    assert response.status_code == 200

    telemetry = AirbyteJobTelemetry.objects.get(connection=connection_a, job_id="101")
    assert telemetry.tenant_id == tenant_a.id
    assert not AirbyteJobTelemetry.objects.filter(tenant=tenant_b).exists()

    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant_a)
    assert status.last_connection_id == connection_a.id
    assert status.last_job_id == "101"
    assert not TenantAirbyteSyncStatus.all_objects.filter(tenant=tenant_b).exists()
