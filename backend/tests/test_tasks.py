from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.conf import settings
from django.db import connection
from django.utils import timezone

from alerts.models import AlertRun
from accounts.tenant_context import get_current_tenant_id
from core.tasks import BaseAdInsightsTask, rotate_deks, _sync_provider_connections, sync_meta_metrics
from integrations.airbyte import AirbyteClientError, AirbyteClientConfigurationError
from integrations.airbyte.service import emit_airbyte_sync_metrics
from integrations.models import AirbyteConnection, ConnectionSyncUpdate, PlatformCredential
from integrations.tasks import remind_expiring_credentials


def test_rotate_deks_updates_key(api_client, user, tenant):
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="123",
    )
    credential.set_raw_tokens("token", "refresh")
    credential.save()
    old_version = credential.dek_key_version
    result = rotate_deks()
    credential.refresh_from_db()
    assert "rotated" in result
    assert credential.dek_key_version != old_version


@pytest.mark.django_db
def test_remind_expiring_credentials_creates_alert(tenant):
    AlertRun.objects.all().delete()
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="acct-42",
        expires_at=timezone.now() + timedelta(days=2),
    )
    credential.set_raw_tokens("access", "refresh")
    credential.save()

    result = remind_expiring_credentials.run()

    assert result["processed"] == 1
    run = AlertRun.objects.latest("created_at")
    assert run.rule_slug == "credential_rotation_due"
    assert run.row_count == 1
    payload = run.raw_results[0]
    assert payload["provider"] == PlatformCredential.META
    assert payload["credential_ref"].startswith("ref_")
    assert payload["status"] == "expiring"


@pytest.mark.django_db
def test_remind_expiring_credentials_without_matches():
    AlertRun.objects.all().delete()

    result = remind_expiring_credentials.run()

    assert result == {"processed": 0}
    assert AlertRun.objects.count() == 0


def test_rotate_deks_schedule_present():
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "rotate-tenant-deks" in schedule
    entry = schedule["rotate-tenant-deks"]
    assert entry["task"] == "core.tasks.rotate_deks"


def test_ai_daily_summary_schedule_present():
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "ai-daily-summary" in schedule
    entry = schedule["ai-daily-summary"]
    assert entry["task"] == "analytics.ai_daily_summary"


def test_sync_provider_sets_tenant_context(monkeypatch, tenant):
    recorded: list[str | None] = []

    class DummyQueryset(list):
        def select_related(self, *args, **kwargs):
            return self

    def fake_filter(*args, **kwargs):
        recorded.append(get_current_tenant_id())
        return DummyQueryset()

    monkeypatch.setattr(AirbyteConnection.objects, "filter", fake_filter, raising=False)

    dummy_task = type("Task", (), {"request": type("Req", (), {"id": "task-123"})()})()

    previous = getattr(connection, settings.TENANT_SETTING_KEY, None)

    outcome = _sync_provider_connections(
        dummy_task,
        tenant=tenant,
        user=None,
        provider=PlatformCredential.META,
    )

    assert outcome == "no_connections"
    assert recorded and recorded[0] == str(tenant.id)
    assert get_current_tenant_id() is None
    assert getattr(connection, settings.TENANT_SETTING_KEY, None) == previous


@pytest.mark.django_db
def test_sync_meta_metrics_task_applies_tenant_context(monkeypatch, tenant):
    recorded: dict[str, str | None] = {}

    def fake_sync(task, *, tenant, user, provider):  # noqa: ANN001
        recorded["tenant"] = str(tenant.id)
        recorded["context"] = get_current_tenant_id()
        return "ok"

    monkeypatch.setattr("core.tasks._sync_provider_connections", fake_sync)

    result = sync_meta_metrics.apply(args=(str(tenant.id),))
    assert result.get() == "ok"
    assert recorded["tenant"] == str(tenant.id)
    assert recorded["context"] == str(tenant.id)
    assert get_current_tenant_id() is None


class RetryCalled(Exception):
    pass


