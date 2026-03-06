from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.utils import timezone

import core.settings as core_settings
from alerts.models import AlertRun
from accounts.tenant_context import get_current_tenant_id
from core.metrics import CELERY_TASK_RETRY_TOTAL, reset_metrics
from core.tasks import (
    AIRBYTE_RETRY_REASON_CLIENT_CONFIGURATION,
    AIRBYTE_RETRY_REASON_CLIENT_ERROR,
    AIRBYTE_RETRY_REASON_RATE_LIMITED,
    AIRBYTE_RETRY_REASON_UNKNOWN,
    AIRBYTE_RETRY_REASON_UPSTREAM_5XX,
    AIRBYTE_RETRY_REASON_UPSTREAM_TIMEOUT,
    BaseAdInsightsTask,
    _classify_airbyte_retry_reason,
    _retry_task,
    _sync_provider_connections,
    rotate_deks,
    sync_meta_metrics,
)
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
    assert entry["options"]["queue"] == settings.CELERY_QUEUE_SUMMARY


def test_airbyte_scheduled_sync_hourly_window_present():
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "airbyte-scheduled-syncs-hourly" in schedule
    entry = schedule["airbyte-scheduled-syncs-hourly"]
    assert entry["task"] == "integrations.tasks.trigger_scheduled_airbyte_syncs"
    assert entry["options"]["queue"] == settings.CELERY_QUEUE_SYNC


def test_metrics_snapshot_sync_schedule_present():
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "metrics-snapshot-sync" in schedule
    entry = schedule["metrics-snapshot-sync"]
    assert entry["task"] == "analytics.sync_metrics_snapshots"
    assert entry["options"]["queue"] == settings.CELERY_QUEUE_SNAPSHOT


def test_celery_task_routes_assign_workload_queues():
    routes = settings.CELERY_TASK_ROUTES
    assert routes["core.tasks.sync_meta_metrics"]["queue"] == settings.CELERY_QUEUE_SYNC
    assert routes["integrations.tasks.sync_*"]["queue"] == settings.CELERY_QUEUE_SYNC
    assert routes["integrations.tasks.evaluate_*"]["queue"] == settings.CELERY_QUEUE_SYNC
    assert routes["analytics.sync_metrics_snapshots"]["queue"] == settings.CELERY_QUEUE_SNAPSHOT
    assert routes["analytics.ai_daily_summary"]["queue"] == settings.CELERY_QUEUE_SUMMARY


def test_celery_task_queues_include_workload_queues():
    queue_names = {queue.name for queue in settings.CELERY_TASK_QUEUES}
    assert settings.CELERY_TASK_DEFAULT_QUEUE in queue_names
    assert settings.CELERY_QUEUE_SYNC in queue_names
    assert settings.CELERY_QUEUE_SNAPSHOT in queue_names
    assert settings.CELERY_QUEUE_SUMMARY in queue_names


def test_celery_queue_settings_are_distinct_non_empty():
    queue_names = [
        settings.CELERY_TASK_DEFAULT_QUEUE,
        settings.CELERY_QUEUE_SYNC,
        settings.CELERY_QUEUE_SNAPSHOT,
        settings.CELERY_QUEUE_SUMMARY,
    ]
    assert all(isinstance(queue_name, str) and queue_name.strip() for queue_name in queue_names)
    assert len(set(queue_names)) == len(queue_names)


def test_celery_worker_runtime_settings_are_valid():
    assert settings.CELERY_WORKER_CONCURRENCY >= 1
    assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER >= 1
    assert settings.CELERY_WORKER_MAX_TASKS_PER_CHILD >= 1
    assert settings.CELERY_WORKER_MAX_MEMORY_PER_CHILD >= 0
    assert settings.CELERY_WORKER_CONCURRENCY_BUDGET >= 3
    assert settings.CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE >= 1
    assert settings.CELERY_WORKER_MAX_PREFETCH_MULTIPLIER >= 1
    assert settings.CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO >= 1


