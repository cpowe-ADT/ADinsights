from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import Tenant
from analytics.models import TenantMetricsSnapshot
from analytics.tasks import generate_snapshots_for_tenants, sync_metrics_snapshots
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

    def fake_generate(tenant_ids=None):  # noqa: ANN001
        raise RuntimeError("boom")

    def fake_retry(self, *, exc=None, base_delay=None, max_delay=None):  # noqa: ANN001
        recorded["exc"] = exc
        recorded["base_delay"] = base_delay
        recorded["max_delay"] = max_delay
        raise RetryCalled

    monkeypatch.setattr("analytics.tasks.generate_snapshots_for_tenants", fake_generate)
    monkeypatch.setattr(BaseAdInsightsTask, "retry_with_backoff", fake_retry, raising=False)

    observed: list[tuple[str, str, float | None]] = []

    def fake_observe(task_name, status, duration_seconds):  # noqa: ANN001
        observed.append((task_name, status, duration_seconds))

    monkeypatch.setattr("analytics.tasks.observe_task", fake_observe)

    with pytest.raises(RetryCalled):
        sync_metrics_snapshots.run(tenant_ids=["tenant-a"])

    assert recorded["base_delay"] == 60
    assert recorded["max_delay"] == 900
    assert observed
    assert observed[0][1] == "failure"