@pytest.mark.django_db
def test_sync_provider_retries_on_client_error(monkeypatch, tenant):
    class DummyTask:
        name = "dummy.task"
        retry_backoff_base_seconds = BaseAdInsightsTask.retry_backoff_base_seconds
        retry_backoff_max_seconds = BaseAdInsightsTask.retry_backoff_max_seconds

        def __init__(self):
            self.request = type("Req", (), {"id": "task-42", "retries": 0})()
            self.retry_args = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None):
            return BaseAdInsightsTask.retry_with_backoff(
                self, exc=exc, base_delay=base_delay, max_delay=max_delay
            )

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

    def fake_from_settings(cls):  # noqa: ANN001
        return DummyClient()

    def fake_sync(self, connections, *, triggered_at=None):  # noqa: ANN001
        raise AirbyteClientError("upstream timeout")

    monkeypatch.setattr("core.tasks.AirbyteClient.from_settings", classmethod(fake_from_settings))
    monkeypatch.setattr("core.tasks.AirbyteSyncService.sync_connections", fake_sync)
    monkeypatch.setattr("core.tasks.random.randint", lambda *_args, **_kwargs: 0)

    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        last_synced_at=timezone.now() - timedelta(hours=2),
    )

    task = DummyTask()
    with pytest.raises(RetryCalled):
        _sync_provider_connections(task, tenant=tenant, user=None, provider=PlatformCredential.META)

    assert isinstance(task.retry_args["exc"], AirbyteClientError)
    assert task.retry_args["countdown"] == 60


@pytest.mark.django_db
def test_sync_provider_configuration_error_backoff(monkeypatch, tenant):
    class DummyTask:
        name = "dummy.task"
        retry_backoff_base_seconds = BaseAdInsightsTask.retry_backoff_base_seconds
        retry_backoff_max_seconds = BaseAdInsightsTask.retry_backoff_max_seconds

        def __init__(self):
            self.request = type("Req", (), {"id": "task-99", "retries": 0})()
            self.retry_args = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None):
            return BaseAdInsightsTask.retry_with_backoff(
                self, exc=exc, base_delay=base_delay, max_delay=max_delay
            )

    def fake_from_settings(cls):  # noqa: ANN001
        raise AirbyteClientConfigurationError("missing api token")

    monkeypatch.setattr("core.tasks.AirbyteClient.from_settings", classmethod(fake_from_settings))
    monkeypatch.setattr("core.tasks.random.randint", lambda *_args, **_kwargs: 0)

    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Google Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.GOOGLE,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=timezone.now() - timedelta(hours=3),
    )

    task = DummyTask()
    with pytest.raises(RetryCalled):
        _sync_provider_connections(task, tenant=tenant, user=None, provider=PlatformCredential.GOOGLE)

    assert isinstance(task.retry_args["exc"], AirbyteClientConfigurationError)
    assert task.retry_args["countdown"] == 300


def test_base_task_retry_with_backoff(monkeypatch):
    class DummyTask:
        name = "dummy.task"
        retry_backoff_base_seconds = BaseAdInsightsTask.retry_backoff_base_seconds
        retry_backoff_max_seconds = BaseAdInsightsTask.retry_backoff_max_seconds

        def __init__(self):
            self.request = type("Req", (), {"id": "task-lookup", "retries": 1})()
            self.retry_args = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None):
            return BaseAdInsightsTask.retry_with_backoff(
                self, exc=exc, base_delay=base_delay, max_delay=max_delay
            )

    monkeypatch.setattr("core.tasks.random.randint", lambda *_args, **_kwargs: 5)
    task = DummyTask()
    with pytest.raises(RetryCalled):
        task.retry_with_backoff(exc=RuntimeError("boom"), base_delay=10, max_delay=120)

    assert isinstance(task.retry_args["exc"], RuntimeError)
    assert task.retry_args["countdown"] == 25