def test_celery_worker_profile_queues_reference_known_values():
    queue_names = {queue.name for queue in settings.CELERY_TASK_QUEUES}
    assert settings.CELERY_QUEUE_SYNC in settings.CELERY_WORKER_SYNC_QUEUES
    assert settings.CELERY_QUEUE_SNAPSHOT in settings.CELERY_WORKER_SNAPSHOT_QUEUES
    assert settings.CELERY_QUEUE_SUMMARY in settings.CELERY_WORKER_SUMMARY_QUEUES

    for queue_name in settings.CELERY_WORKER_SYNC_QUEUES:
        assert queue_name in queue_names
    for queue_name in settings.CELERY_WORKER_SNAPSHOT_QUEUES:
        assert queue_name in queue_names
    for queue_name in settings.CELERY_WORKER_SUMMARY_QUEUES:
        assert queue_name in queue_names


def test_celery_worker_profile_values_are_valid():
    assert settings.CELERY_WORKER_SYNC_CONCURRENCY >= 1
    assert settings.CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER >= 1
    assert settings.CELERY_WORKER_SYNC_MAX_TASKS_PER_CHILD >= 1
    assert settings.CELERY_WORKER_SNAPSHOT_CONCURRENCY >= 1
    assert settings.CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER >= 1
    assert settings.CELERY_WORKER_SNAPSHOT_MAX_TASKS_PER_CHILD >= 1
    assert settings.CELERY_WORKER_SUMMARY_CONCURRENCY >= 1
    assert settings.CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER >= 1
    assert settings.CELERY_WORKER_SUMMARY_MAX_TASKS_PER_CHILD >= 1
    assert settings.CELERY_WORKER_SYNC_CONCURRENCY <= settings.CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE
    assert settings.CELERY_WORKER_SNAPSHOT_CONCURRENCY <= settings.CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE
    assert settings.CELERY_WORKER_SUMMARY_CONCURRENCY <= settings.CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE
    assert (
        settings.CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER
        <= settings.CELERY_WORKER_MAX_PREFETCH_MULTIPLIER
    )
    assert (
        settings.CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER
        <= settings.CELERY_WORKER_MAX_PREFETCH_MULTIPLIER
    )
    assert (
        settings.CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER
        <= settings.CELERY_WORKER_MAX_PREFETCH_MULTIPLIER
    )
    assert (
        settings.CELERY_WORKER_SYNC_CONCURRENCY
        + settings.CELERY_WORKER_SNAPSHOT_CONCURRENCY
        + settings.CELERY_WORKER_SUMMARY_CONCURRENCY
        <= settings.CELERY_WORKER_CONCURRENCY_BUDGET
    )
    assert (
        settings.CELERY_WORKER_SYNC_CONCURRENCY
        <= (
            settings.CELERY_WORKER_SNAPSHOT_CONCURRENCY
            + settings.CELERY_WORKER_SUMMARY_CONCURRENCY
        )
        * settings.CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO
    )


def test_celery_routes_never_use_unknown_queues():
    queue_names = {queue.name for queue in settings.CELERY_TASK_QUEUES}
    for route in settings.CELERY_TASK_ROUTES.values():
        queue_name = route.get("queue")
        if queue_name:
            assert queue_name in queue_names


def test_celery_critical_routes_do_not_fall_back_to_default_queue():
    routes = settings.CELERY_TASK_ROUTES
    default_queue = settings.CELERY_TASK_DEFAULT_QUEUE
    critical_routes = [
        "integrations.tasks.sync_*",
        "integrations.tasks.refresh_*",
        "integrations.tasks.evaluate_*",
        "analytics.sync_metrics_snapshots",
        "analytics.ai_daily_summary",
        "analytics.run_report_export_job",
    ]
    for route_name in critical_routes:
        assert route_name in routes
        assert routes[route_name]["queue"] != default_queue


def test_celery_beat_schedule_queues_use_known_values():
    queue_names = {queue.name for queue in settings.CELERY_TASK_QUEUES}
    schedule = settings.CELERY_BEAT_SCHEDULE
    allow_no_queue = {
        "alerts-quarter-hourly",
        "rotate-tenant-deks",
    }

    for schedule_name, entry in schedule.items():
        options = entry.get("options")
        if schedule_name in allow_no_queue:
            continue
        assert isinstance(options, dict)
        queue_name = options.get("queue")
        assert isinstance(queue_name, str)
        assert queue_name in queue_names


