from __future__ import annotations

import io
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from integrations.airbyte import AirbyteClientConfigurationError, AirbyteClientError
from integrations.airbyte.service import (
    AirbyteSyncService,
    extract_attempt_snapshot,
    extract_job_error,
)
from integrations.models import AirbyteConnection, AirbyteJobTelemetry, PlatformCredential, TenantAirbyteSyncStatus
from integrations.tasks import (
    RETRY_REASON_AIRBYTE_CLIENT_CONFIGURATION,
    RETRY_REASON_AIRBYTE_CLIENT_ERROR,
    refresh_airbyte_sync_health,
    trigger_scheduled_airbyte_syncs,
)


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


def test_extract_attempt_snapshot_supports_top_level_attempts():
    now = timezone.now()
    payload = {
        "job": {
            "id": 145,
            "status": "failed",
            "createdAt": int(now.timestamp()),
            "updatedAt": int((now + timedelta(seconds=30)).timestamp()),
        },
        "attempts": [
            {
                "id": 0,
                "status": "failed",
                "createdAt": int(now.timestamp()),
                "updatedAt": int((now + timedelta(seconds=9)).timestamp()),
                "metrics": {
                    "recordsEmitted": 5,
                    "bytesEmitted": 512,
                    "timeInMillis": 9000,
                },
            }
        ],
    }

    snapshot = extract_attempt_snapshot(payload)
    assert snapshot is not None
    assert snapshot.duration_seconds == 9
    assert snapshot.records_synced == 5
    assert snapshot.bytes_synced == 512


def test_extract_job_error_supports_top_level_attempt_failure_summary():
    payload = {
        "job": {
            "id": 145,
            "status": "failed",
        },
        "attempts": [
            {
                "id": 0,
                "status": "failed",
                "failureSummary": {
                    "failures": [
                        {
                            "failureOrigin": "source",
                            "failureType": "config_error",
                            "externalMessage": "Meta access token expired.",
                        }
                    ]
                },
            }
        ],
    }

    assert extract_job_error(payload) == "Meta access token expired."


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
def test_backfill_airbyte_sync_status_updates_existing_connection(monkeypatch, settings, tenant):
    from integrations.management.commands import backfill_airbyte_sync_status as command_module

    settings.AIRBYTE_API_URL = "http://airbyte"
    settings.AIRBYTE_API_TOKEN = "token"

    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta stale",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        last_synced_at=now - timedelta(hours=4),
        last_job_status="running",
        last_job_id="100",
        last_job_created_at=now - timedelta(hours=4),
        last_job_updated_at=now - timedelta(hours=4),
    )

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

        def latest_job(self, connection_id: str):
            assert connection_id == str(connection.connection_id)
            return {
                "job": {
                    "id": 145,
                    "status": "succeeded",
                    "createdAt": int((now - timedelta(minutes=2)).timestamp()),
                    "updatedAt": int((now - timedelta(minutes=1)).timestamp()),
                }
            }

    monkeypatch.setattr(
        command_module.AirbyteClient, "from_settings", classmethod(lambda cls: DummyClient())
    )

    output = io.StringIO()
    call_command("backfill_airbyte_sync_status", "--apply", stdout=output)

    connection.refresh_from_db()
    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)

    assert connection.last_job_status == "succeeded"
    assert connection.last_job_id == "145"
    assert connection.last_synced_at is not None
    assert status.last_connection_id == connection.id
    assert status.last_job_status == "succeeded"
    assert "updated=1" in output.getvalue()


@pytest.mark.django_db
def test_backfill_airbyte_sync_status_creates_missing_workspace_connections(
    monkeypatch, settings, tenant
):
    from integrations.management.commands import backfill_airbyte_sync_status as command_module

    settings.AIRBYTE_API_URL = "http://airbyte"
    settings.AIRBYTE_API_TOKEN = "token"

    now = timezone.now()
    connection_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

        def list_connections(self, workspace_id_value: str):
            assert workspace_id_value == str(workspace_id)
            return [
                {
                    "connectionId": str(connection_id),
                    "name": "Meta Insights Connection",
                    "status": "active",
                    "scheduleType": "basic",
                    "scheduleData": {
                        "basicSchedule": {
                            "units": 1,
                            "timeUnit": "hours",
                        }
                    },
                }
            ]

        def latest_job(self, connection_id_value: str):
            assert connection_id_value == str(connection_id)
            return {
                "job": {
                    "id": 77,
                    "status": "failed",
                    "createdAt": int((now - timedelta(minutes=5)).timestamp()),
                    "updatedAt": int((now - timedelta(minutes=1)).timestamp()),
                    "errorMessage": "upstream timeout",
                }
            }

    monkeypatch.setattr(
        command_module.AirbyteClient, "from_settings", classmethod(lambda cls: DummyClient())
    )

    output = io.StringIO()
    call_command(
        "backfill_airbyte_sync_status",
        "--tenant-id",
        str(tenant.id),
        "--workspace-id",
        str(workspace_id),
        "--create-missing",
        "--apply",
        stdout=output,
    )

    connection = AirbyteConnection.all_objects.get(connection_id=connection_id)
    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)

    assert connection.workspace_id == workspace_id
    assert connection.provider == PlatformCredential.META
    assert connection.schedule_type == AirbyteConnection.SCHEDULE_INTERVAL
    assert connection.interval_minutes == 60
    assert connection.last_job_status == "failed"
    assert "timeout" in connection.last_job_error
    assert status.last_connection_id == connection.id
    assert status.last_job_status == "failed"
    assert "created=1" in output.getvalue()
    assert "updated=1" in output.getvalue()


