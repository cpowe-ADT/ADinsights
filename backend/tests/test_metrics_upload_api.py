from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
import pytest

from analytics.models import TenantMetricsSnapshot


def _file(name: str, content: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


@pytest.mark.django_db
def test_upload_metrics_requires_campaign_csv(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.post("/api/uploads/metrics/")

    assert response.status_code == 400
    assert response.json()["detail"] == "campaign_csv file is required."


@pytest.mark.django_db
def test_upload_metrics_persists_snapshot(api_client, user, settings):
    settings.ENABLE_UPLOAD_ADAPTER = True
    api_client.force_authenticate(user=user)

    campaign_csv = "\n".join(
        [
            "date,campaign_id,campaign_name,platform,parish,spend,impressions,clicks,conversions",
            "2024-10-01,cmp-1,Launch,Meta,Kingston,120,12000,420,33",
            "2024-10-02,cmp-1,Launch,Meta,Kingston,80,8000,210,20",
        ]
    )

    response = api_client.post(
        "/api/uploads/metrics/",
        data={"campaign_csv": _file("campaign.csv", campaign_csv)},
        format="multipart",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["counts"]["campaign_rows"] == 2

    snapshot = TenantMetricsSnapshot.latest_for(tenant=user.tenant, source="upload")
    assert snapshot is not None

    combined = api_client.get("/api/metrics/combined/", {"source": "upload"})
    assert combined.status_code == 200
    combined_payload = combined.json()
    assert combined_payload["campaign"]["summary"]["totalSpend"] == 200
    assert combined_payload["parish"][0]["parish"] == "Kingston"


@pytest.mark.django_db
def test_upload_metrics_status_endpoint(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/uploads/metrics/")

    assert response.status_code == 200
    assert response.json()["has_upload"] is False
