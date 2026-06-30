"""Sprint 10 polish: ``platforms=`` without ``client_id`` scopes the payload.

Exercises the full HTTP round-trip through the combined metrics view so we
pin end-to-end behaviour: the Meta-only / Google-only dashboard pages emit
``?platforms=meta_ads`` (or ``google_ads``) with no ``client_id`` set, and
the backend must narrow the payload accordingly instead of returning the
combined tenant data. This complements ``test_platform_only_scoping.py``
(which unit-tests the resolver in isolation).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from adapters.meta_direct import MetaDirectAdapter
from analytics.models import (
    Ad,
    AdAccount,
    AdSet,
    Campaign,
    RawPerformanceRecord,
)


@pytest.fixture
def enable_meta_direct_adapter(settings):
    settings.ENABLE_META_DIRECT_ADAPTER = True
    settings.ENABLE_FAKE_ADAPTER = False
    settings.ENABLE_DEMO_ADAPTER = False


def _seed_meta_account(tenant, *, external_id: str, spend: Decimal) -> AdAccount:
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id=external_id,
        account_id=external_id.replace("act_", ""),
        name=f"Account {external_id}",
        currency="USD",
        status="ACTIVE",
    )
    campaign = Campaign.objects.create(
        tenant=tenant,
        ad_account=account,
        external_id=f"cmp-{external_id}",
        name=f"Campaign {external_id}",
        platform="meta",
        account_external_id=external_id,
        status="ACTIVE",
        objective="OUTCOME_AWARENESS",
        currency="USD",
    )
    adset = AdSet.objects.create(
        tenant=tenant,
        campaign=campaign,
        external_id=f"adset-{external_id}",
        name=f"Ad set {external_id}",
        status="ACTIVE",
        bid_strategy="LOWEST_COST_WITHOUT_CAP",
        daily_budget=100,
    )
    ad = Ad.objects.create(
        tenant=tenant,
        adset=adset,
        external_id=f"ad-{external_id}",
        name=f"Creative {external_id}",
        status="ACTIVE",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        campaign=campaign,
        adset=adset,
        ad=ad,
        external_id=ad.external_id,
        source="meta",
        level="ad",
        date=date(2026, 4, 3),
        impressions=1000,
        reach=800,
        clicks=50,
        spend=spend,
        cpc=Decimal("1.5"),
        cpm=Decimal("75"),
        conversions=6,
        currency="USD",
    )
    return account


@pytest.mark.django_db
def test_platforms_meta_only_sums_only_meta_accounts(
    api_client, user, enable_meta_direct_adapter
):
    """Meta-only workspace sends ``platforms=meta_ads`` with no client_id.
    Backend should include every tenant Meta account's spend."""

    api_client.force_authenticate(user=user)
    _seed_meta_account(user.tenant, external_id="act_111", spend=Decimal("25"))
    _seed_meta_account(user.tenant, external_id="act_222", spend=Decimal("75"))

    response = api_client.get(
        "/api/metrics/combined/",
        {"source": MetaDirectAdapter.key, "platforms": "meta_ads"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"]["summary"]["totalSpend"] == pytest.approx(100.0)

    # New resolution metadata surfaced for platform-only scope.
    meta = payload.get("client_resolution")
    assert meta is not None
    assert meta["scope"] == "platforms_only"
    assert meta["client_id"] is None
    # Header reflects platform scope, not client scope.
    assert response["X-Adinsights-Resolved-Via"] == "platforms:meta_ads"


@pytest.mark.django_db
def test_platforms_google_only_excludes_meta_on_meta_direct(
    api_client, user, enable_meta_direct_adapter
):
    """If the user toggles to Google on a meta_direct-backed tenant, the
    payload should come back empty — meta_direct only serves Meta data so
    a Google-only scope must yield zero Meta rows, not leak them through."""

    api_client.force_authenticate(user=user)
    _seed_meta_account(user.tenant, external_id="act_111", spend=Decimal("25"))

    response = api_client.get(
        "/api/metrics/combined/",
        {"source": MetaDirectAdapter.key, "platforms": "google_ads"},
    )
    assert response.status_code == 200
    payload = response.json()
    # Zero Meta spend — scoping told the adapter "Meta accounts = []".
    assert payload["campaign"]["summary"]["totalSpend"] == 0
    meta = payload["client_resolution"]
    assert meta["scope"] == "platforms_only"
    # Tenant has no Google accounts configured → registry's enabled set is
    # empty after intersecting the request's ``google_ads`` with the
    # configured set ``{meta_ads}``. The header reflects the effective set,
    # not the requested one, so it's intentionally empty here.
    assert response["X-Adinsights-Resolved-Via"] == "platforms:"


@pytest.mark.django_db
def test_platforms_omitted_returns_unscoped_payload(
    api_client, user, enable_meta_direct_adapter
):
    """No ``platforms=`` → no scope, no ``client_resolution`` body, and no
    resolved-via header — legacy behaviour is preserved."""

    api_client.force_authenticate(user=user)
    _seed_meta_account(user.tenant, external_id="act_111", spend=Decimal("25"))

    response = api_client.get(
        "/api/metrics/combined/",
        {"source": MetaDirectAdapter.key},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"]["summary"]["totalSpend"] == pytest.approx(25.0)
    assert "client_resolution" not in payload
    assert "X-Adinsights-Resolved-Via" not in response


@pytest.mark.django_db
def test_platforms_with_account_id_keeps_account_filter_authoritative(
    api_client, user, enable_meta_direct_adapter
):
    """When the caller already passed ``account_id``, the platforms filter
    must not widen the result past that single account. The resolver
    short-circuits to "no platform scope" in this case so the narrower
    account filter wins."""

    api_client.force_authenticate(user=user)
    _seed_meta_account(user.tenant, external_id="act_111", spend=Decimal("25"))
    _seed_meta_account(user.tenant, external_id="act_222", spend=Decimal("75"))

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": MetaDirectAdapter.key,
            "platforms": "meta_ads",
            "account_id": "act_111",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # Only act_111 contributes — account_id was preserved.
    assert payload["campaign"]["summary"]["totalSpend"] == pytest.approx(25.0)
    # No client_resolution body since scope was short-circuited.
    assert "client_resolution" not in payload