@pytest.mark.django_db
def test_backfill_airbyte_sync_status_dry_run_does_not_create_missing_connections(
    monkeypatch, settings, tenant
):
    from integrations.management.commands import backfill_airbyte_sync_status as command_module

    settings.AIRBYTE_API_URL = "http://airbyte"
    settings.AIRBYTE_API_TOKEN = "token"

    connection_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

        def list_connections(self, workspace_id_value: str):
            assert workspace_id_value == str(workspace_id)
            return [
                {
                    "connectionId": str(connection_id),
                    "name": "Meta Insights Connection",
                    "status": "active",
                }
            ]

        def latest_job(self, _connection_id_value: str):
            return None

    monkeypatch.setattr(
        command_module.AirbyteClient, "from_settings", classmethod(lambda cls: DummyClient())
    )

    output = io.StringIO()
    call_command(
        "backfill_airbyte_sync_status",
        "--tenant-id",
        str(tenant.id),
        "--workspace-id",
        str(workspace_id),
        "--create-missing",
        stdout=output,
    )

    assert not AirbyteConnection.all_objects.filter(connection_id=connection_id).exists()
    assert "would_create=1" in output.getvalue()


@pytest.mark.django_db
def test_reconcile_airbyte_sync_status_dry_run(tenant):
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta stale",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        last_synced_at=now - timedelta(hours=3),
        last_job_status="running",
        last_job_id="142",
        last_job_updated_at=now - timedelta(hours=3),
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)

    output = io.StringIO()
    call_command("reconcile_airbyte_sync_status", "--stale-minutes", "120", stdout=output)

    connection.refresh_from_db()
    assert connection.last_job_status == "running"
    assert "Dry-run" in output.getvalue()
    assert "candidates=1" in output.getvalue()


@pytest.mark.django_db
def test_reconcile_airbyte_sync_status_apply_updates_remote_failure(monkeypatch, settings, tenant):
    from integrations.management.commands import reconcile_airbyte_sync_status as command_module

    settings.AIRBYTE_API_URL = "http://airbyte"
    settings.AIRBYTE_API_TOKEN = "token"
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta stale",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        last_synced_at=now - timedelta(hours=3),
        last_job_status="running",
        last_job_id="142",
        last_job_updated_at=now - timedelta(hours=3),
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

        def latest_job(self, connection_id: str):
            assert connection_id == str(connection.connection_id)
            return {
                "job": {
                    "id": 145,
                    "status": "failed",
                    "createdAt": int((now - timedelta(minutes=2)).timestamp()),
                    "updatedAt": int((now - timedelta(minutes=1)).timestamp()),
                    "errorMessage": "upstream timeout",
                }
            }

    monkeypatch.setattr(
        command_module.AirbyteClient, "from_settings", classmethod(lambda cls: DummyClient())
    )

    output = io.StringIO()
    call_command("reconcile_airbyte_sync_status", "--apply", stdout=output)

    connection.refresh_from_db()
    status = TenantAirbyteSyncStatus.all_objects.get(tenant=tenant)
    assert connection.last_job_status == "failed"
    assert connection.last_job_id == "145"
    assert "timeout" in connection.last_job_error
    assert status.last_job_status == "failed"
    assert "updated=1" in output.getvalue()


@pytest.mark.django_db
def test_reconcile_airbyte_sync_status_force_fails_remote_running(monkeypatch, settings, tenant):
    from integrations.management.commands import reconcile_airbyte_sync_status as command_module

    settings.AIRBYTE_API_URL = "http://airbyte"
    settings.AIRBYTE_API_TOKEN = "token"
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta stale",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        last_synced_at=now - timedelta(hours=4),
        last_job_status="running",
        last_job_id="142",
        last_job_updated_at=now - timedelta(hours=4),
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

        def latest_job(self, connection_id: str):
            assert connection_id == str(connection.connection_id)
            return {
                "job": {
                    "id": 142,
                    "status": "running",
                    "createdAt": int((now - timedelta(hours=4)).timestamp()),
                    "updatedAt": int((now - timedelta(hours=4)).timestamp()),
                }
            }

    monkeypatch.setattr(
        command_module.AirbyteClient, "from_settings", classmethod(lambda cls: DummyClient())
    )

    output = io.StringIO()
    call_command(
        "reconcile_airbyte_sync_status",
        "--apply",
        "--force-stale-failure",
        stdout=output,
    )

    connection.refresh_from_db()
    assert connection.last_job_status == "failed"
    assert "Marked failed by reconcile_airbyte_sync_status" in connection.last_job_error
    assert "forced_failed=1" in output.getvalue()


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


