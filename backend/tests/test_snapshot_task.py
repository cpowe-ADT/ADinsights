from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from accounts.models import Tenant
from analytics.models import TenantMetricsSnapshot
from analytics.tasks import generate_snapshots_for_tenants


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
