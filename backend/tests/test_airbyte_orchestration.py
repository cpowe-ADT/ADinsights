from __future__ import annotations

import io
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from integrations.airbyte.service import AirbyteSyncService
from integrations.models import AirbyteConnection, TenantAirbyteSyncStatus
from integrations.tasks import trigger_scheduled_airbyte_syncs


@pytest.mark.django_db
def test_interval_schedule_due(tenant):
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Hourly Meta",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        last_synced_at=now - timedelta(hours=2),
    )
    assert connection.should_trigger(now)
    connection.last_synced_at = now - timedelta(minutes=30)
    assert not connection.should_trigger(now)


@pytest.mark.django_db
def test_cron_schedule_due(tenant):
    now = timezone.now().replace(minute=5, second=0, microsecond=0)
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Hourly Google",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 * * * *",
        last_synced_at=now - timedelta(hours=2),
    )
    assert connection.should_trigger(now)
    connection.last_synced_at = now
    assert not connection.should_trigger(now)


@pytest.mark.django_db
def test_airbyte_service_triggers_and_records(tenant):
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=now - timedelta(hours=1),
    )

    class DummyClient:
        def trigger_sync(self, connection_id: str):
            assert str(connection.connection_id) == connection_id
            return {"job": {"id": 55}}

        def get_job(self, job_id: int):
            assert job_id == 55
            return {"job": {"id": job_id, "status": "succeeded", "createdAt": int(now.timestamp())}}

    service = AirbyteSyncService(DummyClient(), now_fn=lambda: now)
    triggered = service.sync_due_connections()
    assert triggered == 1

    connection.refresh_from_db()
    assert connection.last_job_id == "55"
    assert connection.last_job_status == "succeeded"
    assert abs((connection.last_synced_at or now) - now) <= timedelta(seconds=1)

    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)
    assert status.last_connection_id == connection.id
    assert status.last_job_id == "55"
    assert status.last_job_status == "succeeded"
    assert status.last_synced_at == connection.last_synced_at


@pytest.mark.django_db
def test_sync_airbyte_command(monkeypatch, settings):
    from integrations.management.commands import sync_airbyte as command_module

    settings.AIRBYTE_API_URL = "http://airbyte"
    settings.AIRBYTE_API_TOKEN = "token"

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

    dummy_client = DummyClient()
    captured_client = {}

    def fake_from_settings(cls):  # noqa: ANN001
        return dummy_client

    def fake_service(client):
        captured_client["client"] = client
        return type("Svc", (), {"sync_due_connections": lambda self=None: 2})()

    monkeypatch.setattr(command_module.AirbyteClient, "from_settings", classmethod(fake_from_settings))
    monkeypatch.setattr(command_module, "AirbyteSyncService", fake_service)

    output = io.StringIO()
    call_command("sync_airbyte", stdout=output)
    assert "Triggered 2 Airbyte sync(s)." in output.getvalue()
    assert captured_client["client"] is dummy_client


@pytest.mark.django_db
def test_airbyte_celery_task(monkeypatch, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
    )

    now = timezone.now()

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

        def trigger_sync(self, connection_id: str):
            assert str(connection.connection_id) == connection_id
            return {"job": {"id": 1}}

        def get_job(self, job_id: int):
            return {"job": {"id": job_id, "status": "succeeded", "createdAt": int(now.timestamp())}}

    dummy_client = DummyClient()

    from integrations import tasks as tasks_module

    monkeypatch.setattr(
        tasks_module.AirbyteClient, "from_settings", classmethod(lambda cls: dummy_client), raising=False
    )

    class DummyService:
        def __init__(self, client):  # noqa: ANN001
            assert client is dummy_client

        def sync_due_connections(self):  # noqa: D401 - interface compatibility
            return AirbyteSyncService(dummy_client, now_fn=lambda: now).sync_due_connections()

    monkeypatch.setattr(tasks_module, "AirbyteSyncService", DummyService)

    result = trigger_scheduled_airbyte_syncs.run()
    assert result == 1

    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)
    assert status.last_job_status == "succeeded"
