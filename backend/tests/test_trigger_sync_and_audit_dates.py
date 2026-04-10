"""Tests for upgraded trigger-sync endpoint and audit log date filtering."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog
from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from integrations.models import AirbyteConnection, PlatformCredential


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _BaseStubClient:
    """Common Airbyte client stub with context manager support."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self) -> None:
        return None


def list_results(response):
    body = response.json()
    if isinstance(body, list):
        return body
    return body.get("results", [])


# ===========================================================================
# PART 1: trigger-sync endpoint
# ===========================================================================


@pytest.mark.django_db
def test_trigger_sync_success(api_client, user, tenant, monkeypatch):
    """Configured Airbyte returns 200 with triggered status and job_id."""
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Trigger Test",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
    )

    class StubClient(_BaseStubClient):
        def trigger_sync(self, connection_id: str):
            assert connection_id == str(connection.connection_id)
            return {"job": {"id": 999, "status": "pending"}}

    monkeypatch.setattr(
        AirbyteClient,
        "from_settings",
        classmethod(lambda cls: StubClient()),
    )

    api_client.force_authenticate(user=user)
    response = api_client.post(
        f"/api/airbyte/connections/{connection.id}/trigger-sync/"
    )
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "triggered"
    assert payload["connection_id"] == str(connection.connection_id)
    assert payload["job_id"] == "999"

    # Audit log should be created
    log = AuditLog.all_objects.get(
        action="airbyte_connection_sync_triggered",
        resource_id=str(connection.id),
    )
    assert log.metadata["trigger_source"] == "trigger-sync"
    assert log.user_id == user.id


@pytest.mark.django_db
def test_trigger_sync_not_configured(api_client, user, tenant, monkeypatch):
    """When Airbyte is not configured, return 501."""
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="No Airbyte",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
    )

    monkeypatch.setattr(
        AirbyteClient,
        "from_settings",
        classmethod(
            lambda cls: (_ for _ in ()).throw(
                AirbyteClientConfigurationError("AIRBYTE_API_URL must be configured")
            )
        ),
    )

    api_client.force_authenticate(user=user)
    response = api_client.post(
        f"/api/airbyte/connections/{connection.id}/trigger-sync/"
    )
    api_client.force_authenticate(user=None)

    assert response.status_code == 501
    assert "not configured" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_trigger_sync_airbyte_error(api_client, user, tenant, monkeypatch):
    """When Airbyte returns an error, return 502."""
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Error Case",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
    )

    class ErrorClient(_BaseStubClient):
        def trigger_sync(self, connection_id: str):
            raise AirbyteClientError("Connection refused")

    monkeypatch.setattr(
        AirbyteClient,
        "from_settings",
        classmethod(lambda cls: ErrorClient()),
    )

    api_client.force_authenticate(user=user)
    response = api_client.post(
        f"/api/airbyte/connections/{connection.id}/trigger-sync/"
    )
    api_client.force_authenticate(user=None)

    assert response.status_code == 502
    assert "Connection refused" in response.json()["detail"]


@pytest.mark.django_db
def test_trigger_sync_connection_not_found(api_client, user, tenant):
    """Request for nonexistent connection returns 404."""
    api_client.force_authenticate(user=user)
    fake_id = uuid.uuid4()
    response = api_client.post(
        f"/api/airbyte/connections/{fake_id}/trigger-sync/"
    )
    api_client.force_authenticate(user=None)

    assert response.status_code == 404


# ===========================================================================
# PART 2: Audit log date range filtering
# ===========================================================================


@pytest.mark.django_db
def test_audit_log_date_filter_returns_matching(api_client, user, tenant):
    """Filtering by start_date and end_date returns only matching logs."""
    now = timezone.now()

    old_log = AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action="old_event",
        resource_type="test",
        resource_id="1",
    )
    # Override created_at to 10 days ago
    AuditLog.all_objects.filter(pk=old_log.pk).update(
        created_at=now - timedelta(days=10)
    )

    recent_log = AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action="recent_event",
        resource_type="test",
        resource_id="2",
    )
    AuditLog.all_objects.filter(pk=recent_log.pk).update(created_at=now)

    api_client.force_authenticate(user=user)

    # Filter for last 3 days only — should exclude old_log
    start = (now - timedelta(days=3)).date().isoformat()
    end = now.date().isoformat()
    response = api_client.get(
        reverse("auditlog-list"), {"start_date": start, "end_date": end}
    )
    assert response.status_code == 200
    results = list_results(response)
    actions = [r["action"] for r in results]
    assert "recent_event" in actions
    assert "old_event" not in actions

    api_client.force_authenticate(user=None)


@pytest.mark.django_db
def test_audit_log_no_date_params_returns_all(api_client, user, tenant):
    """Without date params, all logs for the tenant are returned."""
    now = timezone.now()

    log1 = AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action="event_a",
        resource_type="test",
        resource_id="1",
    )
    AuditLog.all_objects.filter(pk=log1.pk).update(
        created_at=now - timedelta(days=30)
    )

    AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action="event_b",
        resource_type="test",
        resource_id="2",
    )

    api_client.force_authenticate(user=user)
    response = api_client.get(reverse("auditlog-list"))
    assert response.status_code == 200
    results = list_results(response)
    actions = {r["action"] for r in results}
    assert "event_a" in actions
    assert "event_b" in actions
    api_client.force_authenticate(user=None)


@pytest.mark.django_db
def test_audit_log_invalid_date_returns_empty(api_client, user, tenant):
    """Invalid date params return empty results (not a 500)."""
    AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action="some_event",
        resource_type="test",
        resource_id="1",
    )

    api_client.force_authenticate(user=user)
    response = api_client.get(
        reverse("auditlog-list"), {"start_date": "not-a-date"}
    )
    assert response.status_code == 200
    results = list_results(response)
    assert len(results) == 0
    api_client.force_authenticate(user=None)


@pytest.mark.django_db
def test_audit_log_iso_datetime_param(api_client, user, tenant):
    """Full ISO datetime strings work as date params."""
    now = timezone.now()

    AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action="iso_event",
        resource_type="test",
        resource_id="1",
    )

    api_client.force_authenticate(user=user)
    start = (now - timedelta(days=1)).isoformat()
    end = (now + timedelta(days=1)).isoformat()
    response = api_client.get(
        reverse("auditlog-list"), {"start_date": start, "end_date": end}
    )
    assert response.status_code == 200
    results = list_results(response)
    actions = [r["action"] for r in results]
    assert "iso_event" in actions
    api_client.force_authenticate(user=None)
