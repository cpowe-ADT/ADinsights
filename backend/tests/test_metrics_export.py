from __future__ import annotations

import csv
from datetime import timedelta
from io import StringIO

import pytest
from django.db import connection
from django.utils import timezone

from analytics.views import METRIC_EXPORT_HEADERS


def _read_streaming_body(response) -> list[list[str]]:
    chunks = []
    for piece in response.streaming_content:
        if isinstance(piece, bytes):
            chunks.append(piece.decode("utf-8"))
        else:
            chunks.append(piece)
    csv_text = "".join(chunks)
    return list(csv.reader(StringIO(csv_text)))


def _create_vw_campaign_daily():
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS vw_campaign_daily")
        cursor.execute(
            """
            CREATE TABLE vw_campaign_daily (
                date_day TEXT,
                tenant_id TEXT,
                source_platform TEXT,
                campaign_name TEXT,
                parish_name TEXT,
                impressions INTEGER,
                clicks INTEGER,
                spend REAL,
                conversions INTEGER,
                roas REAL
            )
            """
        )


@pytest.mark.django_db
def test_metrics_export_streams_filtered_rows(api_client, user):
    api_client.force_authenticate(user=user)
    _create_vw_campaign_daily()

    today = timezone.now().date()
    start = (today - timedelta(days=7)).isoformat()
    end = today.isoformat()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO vw_campaign_daily
            (date_day, tenant_id, source_platform, campaign_name, parish_name,
             impressions, clicks, spend, conversions, roas)
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                today.isoformat(),
                str(user.tenant_id),
                "Meta",
                "Kingston Awareness",
                "Kingston",
                1000,
                120,
                450.75,
                25,
                3.2,
            ),
        )
        # Noise row for a different tenant; should be filtered out.
        cursor.execute(
            """
            INSERT INTO vw_campaign_daily
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                today.isoformat(),
                "other-tenant",
                "Google",
                "Montego Bay Prospecting",
                "St James",
                500,
                40,
                200.0,
                5,
                1.5,
            ),
        )

    response = api_client.get(
        "/api/export/metrics.csv",
        {"start_date": start, "end_date": end},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert response["Content-Disposition"] == 'attachment; filename="metrics.csv"'

    rows = _read_streaming_body(response)
    assert rows[0] == METRIC_EXPORT_HEADERS
    # The remaining rows should only include the tenant's record.
    assert rows[1:] == [
        [
            today.isoformat(),
            "Meta",
            "Kingston Awareness",
            "Kingston",
            "1000",
            "120",
            "450.75",
            "25",
            "3.2",
        ]
    ]


@pytest.mark.django_db
def test_metrics_export_requires_authentication(api_client):
    response = api_client.get("/api/export/metrics.csv")

    assert response.status_code == 401