@pytest.mark.django_db
def test_airbyte_celery_task_retries_on_configuration_error(monkeypatch):
    from integrations import tasks as tasks_module

    class RetryCalled(Exception):
        pass

    def raise_config_error(cls):  # noqa: ANN001
        raise AirbyteClientConfigurationError("AIRBYTE_API_URL must be configured")

    def fake_retry_with_backoff(self, *, exc, base_delay=None, max_delay=None, reason=None):
        raise RetryCalled(
            {
                "exc": exc,
                "base_delay": base_delay,
                "max_delay": max_delay,
                "reason": reason,
            }
        )

    monkeypatch.setattr(tasks_module.AirbyteClient, "from_settings", classmethod(raise_config_error))
    monkeypatch.setattr(tasks_module.BaseAdInsightsTask, "retry_with_backoff", fake_retry_with_backoff)

    with pytest.raises(RetryCalled) as excinfo:
        trigger_scheduled_airbyte_syncs.run()

    payload = excinfo.value.args[0]
    assert isinstance(payload["exc"], AirbyteClientConfigurationError)
    assert payload["base_delay"] == 300
    assert payload["max_delay"] == 900
    assert payload["reason"] == RETRY_REASON_AIRBYTE_CLIENT_CONFIGURATION


@pytest.mark.django_db
def test_airbyte_celery_task_retries_on_client_error(monkeypatch):
    from integrations import tasks as tasks_module

    class RetryCalled(Exception):
        pass

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

    class DummyService:
        def __init__(self, client):  # noqa: ANN001
            return None

        def sync_due_connections(self):
            raise AirbyteClientError("boom")

    def fake_retry_with_backoff(self, *, exc, base_delay=None, max_delay=None, reason=None):
        raise RetryCalled(
            {
                "exc": exc,
                "base_delay": base_delay,
                "max_delay": max_delay,
                "reason": reason,
            }
        )

    monkeypatch.setattr(
        tasks_module.AirbyteClient,
        "from_settings",
        classmethod(lambda cls: DummyClient()),
        raising=False,
    )
    monkeypatch.setattr(tasks_module, "AirbyteSyncService", DummyService)
    monkeypatch.setattr(tasks_module.BaseAdInsightsTask, "retry_with_backoff", fake_retry_with_backoff)

    with pytest.raises(RetryCalled) as excinfo:
        trigger_scheduled_airbyte_syncs.run()

    payload = excinfo.value.args[0]
    assert isinstance(payload["exc"], AirbyteClientError)
    assert payload["base_delay"] is None
    assert payload["max_delay"] is None
    assert payload["reason"] == RETRY_REASON_AIRBYTE_CLIENT_ERROR


@pytest.mark.django_db
def test_refresh_airbyte_sync_health_runs_backfill_then_reconcile(monkeypatch, settings):
    from integrations import tasks as tasks_module

    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "workspace-123"
    settings.AIRBYTE_RECONCILE_STALE_MINUTES = 90
    settings.AIRBYTE_RECONCILE_FORCE_STALE_FAILURE = True

    calls: list[tuple[str, ...]] = []

    def fake_call_command(*args, **kwargs):  # noqa: ANN001
        calls.append(tuple(str(arg) for arg in args))
        return None

    monkeypatch.setattr(tasks_module, "call_command", fake_call_command)

    result = refresh_airbyte_sync_health.run()

    assert calls == [
        (
            "backfill_airbyte_sync_status",
            "--apply",
            "--workspace-id",
            "workspace-123",
        ),
        (
            "reconcile_airbyte_sync_status",
            "--stale-minutes",
            "90",
            "--apply",
            "--force-stale-failure",
        ),
    ]
    assert result["workspace_id"] == "workspace-123"
    assert result["stale_minutes"] == 90
    assert result["force_stale_failure"] is True


@pytest.mark.django_db
def test_refresh_airbyte_sync_health_retries_on_configuration_command_error(monkeypatch):
    from integrations import tasks as tasks_module

    class RetryCalled(Exception):
        pass

    def fake_call_command(*args, **kwargs):  # noqa: ANN001
        raise CommandError("AIRBYTE_API_URL must be configured")

    def fake_retry_with_backoff(self, *, exc, base_delay=None, max_delay=None, reason=None):
        raise RetryCalled(
            {
                "exc": exc,
                "base_delay": base_delay,
                "max_delay": max_delay,
                "reason": reason,
            }
        )

    monkeypatch.setattr(tasks_module, "call_command", fake_call_command)
    monkeypatch.setattr(tasks_module.BaseAdInsightsTask, "retry_with_backoff", fake_retry_with_backoff)

    with pytest.raises(RetryCalled) as excinfo:
        refresh_airbyte_sync_health.run()

    payload = excinfo.value.args[0]
    assert isinstance(payload["exc"], CommandError)
    assert payload["base_delay"] == 300
    assert payload["max_delay"] == 900
    assert payload["reason"] == RETRY_REASON_AIRBYTE_CLIENT_CONFIGURATION