@pytest.mark.django_db
def test_sync_provider_retry_backoff_grows_with_attempts(monkeypatch, tenant):
    class DummyTask:
        name = "dummy.task"
        retry_backoff_base_seconds = BaseAdInsightsTask.retry_backoff_base_seconds
        retry_backoff_max_seconds = BaseAdInsightsTask.retry_backoff_max_seconds

        def __init__(self):
            self.request = type("Req", (), {"id": "task-200", "retries": 2})()
            self.retry_args = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None):
            return BaseAdInsightsTask.retry_with_backoff(
                self, exc=exc, base_delay=base_delay, max_delay=max_delay
            )

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

    def fake_from_settings(cls):  # noqa: ANN001
        return DummyClient()

    def fake_sync(self, connections, *, triggered_at=None):  # noqa: ANN001
        raise AirbyteClientError("timeout")

    monkeypatch.setattr("core.tasks.AirbyteClient.from_settings", classmethod(fake_from_settings))
    monkeypatch.setattr("core.tasks.AirbyteSyncService.sync_connections", fake_sync)
    monkeypatch.setattr("core.tasks.random.randint", lambda *_args, **_kwargs: 5)

    AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=120,
        last_synced_at=timezone.now() - timedelta(hours=5),
    )

    task = DummyTask()
    with pytest.raises(RetryCalled):
        _sync_provider_connections(task, tenant=tenant, user=None, provider=PlatformCredential.META)

    assert isinstance(task.retry_args["exc"], AirbyteClientError)
    assert task.retry_args["countdown"] == 245


@pytest.mark.django_db
def test_emit_airbyte_sync_metrics_records_observations(monkeypatch, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=15,
    )
    update = ConnectionSyncUpdate(
        connection=connection,
        job_id="99",
        status="succeeded",
        created_at=timezone.now(),
        updated_at=None,
        completed_at=None,
        duration_seconds=12,
        records_synced=5,
        bytes_synced=None,
        api_cost=Decimal("0"),
        error=None,
    )
    recorded: list[dict[str, object]] = []

    def fake_observe(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    monkeypatch.setattr("integrations.airbyte.service.observe_airbyte_sync", fake_observe)

    emit_airbyte_sync_metrics([update])

    assert recorded
    payload = recorded[0]
    assert payload["tenant_id"] == str(tenant.id)
    assert payload["status"] == "succeeded"
    assert payload["records_synced"] == 5


@pytest.mark.django_db
def test_sync_provider_connections_emits_metrics(monkeypatch, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta Sync",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=10,
        last_synced_at=timezone.now() - timedelta(minutes=90),
    )

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN002, ANN003
            return None

    monkeypatch.setattr("core.tasks.AirbyteClient.from_settings", classmethod(lambda cls: DummyClient()))

    def fake_service_init(self, client):  # noqa: ANN001
        assert isinstance(client, DummyClient)

    def fake_sync(self, due_connections, *, triggered_at=None):  # noqa: ANN001
        connection_obj = due_connections[0]
        return [
            ConnectionSyncUpdate(
                connection=connection_obj,
                job_id="123",
                status="succeeded",
                created_at=timezone.now(),
                updated_at=None,
                completed_at=timezone.now(),
                duration_seconds=9,
                records_synced=11,
                bytes_synced=None,
                api_cost=Decimal("0"),
                error=None,
            )
        ]

    monkeypatch.setattr("core.tasks.AirbyteSyncService.__init__", fake_service_init, raising=False)
    monkeypatch.setattr("core.tasks.AirbyteSyncService.sync_connections", fake_sync, raising=False)

    captured: dict[str, list[ConnectionSyncUpdate]] = {}

    def fake_emit(updates):  # noqa: ANN001
        captured["updates"] = list(updates)

    monkeypatch.setattr("core.tasks.emit_airbyte_sync_metrics", fake_emit)

    dummy_task = type("Task", (), {"request": type("Req", (), {"id": "task-555"})()})()

    result = _sync_provider_connections(dummy_task, tenant=tenant, user=None, provider=PlatformCredential.META)

    assert result.startswith("triggered 1")
    assert "updates" in captured
    assert len(captured["updates"]) == 1
    assert captured["updates"][0].connection.tenant_id == tenant.id
    assert captured["updates"][0].connection.id == connection.id
