"""Tests for ``GoogleAdsChangeEventsView`` pagination (GA-B1).

Verifies the ``next_cursor`` key in the response payload — string when more
pages exist, ``None`` on the final page — and tenant isolation of paging.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, Tenant, User, assign_role, seed_default_roles
from integrations.models import GoogleAdsSdkChangeEvent


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _make_change_event(
    tenant,
    *,
    customer_id: str = "1234567890",
    fingerprint: str = "fp-1",
    offset_minutes: int = 0,
) -> GoogleAdsSdkChangeEvent:
    return GoogleAdsSdkChangeEvent.objects.create(
        tenant=tenant,
        customer_id=customer_id,
        event_fingerprint=fingerprint,
        change_date_time=timezone.now() - timedelta(minutes=offset_minutes),
        user_email="someone@example.com",
        client_type="GOOGLE_ADS_WEB_CLIENT",
        change_resource_type="CAMPAIGN",
        resource_change_operation="UPDATE",
        campaign_id="987654321",
        ad_group_id="",
        ad_id="",
        changed_fields=[],
        source_request_id="req-1",
    )


@pytest.mark.django_db
def test_changes_returns_next_cursor_when_more_pages(api_client, user, tenant):
    for i in range(3):
        _make_change_event(tenant, fingerprint=f"fp-{i}", offset_minutes=i)
    _authenticate(api_client, user)

    response = api_client.get(
        reverse("google-ads-change-events"),
        {"page": 1, "page_size": 2},
    )
    assert response.status_code == 200, response.content
    assert response.data["next_cursor"] == "2"
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_changes_next_cursor_null_on_last_page(api_client, user, tenant):
    for i in range(3):
        _make_change_event(tenant, fingerprint=f"fp-{i}", offset_minutes=i)
    _authenticate(api_client, user)

    response = api_client.get(
        reverse("google-ads-change-events"),
        {"page": 1, "page_size": 10},
    )
    assert response.status_code == 200, response.content
    assert response.data["next_cursor"] is None
    assert len(response.data["results"]) == 3


@pytest.mark.django_db
def test_changes_pagination_tenant_isolated(api_client, tenant):
    seed_default_roles()

    # Tenant A rows
    user_a = User.objects.create_user(
        username="a@example.com",
        email="a@example.com",
        tenant=tenant,
        password="password123",
    )
    assign_role(user_a, Role.ADMIN)
    _make_change_event(tenant, fingerprint="a-1", offset_minutes=0)
    _make_change_event(tenant, fingerprint="a-2", offset_minutes=1)

    # Tenant B rows
    other_tenant = Tenant.objects.create(name="Other Tenant")
    user_b = User.objects.create_user(
        username="b@example.com",
        email="b@example.com",
        tenant=other_tenant,
        password="password123",
    )
    assign_role(user_b, Role.ADMIN)
    _make_change_event(other_tenant, fingerprint="b-1", offset_minutes=0)
    _make_change_event(other_tenant, fingerprint="b-2", offset_minutes=1)

    # Tenant A sees only its own 2 rows
    _authenticate(api_client, user_a)
    resp_a = api_client.get(
        reverse("google-ads-change-events"),
        {"page": 1, "page_size": 50},
    )
    assert resp_a.status_code == 200, resp_a.content
    assert resp_a.data["count"] == 2
    assert len(resp_a.data["results"]) == 2

    # Tenant B sees only its own 2 rows
    _authenticate(api_client, user_b)
    resp_b = api_client.get(
        reverse("google-ads-change-events"),
        {"page": 1, "page_size": 50},
    )
    assert resp_b.status_code == 200, resp_b.content
    assert resp_b.data["count"] == 2
    assert len(resp_b.data["results"]) == 2
