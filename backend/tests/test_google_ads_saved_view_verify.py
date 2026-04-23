"""Tests for ``GoogleAdsSavedViewViewSet.verify`` action (GA-B2).

Verifies the saved-view drift-reconciliation report: unknown filter keys and
unknown columns surface as drift, canonical views show no drift, and
cross-tenant access returns 404.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Role, Tenant, User, assign_role, seed_default_roles
from analytics.models import GoogleAdsSavedView


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _make_saved_view(
    tenant,
    *,
    user=None,
    name: str = "Test View",
    filters: dict | None = None,
    columns: list | None = None,
) -> GoogleAdsSavedView:
    return GoogleAdsSavedView.objects.create(
        tenant=tenant,
        name=name,
        description="",
        filters=filters if filters is not None else {},
        columns=columns if columns is not None else [],
        is_shared=True,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
def test_verify_returns_no_drift_for_canonical_view(api_client, user, tenant):
    view = _make_saved_view(
        tenant,
        user=user,
        filters={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        columns=["campaign_name", "clicks"],
    )
    _authenticate(api_client, user)

    response = api_client.get(
        reverse("analytics-google-ads-saved-view-verify", args=[view.pk]),
    )
    assert response.status_code == 200, response.content
    data = response.data
    assert data["id"] == str(view.pk)
    assert data["name"] == view.name
    assert data["drift"] is False
    assert data["unknown_filter_keys"] == []
    assert data["unknown_columns"] == []
    assert data["checked_against_version"] == "google-ads-v23"


@pytest.mark.django_db
def test_verify_flags_unknown_filter_key(api_client, user, tenant):
    view = _make_saved_view(
        tenant,
        user=user,
        filters={"banana": 1},
        columns=["clicks"],
    )
    _authenticate(api_client, user)

    response = api_client.get(
        reverse("analytics-google-ads-saved-view-verify", args=[view.pk]),
    )
    assert response.status_code == 200, response.content
    data = response.data
    assert data["drift"] is True
    assert "banana" in data["unknown_filter_keys"]
    assert data["unknown_columns"] == []


@pytest.mark.django_db
def test_verify_flags_unknown_column(api_client, user, tenant):
    view = _make_saved_view(
        tenant,
        user=user,
        filters={"start_date": "2025-01-01"},
        columns=["bogus_col"],
    )
    _authenticate(api_client, user)

    response = api_client.get(
        reverse("analytics-google-ads-saved-view-verify", args=[view.pk]),
    )
    assert response.status_code == 200, response.content
    data = response.data
    assert data["drift"] is True
    assert data["unknown_filter_keys"] == []
    assert "bogus_col" in data["unknown_columns"]


@pytest.mark.django_db
def test_verify_tenant_isolation(api_client, user, tenant):
    seed_default_roles()
    view = _make_saved_view(
        tenant,
        user=user,
        filters={"start_date": "2025-01-01"},
        columns=["clicks"],
    )

    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_user = User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
        password="password123",
    )
    assign_role(other_user, Role.ADMIN)
    _authenticate(api_client, other_user)

    response = api_client.get(
        reverse("analytics-google-ads-saved-view-verify", args=[view.pk]),
    )
    assert response.status_code == 404
