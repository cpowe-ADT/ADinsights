from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import httpx
import pytest

from accounts.models import AuditLog, Tenant
from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from integrations.models import AirbyteConnection, PlatformCredential, TenantAirbyteSyncStatus


class _BaseStubClient:
    """Common Airbyte client stub with context manager support."""

    def __enter__(self):  # noqa: D401 - behaviour matches context manager protocol
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401 - silence close semantics
        self.close()

    def close(self) -> None:  # pragma: no cover - nothing to clean up in stubs
        return None


@pytest.mark.django_db
def test_airbyte_connections_health_success(api_client, user, tenant, monkeypatch):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Marketing Sync",
        connection_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        last_synced_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        last_job_id="abc123",
        last_job_status="succeeded",
    )

    created_at = 1_700_000_000

    class StubClient(_BaseStubClient):
        def latest_job(self, connection_id: str):
            assert connection_id == str(connection.connection_id)
            return {
                "job": {
                    "id": 321,
                    "status": "running",
                    "createdAt": created_at,
                }
            }

        def trigger_sync(self, connection_id: str):  # pragma: no cover - unused
            raise AssertionError("trigger_sync should not be called in health test")

    monkeypatch.setattr(
        AirbyteClient,
        "from_settings",
        classmethod(lambda cls: StubClient()),
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/connections/health/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["connections"]) == 1
    info = payload["connections"][0]
    assert info["id"] == str(connection.id)
    assert info["name"] == connection.name
    assert info["connection_id"] == str(connection.connection_id)
    assert info["workspace_id"] == str(connection.workspace_id)
    assert info["provider"] == connection.provider
    assert info["last_synced_at"] == connection.last_synced_at.isoformat()
    assert info["last_job_id"] == connection.last_job_id
    assert info["last_job_status"] == connection.last_job_status
    assert info["latest_job"] == {
        "id": "321",
        "status": "running",
        "created_at": datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat(),
    }


@pytest.mark.django_db
def test_airbyte_connections_health_configuration_error(
    api_client, user, tenant, monkeypatch
):
    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Marketing Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
    )

    def raise_config_error(cls):
        raise AirbyteClientConfigurationError("AIRBYTE_API_URL must be configured")

    monkeypatch.setattr(AirbyteClient, "from_settings", classmethod(raise_config_error))

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/connections/health/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 503
    assert "AIRBYTE_API_URL" in response.json()["detail"]


