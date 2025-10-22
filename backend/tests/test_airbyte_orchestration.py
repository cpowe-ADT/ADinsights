from __future__ import annotations

import io
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from integrations.airbyte.service import AirbyteSyncService
from integrations.models import AirbyteConnection, AirbyteJobTelemetry, PlatformCredential, TenantAirbyteSyncStatus
from integrations.tasks import trigger_scheduled_airbyte_syncs


@pytest.mark.django_db
def test_interval_schedule_due(tenant):
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Hourly Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
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
        provider=PlatformCredential.GOOGLE,
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
        provider=PlatformCredential.META,
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
            return {
                "job": {
                    "id": job_id,
                    "status": "succeeded",
                    "createdAt": int(now.timestamp()),
                    "attempts": [
                        {
                            "id": 0,
                            "status": "succeeded",
                            "createdAt": int(now.timestamp()),
                            "updatedAt": int((now + timedelta(seconds=12)).timestamp()),
                            "metrics": {
                                "recordsEmitted": 42,
                                "bytesEmitted": 1024,
                                "timeInMillis": 12000,
                                "apiCallCost": 3.5,
                            },
                        }
                    ],
                }
            }

    service = AirbyteSyncService(DummyClient(), now_fn=lambda: now)
    updates = service.sync_due_connections()
    assert len(updates) == 1
    AirbyteConnection.persist_sync_updates(updates)
    connection.refresh_from_db()
    assert connection.last_job_id == "55"
    assert connection.last_job_status == "succeeded"
    assert connection.last_job_completed_at is not None
    assert abs((connection.last_synced_at or now) - connection.last_job_completed_at) <= timedelta(seconds=1)
    assert connection.last_job_updated_at is not None
    assert connection.last_job_completed_at is not None
    assert connection.last_job_error == ""

    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)
    assert status.last_connection_id == connection.id
    assert status.last_job_id == "55"
    assert status.last_job_status == "succeeded"
    assert status.last_synced_at == connection.last_synced_at
    assert status.last_job_updated_at == connection.last_job_updated_at
    assert status.last_job_completed_at == connection.last_job_completed_at
    assert status.last_job_error == ""

    telemetry = AirbyteJobTelemetry.all_objects.get(connection=connection, job_id="55")
    assert telemetry.records_synced == 42
    assert telemetry.bytes_synced == 1024
    assert telemetry.duration_seconds == 12
    assert float(telemetry.api_cost) == 3.5


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

    updates_payload = [object(), object()]
    captured_updates: dict[str, list[object]] = {}

    def fake_service(client):
        captured_client["client"] = client
        return type("Svc", (), {"sync_due_connections": lambda self=None: updates_payload})()

    def fake_persist(cls, updates):  # noqa: ANN001
        captured_updates["updates"] = list(updates)
        return []

    monkeypatch.setattr(command_module.AirbyteClient, "from_settings", classmethod(fake_from_settings))
    monkeypatch.setattr(command_module, "AirbyteSyncService", fake_service)
    monkeypatch.setattr(
        command_module.AirbyteConnection,
        "persist_sync_updates",
        classmethod(fake_persist),
    )

    output = io.StringIO()
    call_command("sync_airbyte", stdout=output)
    assert "Triggered 2 Airbyte sync(s)." in output.getvalue()
    assert captured_client["client"] is dummy_client
    assert captured_updates["updates"] == updates_payload


@pytest.mark.django_db
def test_airbyte_celery_task(monkeypatch, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
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
            return {
                "job": {
                    "id": job_id,
                    "status": "succeeded",
                    "createdAt": int(now.timestamp()),
                    "attempts": [
                        {
                            "id": 0,
                            "status": "succeeded",
                            "createdAt": int(now.timestamp()),
                            "updatedAt": int((now + timedelta(seconds=8)).timestamp()),
                            "metrics": {
                                "recordsEmitted": 10,
                                "bytesEmitted": 512,
                                "timeInMillis": 8000,
                            },
                        }
                    ],
                }
            }

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

    telemetry = AirbyteJobTelemetry.all_objects.get(connection=connection, job_id="1")
    assert telemetry.duration_seconds == 8
    assert telemetry.records_synced == 10
