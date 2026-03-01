from __future__ import annotations

from datetime import date
from decimal import Decimal

from rest_framework.test import APIClient

from analytics.models import GoogleAdsExportJob, GoogleAdsSavedView
from integrations.models import (
    GoogleAdsAccountAssignment,
    GoogleAdsSdkCampaignDaily,
)


def _seed_campaign_rows(*, tenant, customer_id: str = "1234567890") -> None:
    GoogleAdsSdkCampaignDaily.objects.create(
        tenant=tenant,
        customer_id=customer_id,
        campaign_id="1001",
        campaign_name="Brand Search",
        campaign_status="ENABLED",
        advertising_channel_type="SEARCH",
        date_day=date(2026, 2, 20),
        currency_code="USD",
        impressions=1000,
        clicks=100,
        conversions=Decimal("10"),
        conversions_value=Decimal("500"),
        cost_micros=200_000_000,
    )
    GoogleAdsSdkCampaignDaily.objects.create(
        tenant=tenant,
        customer_id=customer_id,
        campaign_id="1002",
        campaign_name="PMax Core",
        campaign_status="ENABLED",
        advertising_channel_type="PERFORMANCE_MAX",
        date_day=date(2026, 2, 20),
        currency_code="USD",
        impressions=500,
        clicks=40,
        conversions=Decimal("4"),
        conversions_value=Decimal("180"),
        cost_micros=80_000_000,
    )


def _assign_user_to_customer(*, user, customer_id: str = "1234567890") -> None:
    GoogleAdsAccountAssignment.objects.create(
        tenant=user.tenant,
        user=user,
        customer_id=customer_id,
        access_level=GoogleAdsAccountAssignment.ACCESS_ANALYST,
        is_active=True,
    )


def test_google_ads_executive_endpoint_returns_metrics(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    _seed_campaign_rows(tenant=user.tenant)
    _assign_user_to_customer(user=user)

    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {"start_date": "2026-02-20", "end_date": "2026-02-20"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["spend"] == 280.0
    assert payload["metrics"]["clicks"] == 140.0
    assert payload["metrics"]["conversions"] == 14.0
    assert payload["source_engine"] in {"sdk", "airbyte_fallback"}


def test_google_ads_workspace_summary_endpoint_returns_workspace_payload(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    _seed_campaign_rows(tenant=user.tenant)
    _assign_user_to_customer(user=user)

    response = api_client.get(
        "/api/analytics/google-ads/workspace/summary/",
        {"start_date": "2026-02-20", "end_date": "2026-02-20"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["spend"] == 280.0
    assert "alerts_summary" in payload
    assert "governance_summary" in payload
    assert "top_insights" in payload


def test_google_ads_campaigns_endpoint_paginates(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    _seed_campaign_rows(tenant=user.tenant)
    _assign_user_to_customer(user=user)

    response = api_client.get(
        "/api/analytics/google-ads/campaigns/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "page_size": 1,
            "page": 1,
            "sort": "-spend",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert len(payload["results"]) == 1


def test_google_ads_saved_views_crud(api_client: APIClient, user):
    api_client.force_authenticate(user=user)

    create_response = api_client.post(
        "/api/analytics/google-ads/saved-views/",
        {
            "name": "Weekly Executive",
            "description": "Default weekly executive filters",
            "filters": {"channel_type": "SEARCH"},
            "columns": ["spend", "clicks", "roas"],
            "is_shared": True,
        },
        format="json",
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    list_response = api_client.get("/api/analytics/google-ads/saved-views/")
    assert list_response.status_code == 200
    assert any(row["id"] == created_id for row in list_response.json())

    assert GoogleAdsSavedView.objects.filter(id=created_id, tenant=user.tenant).exists()


def test_google_ads_exports_create_and_status(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    _seed_campaign_rows(tenant=user.tenant)
    _assign_user_to_customer(user=user)

    create_response = api_client.post(
        "/api/analytics/google-ads/exports/",
        {
            "name": "Test Export",
            "export_format": "csv",
            "filters": {"start_date": "2026-02-20", "end_date": "2026-02-20"},
        },
        format="json",
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["status"] in {GoogleAdsExportJob.STATUS_COMPLETED, GoogleAdsExportJob.STATUS_FAILED}

    status_response = api_client.get(f"/api/analytics/google-ads/exports/{payload['id']}/")
    assert status_response.status_code == 200