@pytest.mark.django_db
def test_airbyte_connections_health_timeout(api_client, user, tenant, monkeypatch):
    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Analytics Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.GOOGLE,
    )

    class TimeoutClient(_BaseStubClient):
        def latest_job(self, connection_id: str):
            raise AirbyteClientError("Timed out") from httpx.TimeoutException("boom")

        def trigger_sync(self, connection_id: str):  # pragma: no cover - unused
            raise AssertionError("trigger_sync should not be called in timeout test")

    monkeypatch.setattr(
        AirbyteClient,
        "from_settings",
        classmethod(lambda cls: TimeoutClient()),
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/connections/health/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 504
    assert "Timed out" in response.json()["detail"]


@pytest.mark.django_db
def test_airbyte_connection_sync_success(api_client, user, tenant, monkeypatch):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
    )

    class SyncClient(_BaseStubClient):
        def latest_job(self, connection_id: str):  # pragma: no cover - unused
            raise AssertionError("latest_job should not be called during sync")

        def trigger_sync(self, connection_id: str):
            assert connection_id == str(connection.connection_id)
            return {"job": {"id": 777, "status": "pending"}}

    monkeypatch.setattr(
        AirbyteClient,
        "from_settings",
        classmethod(lambda cls: SyncClient()),
    )

    api_client.force_authenticate(user=user)
    response = api_client.post(f"/api/airbyte/connections/{connection.id}/sync/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 202
    assert response.json()["job_id"] == "777"

    log = AuditLog.all_objects.get(
        action="airbyte_connection_sync_triggered", resource_id=str(connection.id)
    )
    assert log.metadata == {
        "connection_id": str(connection.connection_id),
        "job_id": "777",
    }
    assert log.user_id == user.id


@pytest.mark.django_db
def test_airbyte_connection_sync_upstream_error(api_client, user, tenant, monkeypatch):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
    )

    class ErrorClient(_BaseStubClient):
        def latest_job(self, connection_id: str):  # pragma: no cover - unused
            raise AssertionError("latest_job should not be called during sync error path")

        def trigger_sync(self, connection_id: str):
            raise AirbyteClientError("Boom")

    monkeypatch.setattr(
        AirbyteClient,
        "from_settings",
        classmethod(lambda cls: ErrorClient()),
    )

    api_client.force_authenticate(user=user)
    response = api_client.post(f"/api/airbyte/connections/{connection.id}/sync/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 502
    assert response.json()["detail"] == "Boom"
    assert not AuditLog.all_objects.filter(
        action="airbyte_connection_sync_triggered",
        resource_id=str(connection.id),
    ).exists()


@pytest.mark.django_db
def test_airbyte_connection_create_and_list(api_client, user):
    api_client.force_authenticate(user=user)

    payload = {
        "name": "Marketing Sync",
        "connection_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "provider": PlatformCredential.META,
        "schedule_type": AirbyteConnection.SCHEDULE_INTERVAL,
        "interval_minutes": 60,
        "is_active": True,
    }

    response = api_client.post("/api/airbyte/connections/", payload, format="json")
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == payload["name"]
    assert created["connection_id"] == payload["connection_id"]
    assert created["schedule_type"] == AirbyteConnection.SCHEDULE_INTERVAL
    assert created["interval_minutes"] == 60

    list_response = api_client.get("/api/airbyte/connections/")
    assert list_response.status_code == 200
    results = list_response.json()
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["id"] == created["id"]

    log = AuditLog.all_objects.get(
        action="airbyte_connection_created",
        resource_id=created["id"],
    )
    assert log.metadata["connection_id"] == payload["connection_id"]


@pytest.mark.django_db
def test_airbyte_connection_update_schedule(api_client, user, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Sync",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
    )

    api_client.force_authenticate(user=user)
    response = api_client.patch(
        f"/api/airbyte/connections/{connection.id}/",
        {
            "schedule_type": AirbyteConnection.SCHEDULE_CRON,
            "cron_expression": "0 6-22 * * *",
        },
        format="json",
    )
    assert response.status_code == 200

    connection.refresh_from_db()
    assert connection.schedule_type == AirbyteConnection.SCHEDULE_CRON
    assert connection.interval_minutes is None
    assert connection.cron_expression == "0 6-22 * * *"


@pytest.mark.django_db
def test_airbyte_connection_cron_requires_expression(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/api/airbyte/connections/",
        {
            "name": "Cron",
            "connection_id": str(uuid.uuid4()),
            "schedule_type": AirbyteConnection.SCHEDULE_CRON,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "cron_expression" in response.json()


@pytest.mark.django_db
def test_airbyte_connection_list_scoped_to_tenant(api_client, user, tenant):
    other_tenant = AirbyteConnection.objects.create(
        tenant=Tenant.objects.create(name="Other Tenant"),
        name="Other Sync",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
    )

    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Primary Sync",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/connections/")
    assert response.status_code == 200
    results = response.json()
    assert {row["name"] for row in results} == {"Primary Sync"}
    assert str(other_tenant.connection_id) not in {row["connection_id"] for row in results}


@pytest.mark.django_db
def test_airbyte_connection_manual_schedule_clears_fields(api_client, user, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Manual",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
    )

    api_client.force_authenticate(user=user)
    response = api_client.patch(
        f"/api/airbyte/connections/{connection.id}/",
        {"schedule_type": AirbyteConnection.SCHEDULE_MANUAL},
        format="json",
    )
    assert response.status_code == 200

    connection.refresh_from_db()
    assert connection.schedule_type == AirbyteConnection.SCHEDULE_MANUAL
    assert connection.interval_minutes is None
    assert connection.cron_expression == ""


@pytest.mark.django_db
def test_airbyte_connection_interval_rejects_cron_expression(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/api/airbyte/connections/",
        {
            "name": "Interval",
            "connection_id": str(uuid.uuid4()),
            "schedule_type": AirbyteConnection.SCHEDULE_INTERVAL,
            "interval_minutes": 30,
            "cron_expression": "0 6-22 * * *",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "cron_expression" in response.json()


@pytest.mark.django_db
def test_airbyte_connection_cron_rejects_interval_minutes(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/api/airbyte/connections/",
        {
            "name": "Cron",
            "connection_id": str(uuid.uuid4()),
            "schedule_type": AirbyteConnection.SCHEDULE_CRON,
            "cron_expression": "0 6-22 * * *",
            "interval_minutes": 30,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "interval_minutes" in response.json()


@pytest.mark.django_db
def test_airbyte_connection_cron_rejects_invalid_expression(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/api/airbyte/connections/",
        {
            "name": "Cron",
            "connection_id": str(uuid.uuid4()),
            "schedule_type": AirbyteConnection.SCHEDULE_CRON,
            "cron_expression": "not-a-cron",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "cron_expression" in response.json()


@pytest.mark.django_db
def test_airbyte_connection_summary(api_client, user, tenant):
    now = datetime.now(timezone.utc)
    due_connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Due",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=now - timedelta(hours=2),
    )
    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Not Due",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.GOOGLE,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=120,
        last_synced_at=now,
    )
    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Manual",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_MANUAL,
        is_active=False,
    )

    TenantAirbyteSyncStatus.all_objects.create(
        tenant=tenant,
        last_connection=due_connection,
        last_synced_at=now,
        last_job_id="job-123",
        last_job_status="succeeded",
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/connections/summary/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["active"] == 2
    assert payload["inactive"] == 1
    assert payload["due"] == 1
    assert payload["by_provider"]["META"]["total"] == 2
    assert payload["by_provider"]["GOOGLE"]["total"] == 1
    assert payload["latest_sync"]["last_job_id"] == "job-123"

    log = AuditLog.all_objects.get(action="airbyte_connection_summary_viewed")
    assert log.resource_id == "summary"


@pytest.mark.django_db
def test_airbyte_connection_summary_handles_unknown_provider(api_client, user, tenant):
    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Unknown Provider",
        connection_id=uuid.uuid4(),
        provider=None,
        schedule_type=AirbyteConnection.SCHEDULE_MANUAL,
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/airbyte/connections/summary/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["by_provider"]["UNKNOWN"]["total"] == 1
    assert payload["latest_sync"] is None
