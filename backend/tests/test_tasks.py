from __future__ import annotations

from datetime import timedelta
import uuid

import pytest
from django.conf import settings
from django.utils import timezone

from alerts.models import AlertRun
from accounts.tenant_context import get_current_tenant_id
from core.tasks import rotate_deks, _sync_provider_connections
from integrations.models import AirbyteConnection, PlatformCredential
from integrations.airbyte import AirbyteClientError, AirbyteClientConfigurationError
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

    outcome = _sync_provider_connections(
        dummy_task,
        tenant=tenant,
        user=None,
        provider=PlatformCredential.META,
    )

    assert outcome == "no_connections"
    assert recorded and recorded[0] == str(tenant.id)
    assert get_current_tenant_id() is None


class RetryCalled(Exception):
    pass


@pytest.mark.django_db
def test_sync_provider_retries_on_client_error(monkeypatch, tenant):
    class DummyTask:
        def __init__(self):
            self.request = type("Req", (), {"id": "task-42"})()
            self.retry_args = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

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
    assert task.retry_args["countdown"] is None


@pytest.mark.django_db
def test_sync_provider_configuration_error_backoff(monkeypatch, tenant):
    class DummyTask:
        def __init__(self):
            self.request = type("Req", (), {"id": "task-99"})()
            self.retry_args = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

    def fake_from_settings(cls):  # noqa: ANN001
        raise AirbyteClientConfigurationError("missing api token")

    monkeypatch.setattr("core.tasks.AirbyteClient.from_settings", classmethod(fake_from_settings))

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
