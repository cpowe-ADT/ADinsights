from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import Tenant
from analytics.models import TenantMetricsSnapshot
from analytics.tasks import (
    DAILY_SUMMARY_FAILURE_REASON_GENERATION,
    SNAPSHOT_FAILURE_REASON_GENERATION,
    SNAPSHOT_FAILURE_REASON_LOCKED,
    SNAPSHOT_LOCK_SCOPE_ALL,
    SNAPSHOT_STALE_TTL_SECONDS,
    _retry_analytics_task,
    _snapshot_lock_scope,
    _snapshot_sync_lock_key_for_tenants,
    ai_daily_summary,
    evaluate_snapshot_freshness,
    generate_snapshots_for_tenants,
    sync_metrics_snapshots,
)
from core.metrics import CELERY_TASK_RETRY_TOTAL, reset_metrics
from core.tasks import BaseAdInsightsTask


def _seed_dashboard_snapshot_view(records: list[dict[str, object]]):
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS vw_dashboard_aggregate_snapshot")
        cursor.execute(
            """
            CREATE TABLE vw_dashboard_aggregate_snapshot (
                tenant_id TEXT,
                generated_at TEXT,
                campaign_metrics TEXT,
                creative_metrics TEXT,
                budget_metrics TEXT,
                parish_metrics TEXT
            )
            """
        )
        for record in records:
            cursor.execute(
                """
                INSERT INTO vw_dashboard_aggregate_snapshot
                (tenant_id, generated_at, campaign_metrics, creative_metrics, budget_metrics, parish_metrics)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["tenant_id"],
                    record["generated_at"],
                    json.dumps(record["campaign_metrics"]),
                    json.dumps(record["creative_metrics"]),
                    json.dumps(record["budget_metrics"]),
                    json.dumps(record["parish_metrics"]),
                ),
            )


@pytest.mark.django_db
def test_generate_snapshots_for_tenants_creates_payloads(tenant):
    other_tenant = Tenant.objects.create(name="Tenant B")
    now = timezone.now().isoformat()
    _seed_dashboard_snapshot_view(
        [
            {
                "tenant_id": str(tenant.id),
                "generated_at": now,
                "campaign_metrics": {
                    "summary": {"currency": "USD", "totalSpend": 100},
                    "trend": [],
                    "rows": [],
                },
                "creative_metrics": [],
                "budget_metrics": [],
                "parish_metrics": [],
            },
            {
                "tenant_id": str(other_tenant.id),
                "generated_at": now,
                "campaign_metrics": {
                    "summary": {"currency": "USD", "totalSpend": 50},
                    "trend": [],
                    "rows": [],
                },
                "creative_metrics": [],
                "budget_metrics": [],
                "parish_metrics": [],
            },
        ]
    )

    outcomes = generate_snapshots_for_tenants([str(tenant.id), str(other_tenant.id)])

    assert len(outcomes) == 2
    outcome_map = {outcome.tenant_id: outcome for outcome in outcomes}
    assert outcome_map[str(tenant.id)].row_counts["campaign_rows"] == 0
    assert outcome_map[str(tenant.id)].row_counts["creative"] == 0
    assert outcome_map[str(tenant.id)].stale is False
    snapshot = TenantMetricsSnapshot.objects.get(tenant=tenant, source="warehouse")
    assert snapshot.payload["campaign"]["summary"]["totalSpend"] == 100
    assert "snapshot_generated_at" in snapshot.payload


@pytest.mark.django_db
def test_snapshot_management_command_limits_to_single_tenant(tenant):
    now = timezone.now().isoformat()
    _seed_dashboard_snapshot_view(
        [
            {
                "tenant_id": str(tenant.id),
                "generated_at": now,
                "campaign_metrics": {
                    "summary": {"currency": "USD", "totalSpend": 75},
                    "trend": [],
                    "rows": [],
                },
                "creative_metrics": [],
                "budget_metrics": [],
                "parish_metrics": [],
            }
        ]
    )

    call_command("snapshot_metrics", "--tenant-id", str(tenant.id))

    snapshot = TenantMetricsSnapshot.objects.get(tenant=tenant, source="warehouse")
    assert snapshot.payload["campaign"]["summary"]["totalSpend"] == 75


@pytest.mark.django_db
def test_generate_snapshots_normalizes_generated_at_timezone(tenant):
    naive_timestamp = "2024-01-02T13:00:00"
    _seed_dashboard_snapshot_view(
        [
            {
                "tenant_id": str(tenant.id),
                "generated_at": naive_timestamp,
                "campaign_metrics": {
                    "summary": {"currency": "USD", "totalSpend": 42},
                    "trend": [],
                    "rows": [],
                },
                "creative_metrics": [],
                "budget_metrics": [],
                "parish_metrics": [],
            }
        ]
    )

    outcomes = generate_snapshots_for_tenants([str(tenant.id)])

    assert len(outcomes) == 1
    snapshot = TenantMetricsSnapshot.objects.get(tenant=tenant, source="warehouse")
    assert timezone.is_aware(snapshot.generated_at)
    parsed = parse_datetime(snapshot.payload["snapshot_generated_at"])
    assert parsed is not None and timezone.is_aware(parsed)


def test_sync_metrics_snapshots_has_retry_policy():
    assert sync_metrics_snapshots.max_retries == 5


class RetryCalled(Exception):
    pass


def test_sync_metrics_snapshots_retries_with_backoff(monkeypatch):
    recorded: dict[str, object] = {}
    released: list[tuple[str, str | None]] = []

    def fake_generate(tenant_ids=None):  # noqa: ANN001
        raise RuntimeError("boom")

    def fake_retry(self, *, exc=None, base_delay=None, max_delay=None, reason=None):  # noqa: ANN001
        recorded["exc"] = exc
        recorded["base_delay"] = base_delay
        recorded["max_delay"] = max_delay
        recorded["reason"] = reason
        raise RetryCalled

    monkeypatch.setattr("analytics.tasks.generate_snapshots_for_tenants", fake_generate)
    monkeypatch.setattr(BaseAdInsightsTask, "retry_with_backoff", fake_retry, raising=False)
    monkeypatch.setattr(
        "analytics.tasks._acquire_snapshot_sync_lock",
        lambda **_kwargs: "lock-token",
    )
    monkeypatch.setattr(
        "analytics.tasks._release_snapshot_sync_lock",
        lambda **kwargs: released.append((kwargs["lock_key"], kwargs["token"])),
    )

    observed: list[tuple[str, str, float | None]] = []

    def fake_observe(task_name, status, duration_seconds):  # noqa: ANN001
        observed.append((task_name, status, duration_seconds))

    monkeypatch.setattr("analytics.tasks.observe_task", fake_observe)

    with pytest.raises(RetryCalled):
        sync_metrics_snapshots.run(tenant_ids=["tenant-a"])

    assert recorded["base_delay"] == 60
    assert recorded["max_delay"] == 900
    assert recorded["reason"] == SNAPSHOT_FAILURE_REASON_GENERATION
    assert observed
    assert observed[0][1] == "failure"
    assert released
    assert released[0][1] == "lock-token"


def test_sync_metrics_snapshots_skips_when_lock_not_acquired(monkeypatch):
    observed: list[tuple[str, str, float | None]] = []

    def fake_observe(task_name, status, duration_seconds):  # noqa: ANN001
        observed.append((task_name, status, duration_seconds))

    monkeypatch.setattr("analytics.tasks.observe_task", fake_observe)
    monkeypatch.setattr(
        "analytics.tasks._acquire_snapshot_sync_lock",
        lambda **_kwargs: None,
    )

    def should_not_run(_tenant_ids=None):  # noqa: ANN001
        raise AssertionError("generate_snapshots_for_tenants must not run when lock is held")

    monkeypatch.setattr("analytics.tasks.generate_snapshots_for_tenants", should_not_run)

    result = sync_metrics_snapshots.run(tenant_ids=["tenant-a"])

    assert result["skipped"] is True
    assert result["reason"] == SNAPSHOT_FAILURE_REASON_LOCKED
    assert observed
    assert observed[0][1] == "skipped"


def test_snapshot_lock_scope_is_order_insensitive():
    first = _snapshot_lock_scope(["tenant-b", "tenant-a", "tenant-a"])
    second = _snapshot_lock_scope(["tenant-a", "tenant-b"])
    assert first == second
    assert first.startswith("subset-2-")


def test_snapshot_lock_scope_defaults_to_all_scope():
    assert _snapshot_lock_scope(None) == SNAPSHOT_LOCK_SCOPE_ALL
    assert _snapshot_lock_scope([]) == SNAPSHOT_LOCK_SCOPE_ALL


def test_sync_metrics_snapshots_uses_tenant_scoped_lock_key_and_ttl(monkeypatch, settings):
    settings.METRICS_SNAPSHOT_SYNC_LOCK_TTL_SECONDS = 321
    captured: dict[str, object] = {}

    def fake_acquire(*, lock_key: str, ttl_seconds: int):  # noqa: D401 - test helper
        captured["lock_key"] = lock_key
        captured["ttl_seconds"] = ttl_seconds
        return None

    monkeypatch.setattr("analytics.tasks._acquire_snapshot_sync_lock", fake_acquire)

    result = sync_metrics_snapshots.run(tenant_ids=["tenant-b", "tenant-a", "tenant-a"])

    assert result["skipped"] is True
    assert result["tenant_scope"].startswith("subset-2-")
    assert captured["lock_key"] == _snapshot_sync_lock_key_for_tenants(["tenant-a", "tenant-b"])
    assert captured["ttl_seconds"] == 321


@pytest.mark.django_db
def test_generate_snapshots_respects_configured_stale_ttl(tenant, settings):
    settings.METRICS_SNAPSHOT_STALE_TTL_SECONDS = 5
    generated_at = (timezone.now() - timedelta(seconds=15)).isoformat()
    _seed_dashboard_snapshot_view(
        [
            {
                "tenant_id": str(tenant.id),
                "generated_at": generated_at,
                "campaign_metrics": {
                    "summary": {"currency": "USD", "totalSpend": 42},
                    "trend": [],
                    "rows": [],
                },
                "creative_metrics": [],
                "budget_metrics": [],
                "parish_metrics": [],
            }
        ]
    )

    outcomes = generate_snapshots_for_tenants([str(tenant.id)])

    assert len(outcomes) == 1
    assert outcomes[0].stale is True


def test_sync_metrics_snapshots_releases_lock_on_success(monkeypatch):
    released: list[tuple[str, str | None]] = []

    monkeypatch.setattr(
        "analytics.tasks._acquire_snapshot_sync_lock",
        lambda **_kwargs: "lock-token",
    )
    monkeypatch.setattr(
        "analytics.tasks._release_snapshot_sync_lock",
        lambda **kwargs: released.append((kwargs["lock_key"], kwargs["token"])),
    )
    monkeypatch.setattr("analytics.tasks.generate_snapshots_for_tenants", lambda tenant_ids=None: [])

    result = sync_metrics_snapshots.run(tenant_ids=["tenant-a"])

    assert result["processed"] == 0
    assert released
    assert released[0][1] == "lock-token"


def test_ai_daily_summary_retries_with_backoff_reason(monkeypatch):
    recorded: dict[str, object] = {}

    def fake_generate(tenant_ids=None):  # noqa: ANN001
        raise RuntimeError("daily summary boom")

    def fake_retry(self, *, exc=None, base_delay=None, max_delay=None, reason=None):  # noqa: ANN001
        recorded["exc"] = exc
        recorded["base_delay"] = base_delay
        recorded["max_delay"] = max_delay
        recorded["reason"] = reason
        raise RetryCalled

    monkeypatch.setattr("analytics.tasks.generate_daily_summaries_for_tenants", fake_generate)
    monkeypatch.setattr(BaseAdInsightsTask, "retry_with_backoff", fake_retry, raising=False)

    observed: list[tuple[str, str, float | None]] = []

    def fake_observe(task_name, status, duration_seconds):  # noqa: ANN001
        observed.append((task_name, status, duration_seconds))

    monkeypatch.setattr("analytics.tasks.observe_task", fake_observe)

    with pytest.raises(RetryCalled):
        ai_daily_summary.run(tenant_ids=["tenant-a"])

    assert recorded["base_delay"] == 60
    assert recorded["max_delay"] == 900
    assert recorded["reason"] == DAILY_SUMMARY_FAILURE_REASON_GENERATION
    assert observed
    assert observed[0][1] == "failure"


def test_evaluate_snapshot_freshness_thresholds():
    now = timezone.now()
    stale, age_seconds = evaluate_snapshot_freshness(
        generated_at=now - timedelta(seconds=SNAPSHOT_STALE_TTL_SECONDS + 1),
        now=now,
    )
    assert stale is True
    assert age_seconds > SNAPSHOT_STALE_TTL_SECONDS

    fresh, fresh_age_seconds = evaluate_snapshot_freshness(
        generated_at=now - timedelta(seconds=SNAPSHOT_STALE_TTL_SECONDS - 1),
        now=now,
    )
    assert fresh is False
    assert 0 <= fresh_age_seconds < SNAPSHOT_STALE_TTL_SECONDS


def test_retry_analytics_task_legacy_helper_records_reason_metric():
    reset_metrics(registries=[CELERY_TASK_RETRY_TOTAL])

    class LegacyTask:
        name = "analytics.legacy.task"

        def __init__(self):
            self.called = None

        def retry_with_backoff(self, *, exc=None, base_delay=None, max_delay=None):  # noqa: ANN001
            self.called = {"exc": exc, "base_delay": base_delay, "max_delay": max_delay}
            raise RetryCalled

    task = LegacyTask()
    with pytest.raises(RetryCalled):
        _retry_analytics_task(
            task,
            exc=RuntimeError("boom"),
            reason="analytics_legacy_reason",
            base_delay=10,
            max_delay=20,
        )

    assert isinstance(task.called["exc"], RuntimeError)
    retry_sample = next(
        sample
        for sample in CELERY_TASK_RETRY_TOTAL.collect()[0].samples
        if sample.name == "celery_task_retries_total"
        and sample.labels == {"task_name": "analytics.legacy.task", "reason": "analytics_legacy_reason"}
    )
    assert retry_sample.value == 1


def test_retry_analytics_task_without_helper_records_reason_metric():
    reset_metrics(registries=[CELERY_TASK_RETRY_TOTAL])

    class RetryOnlyTask:
        name = "analytics.retry.only"
        default_retry_delay = 25

        def __init__(self):
            self.called = None

        def retry(self, exc=None, countdown=None):  # noqa: ANN001
            self.called = {"exc": exc, "countdown": countdown}
            raise RetryCalled

    task = RetryOnlyTask()
    with pytest.raises(RetryCalled):
        _retry_analytics_task(
            task,
            exc=RuntimeError("boom"),
            reason="analytics_retry_fallback",
            base_delay=40,
        )

    assert isinstance(task.called["exc"], RuntimeError)
    assert task.called["countdown"] == 40
    retry_sample = next(
        sample
        for sample in CELERY_TASK_RETRY_TOTAL.collect()[0].samples
        if sample.name == "celery_task_retries_total"
        and sample.labels == {"task_name": "analytics.retry.only", "reason": "analytics_retry_fallback"}
    )
    assert retry_sample.value == 1
