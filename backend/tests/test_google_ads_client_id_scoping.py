"""Sprint 4: Google Ads analytics endpoints accept ``client_id``.

When ``client_id`` is passed, the response must scope to the Client's Google
customer_ids (MCC-expanded), surface a ``client_resolution`` object in the
body, and set the ``X-Adinsights-Resolved-Via`` header.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from rest_framework.test import APIClient

from integrations.models import (
    Client as IntegrationsClient,
    ClientPlatformAccount,
    GoogleAdsAccountAssignment,
    GoogleAdsAccountMapping,
    GoogleAdsSdkCampaignDaily,
)


def _seed_row(*, tenant, customer_id: str, campaign_id: str, spend_micros: int) -> None:
    GoogleAdsSdkCampaignDaily.objects.create(
        tenant=tenant,
        customer_id=customer_id,
        campaign_id=campaign_id,
        campaign_name=f"C-{campaign_id}",
        campaign_status="ENABLED",
        advertising_channel_type="SEARCH",
        date_day=date(2026, 2, 20),
        currency_code="USD",
        impressions=1000,
        clicks=100,
        conversions=Decimal("10"),
        conversions_value=Decimal("500"),
        cost_micros=spend_micros,
    )


def _admin(user):
    # Simplest path to admin: superuser. The views short-circuit _is_admin().
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])


def test_client_id_union_of_two_google_customer_ids(api_client: APIClient, user):
    """A client with two Google customer_ids returns the union spend."""

    api_client.force_authenticate(user=user)
    _admin(user)

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
        external_id="111",
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
        external_id="222",
    )

    # Seed spend: client has 111 + 222, plus an unrelated 999 that must NOT leak in.
    _seed_row(tenant=user.tenant, customer_id="111", campaign_id="1001", spend_micros=200_000_000)
    _seed_row(tenant=user.tenant, customer_id="222", campaign_id="1002", spend_micros=50_000_000)
    _seed_row(tenant=user.tenant, customer_id="999", campaign_id="1003", spend_micros=900_000_000)

    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "client_id": str(client.id),
        },
    )
    assert response.status_code == 200
    body = response.json()
    # 200 + 50 = 250 (unrelated 900 stays out)
    assert body["metrics"]["spend"] == 250.0
    meta = body["client_resolution"]
    assert meta["client_id"] == str(client.id)
    assert set(meta["google_customer_ids"]) == {"111", "222"}
    assert meta["reason"] is None
    assert response["X-Adinsights-Resolved-Via"] == f"client:{client.id}"


def test_client_id_empty_when_no_google_accounts(api_client: APIClient, user):
    """A client with zero Google accounts → empty payload + reason."""

    api_client.force_authenticate(user=user)
    _admin(user)

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="NoGoogle", slug="nogoogle"
    )
    # No ClientPlatformAccount rows at all.
    _seed_row(tenant=user.tenant, customer_id="111", campaign_id="1001", spend_micros=200_000_000)

    response = api_client.get(
        "/api/analytics/google-ads/campaigns/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "client_id": str(client.id),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["client_resolution"]["reason"] == "no_google_accounts_for_client"
    assert body["client_resolution"]["google_customer_ids"] == []


def test_client_id_not_found_returns_empty(api_client: APIClient, user):
    """Unknown client_id (or cross-tenant) is surfaced as client_not_found."""

    api_client.force_authenticate(user=user)
    _admin(user)

    _seed_row(tenant=user.tenant, customer_id="111", campaign_id="1001", spend_micros=200_000_000)

    bogus_client_id = "00000000-0000-0000-0000-000000000000"
    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "client_id": bogus_client_id,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["spend"] == 0.0
    assert body["client_resolution"]["reason"] == "client_not_found"


def test_client_id_plus_customer_id_intersection_wins(api_client: APIClient, user):
    """``client_id`` + ``customer_id``: only the intersection is returned."""

    api_client.force_authenticate(user=user)
    _admin(user)

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
        external_id="111",
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
        external_id="222",
    )
    _seed_row(tenant=user.tenant, customer_id="111", campaign_id="1001", spend_micros=200_000_000)
    _seed_row(tenant=user.tenant, customer_id="222", campaign_id="1002", spend_micros=50_000_000)

    # Narrow to just 111.
    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "client_id": str(client.id),
            "customer_id": "111",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["spend"] == 200.0
    assert body["client_resolution"]["reason"] == "client_plus_customer"


def test_client_id_customer_not_in_client_returns_empty(api_client: APIClient, user):
    """customer_id outside the client's set → empty intersection."""

    api_client.force_authenticate(user=user)
    _admin(user)

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
        external_id="111",
    )
    _seed_row(tenant=user.tenant, customer_id="999", campaign_id="1001", spend_micros=500_000_000)

    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "client_id": str(client.id),
            "customer_id": "999",  # not in the client
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["spend"] == 0.0
    assert body["client_resolution"]["reason"] == "customer_not_in_client"


