from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone

import pytest
from django.db import connection
from django.utils import timezone

from accounts.models import AuditLog


ENDPOINT = "/api/dashboards/aggregate-snapshot/"


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _create_snapshot_view() -> None:
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


@pytest.fixture()
def aggregate_snapshot_rows():
    _create_snapshot_view()
    yield
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS vw_dashboard_aggregate_snapshot")


@pytest.mark.django_db
def test_aggregate_snapshot_requires_authentication(api_client):
    response = api_client.get(ENDPOINT)

    assert response.status_code == 401


@pytest.mark.django_db
def test_aggregate_snapshot_returns_tenant_scoped_payload(api_client, user, aggregate_snapshot_rows):
    api_client.force_authenticate(user=user)

    generated_at = timezone.now().isoformat()
    tenant_payload = {
        "campaign_metrics": {
            "summary": {
                "currency": "JMD",
                "totalSpend": 1250.55,
                "totalImpressions": 42000,
                "totalClicks": 3200,
                "totalConversions": 280,
                "averageRoas": 3.4,
            },
            "trend": [
                {"date": "2024-01-01", "spend": 100.0, "impressions": 3000, "clicks": 220, "conversions": 18},
                {"date": "2024-01-02", "spend": 150.0, "impressions": 3500, "clicks": 260, "conversions": 20},
            ],
            "rows": [
                {
                    "id": "cmp_1",
                    "name": "Kingston Awareness",
                    "platform": "Meta",
                    "status": "ACTIVE",
                    "parish": "Kingston",
                    "spend": 400.0,
                    "impressions": 10000,
                    "clicks": 800,
                    "conversions": 60,
                    "roas": 2.5,
                }
            ],
        },
        "creative_metrics": [
            {
                "id": "cr_1",
                "name": "Carousel",
                "campaignId": "cmp_1",
                "campaignName": "Kingston Awareness",
                "platform": "Meta",
                "parish": "Kingston",
                "spend": 200.0,
                "impressions": 6000,
                "clicks": 420,
                "conversions": 35,
                "roas": 3.1,
            }
        ],
        "budget_metrics": [
            {
                "id": "budget_1",
                "campaignName": "Kingston Awareness",
                "parishes": ["Kingston"],
                "monthlyBudget": 2000.0,
                "spendToDate": 1200.0,
                "projectedSpend": 2050.0,
                "pacingPercent": 1.02,
            }
        ],
        "parish_metrics": [
            {
                "parish": "Kingston",
                "spend": 400.0,
                "impressions": 10000,
                "clicks": 800,
                "conversions": 60,
                "roas": 2.5,
                "campaignCount": 3,
                "currency": "JMD",
            }
        ],
    }

    other_payload = dict(tenant_payload)
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO vw_dashboard_aggregate_snapshot (
                tenant_id,
                generated_at,
                campaign_metrics,
                creative_metrics,
                budget_metrics,
                parish_metrics
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(user.tenant_id),
                    generated_at,
                    json.dumps(tenant_payload["campaign_metrics"]),
                    json.dumps(tenant_payload["creative_metrics"]),
                    json.dumps(tenant_payload["budget_metrics"]),
                    json.dumps(tenant_payload["parish_metrics"]),
                ),
                (
                    "other-tenant",
                    datetime.now(dt_timezone.utc).isoformat(),
                    json.dumps(other_payload["campaign_metrics"]),
                    json.dumps(other_payload["creative_metrics"]),
                    json.dumps(other_payload["budget_metrics"]),
                    json.dumps(other_payload["parish_metrics"]),
                ),
            ],
        )

    response = api_client.get(ENDPOINT)

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == str(user.tenant_id)
    assert _parse_iso(payload["generated_at"]) == _parse_iso(generated_at)

    metrics = payload["metrics"]
    assert metrics["campaign_metrics"]["summary"]["totalSpend"] == pytest.approx(1250.55)
    assert metrics["campaign_metrics"]["rows"][0]["id"] == "cmp_1"
    assert metrics["creative_metrics"][0]["campaignId"] == "cmp_1"
    assert metrics["budget_metrics"][0]["monthlyBudget"] == pytest.approx(2000.0)
    assert metrics["parish_metrics"][0]["parish"] == "Kingston"


@pytest.mark.django_db
def test_aggregate_snapshot_emits_audit_log(api_client, user, aggregate_snapshot_rows):
    api_client.force_authenticate(user=user)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO vw_dashboard_aggregate_snapshot (
                tenant_id,
                generated_at,
                campaign_metrics,
                creative_metrics,
                budget_metrics,
                parish_metrics
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(user.tenant_id),
                timezone.now().isoformat(),
                json.dumps(
                    {
                        "summary": {
                            "currency": "JMD",
                            "totalSpend": 0,
                            "totalImpressions": 0,
                            "totalClicks": 0,
                            "totalConversions": 0,
                            "averageRoas": 0,
                        },
                        "trend": [],
                        "rows": [],
                    }
                ),
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
            ),
        )

    response = api_client.get(ENDPOINT)
    assert response.status_code == 200

    log = AuditLog.all_objects.get(
        tenant=user.tenant,
        action="aggregate_snapshot_viewed",
        resource_type="dashboard",
    )
    assert log.user == user
    assert log.resource_id == str(user.tenant_id)
    assert log.metadata.get("path") == ENDPOINT
    assert "access_token" not in json.dumps(log.metadata)


@pytest.mark.django_db
def test_aggregate_snapshot_missing_view_returns_default(api_client, user):
    api_client.force_authenticate(user=user)

    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS vw_dashboard_aggregate_snapshot")

    response = api_client.get(ENDPOINT)

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == str(user.tenant_id)

    metrics = payload["metrics"]
    summary = metrics["campaign_metrics"]["summary"]
    assert summary["totalSpend"] == 0.0
    assert summary["totalImpressions"] == 0
    assert metrics["campaign_metrics"]["rows"] == []
