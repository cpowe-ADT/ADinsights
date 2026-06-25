"""Tests for the saved report layouts API (``SavedReportLayoutViewSet``).

Covers CRUD with tenant/owner stamping, config round-tripping, tenant isolation
(cross-tenant access 404s), and owner-scoping (a non-admin sees only their own
layouts plus shared ones).
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Role, Tenant, User, assign_role, seed_default_roles
from analytics.models import SavedReportLayout

SAMPLE_CONFIG = {
    "id": "slb-overview",
    "title": "SLB Overview",
    "cols": 12,
    "rowHeight": 64,
    "widgets": [
        {
            "id": "spend",
            "type": "kpi",
            "title": "Spend",
            "x": 1,
            "y": 1,
            "w": 3,
            "h": 2,
            "dataKey": "summary.totalSpend",
            "options": {"format": "currency", "currency": "JMD"},
        }
    ],
}


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _member(tenant, email: str, role: str = Role.VIEWER) -> User:
    user = User.objects.create_user(
        username=email,
        email=email,
        tenant=tenant,
        password="password123",
    )
    assign_role(user, role)
    return user


@pytest.mark.django_db
def test_create_stamps_tenant_and_owner(api_client, user, tenant):
    _authenticate(api_client, user)

    response = api_client.post(
        reverse("analytics-report-layout-list"),
        {"name": "Overview", "config": SAMPLE_CONFIG},
        format="json",
    )

    assert response.status_code == 201, response.content
    layout = SavedReportLayout.all_objects.get(id=response.data["id"])
    assert layout.tenant_id == tenant.id
    assert layout.created_by_id == user.id
    assert layout.updated_by_id == user.id
    # Config round-trips verbatim.
    assert layout.config == SAMPLE_CONFIG
    assert response.data["config"]["widgets"][0]["dataKey"] == "summary.totalSpend"


@pytest.mark.django_db
def test_list_returns_own_layouts(api_client, user, tenant):
    SavedReportLayout.objects.create(
        tenant=tenant, name="Mine", config=SAMPLE_CONFIG, created_by=user, updated_by=user
    )
    _authenticate(api_client, user)

    response = api_client.get(reverse("analytics-report-layout-list"))

    assert response.status_code == 200, response.content
    results = response.data["results"] if "results" in response.data else response.data
    assert [r["name"] for r in results] == ["Mine"]


@pytest.mark.django_db
def test_update_roundtrips_config_and_stamps_updated_by(api_client, user, tenant):
    layout = SavedReportLayout.objects.create(
        tenant=tenant, name="Draft", config={}, created_by=user, updated_by=user
    )
    _authenticate(api_client, user)

    response = api_client.patch(
        reverse("analytics-report-layout-detail", args=[layout.pk]),
        {"name": "Final", "config": SAMPLE_CONFIG},
        format="json",
    )

    assert response.status_code == 200, response.content
    layout.refresh_from_db()
    assert layout.name == "Final"
    assert layout.config == SAMPLE_CONFIG
    assert layout.updated_by_id == user.id


@pytest.mark.django_db
def test_delete_removes_layout(api_client, user, tenant):
    layout = SavedReportLayout.objects.create(
        tenant=tenant, name="Trash me", config=SAMPLE_CONFIG, created_by=user, updated_by=user
    )
    _authenticate(api_client, user)

    response = api_client.delete(
        reverse("analytics-report-layout-detail", args=[layout.pk])
    )

    assert response.status_code == 204, response.content
    assert not SavedReportLayout.all_objects.filter(pk=layout.pk).exists()


@pytest.mark.django_db
def test_tenant_isolation_returns_404(api_client, user, tenant):
    layout = SavedReportLayout.objects.create(
        tenant=tenant, name="Secret", config=SAMPLE_CONFIG, created_by=user, updated_by=user
    )

    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_user = _member(other_tenant, "other@example.com", role=Role.ADMIN)
    _authenticate(api_client, other_user)

    response = api_client.get(
        reverse("analytics-report-layout-detail", args=[layout.pk])
    )
    assert response.status_code == 404, response.content

    list_response = api_client.get(reverse("analytics-report-layout-list"))
    results = (
        list_response.data["results"]
        if "results" in list_response.data
        else list_response.data
    )
    assert results == []


@pytest.mark.django_db
def test_owner_scoping_hides_other_users_private_layout(api_client, tenant):
    seed_default_roles()
    owner = _member(tenant, "owner@example.com", role=Role.VIEWER)
    other = _member(tenant, "teammate@example.com", role=Role.VIEWER)

    private = SavedReportLayout.objects.create(
        tenant=tenant, name="Owner private", config=SAMPLE_CONFIG,
        created_by=owner, updated_by=owner, is_shared=False,
    )
    shared = SavedReportLayout.objects.create(
        tenant=tenant, name="Team shared", config=SAMPLE_CONFIG,
        created_by=owner, updated_by=owner, is_shared=True,
    )

    _authenticate(api_client, other)
    response = api_client.get(reverse("analytics-report-layout-list"))
    results = response.data["results"] if "results" in response.data else response.data
    names = {r["name"] for r in results}

    assert shared.name in names
    assert private.name not in names