def test_celery_runtime_validation_rejects_duplicate_queue_names(monkeypatch):
    monkeypatch.setattr(core_settings, "CELERY_TASK_DEFAULT_QUEUE", core_settings.CELERY_QUEUE_SYNC)

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


def test_celery_runtime_validation_rejects_unknown_schedule_queue(monkeypatch):
    monkeypatch.setattr(
        core_settings,
        "CELERY_BEAT_SCHEDULE",
        {
            "invalid-queue-entry": {
                "task": "integrations.tasks.sync_meta_accounts",
                "schedule": object(),
                "options": {"queue": "missing"},
            }
        },
    )

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


def test_celery_runtime_validation_rejects_unknown_worker_profile_queue(monkeypatch):
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SUMMARY_QUEUES", ("missing",))

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


def test_celery_runtime_validation_rejects_worker_profile_without_required_queue(monkeypatch):
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SNAPSHOT_QUEUES", (core_settings.CELERY_QUEUE_SYNC,))

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


def test_celery_runtime_validation_rejects_prefetch_multiplier_above_cap(monkeypatch):
    monkeypatch.setattr(core_settings, "CELERY_WORKER_MAX_PREFETCH_MULTIPLIER", 1)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER", 2)

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


def test_celery_runtime_validation_rejects_profile_concurrency_above_cap(monkeypatch):
    monkeypatch.setattr(core_settings, "CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE", 2)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SYNC_CONCURRENCY", 3)

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


def test_celery_runtime_validation_rejects_total_profile_concurrency_above_budget(monkeypatch):
    monkeypatch.setattr(core_settings, "CELERY_WORKER_CONCURRENCY_BUDGET", 4)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SYNC_CONCURRENCY", 3)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SNAPSHOT_CONCURRENCY", 1)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SUMMARY_CONCURRENCY", 1)

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


def test_celery_runtime_validation_rejects_sync_fairness_ratio_breach(monkeypatch):
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO", 2)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SYNC_CONCURRENCY", 9)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SNAPSHOT_CONCURRENCY", 2)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_SUMMARY_CONCURRENCY", 2)
    monkeypatch.setattr(core_settings, "CELERY_WORKER_CONCURRENCY_BUDGET", 16)

    with pytest.raises(ImproperlyConfigured):
        core_settings._validate_celery_runtime_configuration()


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
            self.retry_reason = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None, reason=None):
            self.retry_reason = reason
            return BaseAdInsightsTask.retry_with_backoff(
                self,
                exc=exc,
                base_delay=base_delay,
                max_delay=max_delay,
                reason=reason,
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
    assert task.retry_reason == AIRBYTE_RETRY_REASON_CLIENT_ERROR


@pytest.mark.django_db
def test_sync_provider_configuration_error_backoff(monkeypatch, tenant):
    class DummyTask:
        name = "dummy.task"
        retry_backoff_base_seconds = BaseAdInsightsTask.retry_backoff_base_seconds
        retry_backoff_max_seconds = BaseAdInsightsTask.retry_backoff_max_seconds

        def __init__(self):
            self.request = type("Req", (), {"id": "task-99", "retries": 0})()
            self.retry_args = None
            self.retry_reason = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.retry_args = {"exc": exc, "countdown": countdown}
            raise RetryCalled

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None, reason=None):
            self.retry_reason = reason
            return BaseAdInsightsTask.retry_with_backoff(
                self,
                exc=exc,
                base_delay=base_delay,
                max_delay=max_delay,
                reason=reason,
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
    assert task.retry_reason == AIRBYTE_RETRY_REASON_CLIENT_CONFIGURATION


def test_classify_airbyte_retry_reason_for_rate_limited_status():
    reason = _classify_airbyte_retry_reason(
        AirbyteClientError("rate limited", status_code=429)
    )

    assert reason == AIRBYTE_RETRY_REASON_RATE_LIMITED


def test_classify_airbyte_retry_reason_for_upstream_5xx():
    reason = _classify_airbyte_retry_reason(
        AirbyteClientError("upstream error", status_code=503)
    )

    assert reason == AIRBYTE_RETRY_REASON_UPSTREAM_5XX


def test_classify_airbyte_retry_reason_for_upstream_timeout_status():
    reason = _classify_airbyte_retry_reason(
        AirbyteClientError("gateway timeout", status_code=504)
    )

    assert reason == AIRBYTE_RETRY_REASON_UPSTREAM_TIMEOUT


def test_classify_airbyte_retry_reason_falls_back_to_client_error_without_status():
    reason = _classify_airbyte_retry_reason(AirbyteClientError("transport error"))

    assert reason == AIRBYTE_RETRY_REASON_CLIENT_ERROR


def test_classify_airbyte_retry_reason_falls_back_to_unknown_for_non_airbyte_exception():
    reason = _classify_airbyte_retry_reason(RuntimeError("boom"))

    assert reason == AIRBYTE_RETRY_REASON_UNKNOWN


def test_base_task_retry_with_backoff(monkeypatch):
    reset_metrics(registries=[CELERY_TASK_RETRY_TOTAL])

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

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None, reason=None):
            return BaseAdInsightsTask.retry_with_backoff(
                self, exc=exc, base_delay=base_delay, max_delay=max_delay, reason=reason
            )

    monkeypatch.setattr("core.tasks.random.randint", lambda *_args, **_kwargs: 5)
    task = DummyTask()
    with pytest.raises(RetryCalled):
        task.retry_with_backoff(exc=RuntimeError("boom"), base_delay=10, max_delay=120)

    assert isinstance(task.retry_args["exc"], RuntimeError)
    assert task.retry_args["countdown"] == 25
    samples = CELERY_TASK_RETRY_TOTAL.collect()[0].samples
    retry_sample = next(
        sample
        for sample in samples
        if sample.name == "celery_task_retries_total"
        and sample.labels == {"task_name": "dummy.task", "reason": "airbyte_unknown_error"}
    )
    assert retry_sample.value == 1


