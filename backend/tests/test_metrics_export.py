from __future__ import annotations

import csv
from io import StringIO

import pytest

from analytics.exporters import FakeMetricsExportAdapter


def _read_streaming_body(response) -> list[list[str]]:
    chunks = []
    for piece in response.streaming_content:
        if isinstance(piece, bytes):
            chunks.append(piece.decode("utf-8"))
        else:
            chunks.append(piece)
    csv_text = "".join(chunks)
    return list(csv.reader(StringIO(csv_text)))


@pytest.mark.django_db
def test_metrics_export_returns_csv_attachment(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/export/metrics.csv")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert (
        response["Content-Disposition"]
        == 'attachment; filename="metrics.csv"'
    )

    rows = _read_streaming_body(response)
    adapter = FakeMetricsExportAdapter()
    expected_headers = list(adapter.get_headers())

    assert rows[0] == expected_headers
    assert rows[1:] == [
        [str(value) for value in row]
        for row in adapter.iter_rows()
    ]


@pytest.mark.django_db
def test_metrics_export_requires_authentication(api_client):
    response = api_client.get("/api/export/metrics.csv")

    assert response.status_code == 401
