from __future__ import annotations

from datetime import datetime, timezone
import uuid

import httpx
import pytest

from accounts.models import AuditLog
from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from integrations.models import AirbyteConnection, PlatformCredential


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