def test_retry_task_legacy_helper_compatibility():
    reset_metrics(registries=[CELERY_TASK_RETRY_TOTAL])

    class LegacyTask:
        name = "legacy.task"

        def __init__(self):
            self.called = None

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None):  # noqa: ANN001
            self.called = {
                "exc": exc,
                "base_delay": base_delay,
                "max_delay": max_delay,
            }
            raise RetryCalled

    task = LegacyTask()
    with pytest.raises(RetryCalled):
        _retry_task(
            task,
            exc=RuntimeError("boom"),
            reason="ignored_for_legacy",
            base_delay=15,
            max_delay=30,
        )

    assert isinstance(task.called["exc"], RuntimeError)
    assert task.called["base_delay"] == 15
    assert task.called["max_delay"] == 30
    retry_sample = next(
        sample
        for sample in CELERY_TASK_RETRY_TOTAL.collect()[0].samples
        if sample.name == "celery_task_retries_total"
        and sample.labels == {"task_name": "legacy.task", "reason": "ignored_for_legacy"}
    )
    assert retry_sample.value == 1


def test_retry_task_without_helper_records_reason_metric():
    reset_metrics(registries=[CELERY_TASK_RETRY_TOTAL])

    class RetryOnlyTask:
        name = "retry.only.task"
        default_retry_delay = 12

        def __init__(self):
            self.called = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.called = {"exc": exc, "countdown": countdown}
            raise RetryCalled

    task = RetryOnlyTask()
    with pytest.raises(RetryCalled):
        _retry_task(
            task,
            exc=RuntimeError("boom"),
            reason="explicit_retry_reason",
            base_delay=30,
        )

    assert isinstance(task.called["exc"], RuntimeError)
    assert task.called["countdown"] == 30
    retry_sample = next(
        sample
        for sample in CELERY_TASK_RETRY_TOTAL.collect()[0].samples
        if sample.name == "celery_task_retries_total"
        and sample.labels == {"task_name": "retry.only.task", "reason": "explicit_retry_reason"}
    )
    assert retry_sample.value == 1


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
