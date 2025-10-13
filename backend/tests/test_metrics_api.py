from __future__ import annotations

from datetime import date

import analytics.views
import pytest
from django.db import connection

from accounts.models import Tenant


@pytest.fixture(autouse=True)
def metrics_view(db):
    """Ensure the vw_campaign_daily view exists for tests."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists vw_campaign_daily (
                tenant_id varchar(36) not null,
                date_day date not null,
                source_platform varchar(64) not null,
                campaign_name varchar(255) not null,
                parish_name varchar(255),
                impressions integer not null,
                clicks integer not null,
                spend real not null,
                conversions integer not null,
                roas real not null
            )
            """
        )
    yield
    with connection.cursor() as cursor:
        cursor.execute("delete from vw_campaign_daily")


def _insert_metric_row(
    tenant_id: str,
    day: date,
    platform: str,
    campaign: str,
    parish: str | None,
    impressions: int,
    clicks: int,
    spend: float,
    conversions: int,
    roas: float,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into vw_campaign_daily (
                tenant_id,
                date_day,
                source_platform,
                campaign_name,
                parish_name,
                impressions,
                clicks,
                spend,
                conversions,
                roas
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                tenant_id,
                day.isoformat(),
                platform,
                campaign,
                parish,
                impressions,
                clicks,
                spend,
                conversions,
                roas,
            ],
        )


@pytest.mark.django_db
def test_metrics_happy_path_returns_ordered_rows(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")

    _insert_metric_row(
        str(tenant.id),
        date(2024, 1, 2),
        "Meta",
        "Campaign B",
        "Kingston",
        200,
        20,
        120.5,
        15,
        2.4,
    )
    _insert_metric_row(
        str(tenant.id),
        date(2024, 1, 1),
        "Google",
        "Campaign A",
        "St. Andrew",
        150,
        10,
        80.0,
        8,
        1.8,
    )
    _insert_metric_row(
        str(other_tenant.id),
        date(2024, 1, 3),
        "Meta",
        "Other Tenant Campaign",
        None,
        999,
        99,
        999.0,
        99,
        9.9,
    )

    api_client.force_authenticate(user=user)
    response = api_client.get(
        "/api/metrics/",
        {"start_date": "2024-01-01", "end_date": "2024-01-31"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    results = payload["results"]
    first, second = results
    assert first["date"] == "2024-01-02"
    assert second["date"] == "2024-01-01"
    assert list(first.keys()) == [
        "date",
        "platform",
        "campaign",
        "parish",
        "impressions",
        "clicks",
        "spend",
        "conversions",
        "roas",
    ]
    assert {row["campaign"] for row in results} == {"Campaign A", "Campaign B"}


@pytest.mark.django_db
def test_metrics_requires_authentication(api_client):
    response = api_client.get(
        "/api/metrics/",
        {"start_date": "2024-01-01", "end_date": "2024-01-31"},
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_metrics_invalid_date_range_short_circuits(api_client, user, monkeypatch):
    api_client.force_authenticate(user=user)

    def fail_cursor(*args, **kwargs):  # pragma: no cover - exercised when misused
        pytest.fail("Database cursor should not be invoked for invalid params")

    monkeypatch.setattr(analytics.views.connection, "cursor", fail_cursor)

    response = api_client.get(
        "/api/metrics/",
        {"start_date": "2024-02-01", "end_date": "2024-01-01"},
    )

    assert response.status_code == 400
    assert response.json()["non_field_errors"] == [
        "start_date must be before or equal to end_date."
    ]
    monkeypatch.undo()


@pytest.mark.django_db
def test_metrics_isolated_by_tenant(api_client, tenant, user):
    another_tenant = Tenant.objects.create(name="Neighbor Tenant")

    _insert_metric_row(
        str(tenant.id),
        date(2024, 1, 5),
        "Meta",
        "Tenant Campaign",
        None,
        100,
        12,
        45.0,
        6,
        1.2,
    )
    _insert_metric_row(
        str(another_tenant.id),
        date(2024, 1, 5),
        "Meta",
        "Neighbor Campaign",
        None,
        200,
        22,
        95.0,
        9,
        1.9,
    )

    api_client.force_authenticate(user=user)
    response = api_client.get(
        "/api/metrics/",
        {"start_date": "2024-01-01", "end_date": "2024-01-31"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    results = payload["results"]
    assert len(results) == 1
    assert results[0]["campaign"] == "Tenant Campaign"
