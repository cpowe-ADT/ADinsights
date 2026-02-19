from __future__ import annotations
from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import Tenant
from analytics.models import Ad, AdAccount, AdSet, Campaign, RawPerformanceRecord


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.username, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_meta_accounts_endpoint_tenant_scoped(api_client, user):
    _authenticate(api_client, user)
    own = AdAccount.objects.create(
        tenant=user.tenant,
        external_id="act_123",
        account_id="123",
        name="Primary Account",
        status="1",
    )
    other_tenant = Tenant.objects.create(name="Other Tenant")
    AdAccount.all_objects.create(
        tenant=other_tenant,
        external_id="act_999",
        account_id="999",
        name="Other Account",
        status="1",
    )

    response = api_client.get(reverse("meta-accounts"), {"search": "Primary"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["external_id"] == own.external_id


@pytest.mark.django_db
def test_meta_campaigns_endpoint_filters_account_status_and_search(api_client, user):
    _authenticate(api_client, user)
    account = AdAccount.objects.create(
        tenant=user.tenant,
        external_id="act_123",
        account_id="123",
        name="Primary Account",
    )
    Campaign.objects.create(
        tenant=user.tenant,
        ad_account=account,
        external_id="cmp-1",
        name="Alpha Campaign",
        platform="meta",
        account_external_id="act_123",
        status="ACTIVE",
    )
    Campaign.objects.create(
        tenant=user.tenant,
        ad_account=account,
        external_id="cmp-2",
        name="Beta Campaign",
        platform="meta",
        account_external_id="act_123",
        status="PAUSED",
    )

    response = api_client.get(
        reverse("meta-campaigns"),
        {"account_id": "123", "status": "ACTIVE", "search": "Alpha"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["external_id"] == "cmp-1"


@pytest.mark.django_db
def test_meta_adsets_and_ads_endpoint_filters_foreign_keys(api_client, user):
    _authenticate(api_client, user)
    account = AdAccount.objects.create(
        tenant=user.tenant,
        external_id="act_123",
        account_id="123",
    )
    campaign = Campaign.objects.create(
        tenant=user.tenant,
        ad_account=account,
        external_id="cmp-1",
        name="Campaign One",
        platform="meta",
        account_external_id="act_123",
    )
    adset = AdSet.objects.create(
        tenant=user.tenant,
        campaign=campaign,
        external_id="adset-1",
        name="AdSet One",
        status="ACTIVE",
    )
    Ad.objects.create(
        tenant=user.tenant,
        adset=adset,
        external_id="ad-1",
        name="Ad One",
        status="ACTIVE",
    )
    Ad.objects.create(
        tenant=user.tenant,
        adset=adset,
        external_id="ad-2",
        name="Ad Two",
        status="PAUSED",
    )

    adsets_response = api_client.get(reverse("meta-adsets"), {"campaign_id": "cmp-1"})
    assert adsets_response.status_code == 200
    assert adsets_response.json()["count"] == 1

    ads_response = api_client.get(reverse("meta-ads"), {"adset_id": "adset-1", "status": "ACTIVE"})
    assert ads_response.status_code == 200
    payload = ads_response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["external_id"] == "ad-1"


@pytest.mark.django_db
def test_meta_insights_endpoint_supports_level_and_date_window(api_client, user):
    _authenticate(api_client, user)
    account = AdAccount.objects.create(
        tenant=user.tenant,
        external_id="act_123",
        account_id="123",
        currency="USD",
    )
    campaign = Campaign.objects.create(
        tenant=user.tenant,
        ad_account=account,
        external_id="cmp-1",
        name="Campaign One",
        platform="meta",
        account_external_id="act_123",
        status="ACTIVE",
    )
    adset = AdSet.objects.create(
        tenant=user.tenant,
        campaign=campaign,
        external_id="adset-1",
        name="AdSet One",
        status="ACTIVE",
    )
    ad = Ad.objects.create(
        tenant=user.tenant,
        adset=adset,
        external_id="ad-1",
        name="Ad One",
        status="ACTIVE",
    )
    RawPerformanceRecord.objects.create(
        tenant=user.tenant,
        ad_account=account,
        external_id="ad-1",
        source="meta",
        level="ad",
        date="2026-01-30",
        campaign=campaign,
        adset=adset,
        ad=ad,
        impressions=1000,
        reach=900,
        clicks=35,
        spend=Decimal("17.500000"),
        cpc=Decimal("0.500000"),
        cpm=Decimal("17.500000"),
        actions=[{"action_type": "purchase", "value": "3"}],
        conversions=3,
    )
    RawPerformanceRecord.objects.create(
        tenant=user.tenant,
        ad_account=account,
        external_id="cmp-1",
        source="meta",
        level="campaign",
        date="2026-01-30",
        campaign=campaign,
        impressions=1500,
    )

    response = api_client.get(
        reverse("meta-insights"),
        {
            "account_id": "act_123",
            "level": "ad",
            "since": "2026-01-01",
            "until": "2026-01-31",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    row = payload["results"][0]
    assert row["external_id"] == "ad-1"
    assert row["reach"] == 900
    assert row["actions"][0]["action_type"] == "purchase"


@pytest.mark.django_db
def test_meta_insights_endpoint_validates_date_bounds(api_client, user):
    _authenticate(api_client, user)
    response = api_client.get(
        reverse("meta-insights"),
        {"since": "2026-02-10", "until": "2026-02-01"},
    )
    assert response.status_code == 400
    assert "until" in response.json()
