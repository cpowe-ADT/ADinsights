"""Tests for the per-campaign extension + cache on ``GoogleAdsBudgetPacingView``.

Covers GA-A1 scope:
* Per-campaign rollup with best-effort budget name-match.
* Tenant isolation (no cross-tenant data leak).
* 15-minute cache with tenant-scoped keys.
* Empty-campaigns happy path.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.urls import reverse

from accounts.models import Role, Tenant, User, assign_role, seed_default_roles
from integrations.models import CampaignBudget, GoogleAdsSdkCampaignDaily


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _make_daily_row(
    tenant,
    *,
    customer_id: str = "1234567890",
    campaign_id: str,
    campaign_name: str,
    date_day: date,
    cost_micros: int,
) -> GoogleAdsSdkCampaignDaily:
    return GoogleAdsSdkCampaignDaily.objects.create(
        tenant=tenant,
        customer_id=customer_id,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        campaign_status="ENABLED",
        advertising_channel_type="SEARCH",
        date_day=date_day,
        currency_code="USD",
        impressions=1000,
        clicks=100,
        conversions=Decimal("10"),
        conversions_value=Decimal("500"),
        cost_micros=cost_micros,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_pacing_returns_campaigns_array(api_client, user, tenant):
    _make_daily_row(
        tenant,
        campaign_id="1001",
        campaign_name="Brand Always-On",
        date_day=date(2026, 4, 10),
        cost_micros=2_800_000_000,
    )
    _make_daily_row(
        tenant,
        campaign_id="1002",
        campaign_name="Promo Push",
        date_day=date(2026, 4, 10),
        cost_micros=350_000_000,
    )
    CampaignBudget.objects.create(
        tenant=tenant,
        name="Brand Always-On",
        monthly_target=Decimal("5000.00"),
        currency="USD",
        is_active=True,
    )

    _authenticate(api_client, user)
    response = api_client.get(
        reverse("google-ads-budgets-pacing"),
        {"start_date": "2026-04-01", "end_date": "2026-04-15"},
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "campaigns" in body
    assert len(body["campaigns"]) == 2
    by_name = {row["campaign_name"]: row for row in body["campaigns"]}
    matched = by_name["Brand Always-On"]
    assert matched["budget_amount"] == 5000.0
    assert matched["pace_pct"] is not None
    assert matched["variance"] is not None
    assert matched["spend_mtd"] == 2800.0
    unmatched = by_name["Promo Push"]
    assert unmatched["budget_amount"] is None
    assert unmatched["pace_pct"] is None
    assert unmatched["variance"] is None
    assert unmatched["projected_eom"] is not None

    assert body["cache"]["served_from_cache"] is False
    assert body["cache"]["ttl_seconds"] == 900


@pytest.mark.django_db
def test_pacing_tenant_isolation(api_client, tenant):
    seed_default_roles()
    _make_daily_row(
        tenant,
        campaign_id="1001",
        campaign_name="Tenant A Campaign",
        date_day=date(2026, 4, 10),
        cost_micros=1_000_000_000,
    )

    tenant_b = Tenant.objects.create(name="Tenant B")
    user_b = User.objects.create_user(
        username="b@example.com",
        email="b@example.com",
        tenant=tenant_b,
        password="password123",
    )
    assign_role(user_b, Role.ADMIN)

    _authenticate(api_client, user_b)
    response = api_client.get(
        reverse("google-ads-budgets-pacing"),
        {"start_date": "2026-04-01", "end_date": "2026-04-15"},
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["campaigns"] == []
    assert body["spend_mtd"] == 0.0


@pytest.mark.django_db
def test_pacing_cache_hit(api_client, user, tenant):
    _make_daily_row(
        tenant,
        campaign_id="1001",
        campaign_name="Cached Campaign",
        date_day=date(2026, 4, 10),
        cost_micros=500_000_000,
    )

    _authenticate(api_client, user)
    url = reverse("google-ads-budgets-pacing")
    first = api_client.get(url, {"start_date": "2026-04-01", "end_date": "2026-04-15"})
    second = api_client.get(url, {"start_date": "2026-04-01", "end_date": "2026-04-15"})

    assert first.status_code == 200, first.content
    assert second.status_code == 200, second.content
    assert first.json()["cache"]["served_from_cache"] is False
    assert second.json()["cache"]["served_from_cache"] is True
    # Payload (minus cache block) should match.
    first_payload = {k: v for k, v in first.json().items() if k != "cache"}
    second_payload = {k: v for k, v in second.json().items() if k != "cache"}
    assert first_payload == second_payload


@pytest.mark.django_db
def test_pacing_cache_tenant_scoped(api_client, tenant):
    seed_default_roles()
    user_a = User.objects.create_user(
        username="a@example.com",
        email="a@example.com",
        tenant=tenant,
        password="password123",
    )
    assign_role(user_a, Role.ADMIN)
    _make_daily_row(
        tenant,
        campaign_id="1001",
        campaign_name="Tenant A Camp",
        date_day=date(2026, 4, 10),
        cost_micros=1_000_000_000,
    )

    tenant_b = Tenant.objects.create(name="Tenant B")
    user_b = User.objects.create_user(
        username="b@example.com",
        email="b@example.com",
        tenant=tenant_b,
        password="password123",
    )
    assign_role(user_b, Role.ADMIN)
    _make_daily_row(
        tenant_b,
        campaign_id="2001",
        campaign_name="Tenant B Camp",
        date_day=date(2026, 4, 10),
        cost_micros=2_000_000_000,
    )

    # Prime cache as tenant A
    _authenticate(api_client, user_a)
    response_a = api_client.get(
        reverse("google-ads-budgets-pacing"),
        {"start_date": "2026-04-01", "end_date": "2026-04-15"},
    )
    assert response_a.status_code == 200, response_a.content
    body_a = response_a.json()
    assert len(body_a["campaigns"]) == 1
    assert body_a["campaigns"][0]["campaign_name"] == "Tenant A Camp"

    # Tenant B must not see cached A result
    _authenticate(api_client, user_b)
    response_b = api_client.get(
        reverse("google-ads-budgets-pacing"),
        {"start_date": "2026-04-01", "end_date": "2026-04-15"},
    )
    assert response_b.status_code == 200, response_b.content
    body_b = response_b.json()
    assert len(body_b["campaigns"]) == 1
    assert body_b["campaigns"][0]["campaign_name"] == "Tenant B Camp"
    assert body_b["cache"]["served_from_cache"] is False


@pytest.mark.django_db
def test_pacing_empty_campaigns_when_no_data(api_client, user, tenant):
    _authenticate(api_client, user)
    response = api_client.get(
        reverse("google-ads-budgets-pacing"),
        {"start_date": "2026-04-01", "end_date": "2026-04-15"},
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["campaigns"] == []
    assert body["spend_mtd"] == 0.0