def test_client_id_mcc_expansion(api_client: APIClient, user):
    """Linking an MCC expands transparently to its non-manager children."""

    api_client.force_authenticate(user=user)
    _admin(user)

    # MCC 500 manages 111 and 222. Client only has the MCC linked.
    GoogleAdsAccountMapping.all_objects.create(
        tenant=user.tenant,
        customer_id="500",
        customer_name="Parent MCC",
        is_manager=True,
    )
    GoogleAdsAccountMapping.all_objects.create(
        tenant=user.tenant,
        customer_id="111",
        customer_name="Child A",
        is_manager=False,
        manager_customer_id="500",
    )
    GoogleAdsAccountMapping.all_objects.create(
        tenant=user.tenant,
        customer_id="222",
        customer_name="Child B",
        is_manager=False,
        manager_customer_id="500",
    )

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
        external_id="500",  # link the MCC, not the children
    )

    _seed_row(tenant=user.tenant, customer_id="111", campaign_id="1001", spend_micros=200_000_000)
    _seed_row(tenant=user.tenant, customer_id="222", campaign_id="1002", spend_micros=50_000_000)

    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "client_id": str(client.id),
        },
    )
    assert response.status_code == 200
    body = response.json()
    # Spend across both children should show even though only the MCC was linked.
    assert body["metrics"]["spend"] == 250.0
    meta = body["client_resolution"]
    assert set(meta["google_customer_ids"]) == {"111", "222"}
    assert len(meta["mcc_expansions"]) == 1
    exp = meta["mcc_expansions"][0]
    assert exp["manager_customer_id"] == "500"
    assert set(exp["child_customer_ids"]) == {"111", "222"}


def test_client_id_preserves_tenant_isolation(api_client: APIClient, user):
    """A client owned by another tenant is invisible (returns client_not_found)."""

    from accounts.models import Tenant

    api_client.force_authenticate(user=user)
    _admin(user)

    other_tenant = Tenant.objects.create(name="Other")
    other_client = IntegrationsClient.all_objects.create(
        tenant=other_tenant, name="OtherCo", slug="otherco"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=other_tenant,
        client=other_client,
        platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
        external_id="111",
    )
    _seed_row(tenant=user.tenant, customer_id="111", campaign_id="1001", spend_micros=900_000_000)

    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {
            "start_date": "2026-02-20",
            "end_date": "2026-02-20",
            "client_id": str(other_client.id),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["spend"] == 0.0
    assert body["client_resolution"]["reason"] == "client_not_found"


def test_no_client_id_existing_behavior_unchanged(api_client: APIClient, user):
    """Omitting client_id must leave legacy behavior (customer_id filter) intact."""

    api_client.force_authenticate(user=user)
    GoogleAdsAccountAssignment.objects.create(
        tenant=user.tenant,
        user=user,
        customer_id="111",
        access_level=GoogleAdsAccountAssignment.ACCESS_ANALYST,
        is_active=True,
    )
    _seed_row(tenant=user.tenant, customer_id="111", campaign_id="1001", spend_micros=200_000_000)

    response = api_client.get(
        "/api/analytics/google-ads/executive/",
        {"start_date": "2026-02-20", "end_date": "2026-02-20"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["spend"] == 200.0
    # No resolution meta when no client was requested.
    assert "client_resolution" not in body
    assert "X-Adinsights-Resolved-Via" not in response
