"""Tests for ``GoogleAdsRecommendationDismissView`` (GA-A2, LOCAL ONLY).

No SDK ``DismissRecommendation`` call is made — tests include a regression
guard that greps the backend for any such call.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, Role, Tenant, User, assign_role, seed_default_roles
from integrations.models import GoogleAdsSdkRecommendation


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _make_rec(
    tenant,
    *,
    customer_id: str = "1234567890",
    resource_name: str = "customers/1234567890/recommendations/abc",
    recommendation_type: str = "KEYWORD",
) -> GoogleAdsSdkRecommendation:
    return GoogleAdsSdkRecommendation.objects.create(
        tenant=tenant,
        customer_id=customer_id,
        recommendation_type=recommendation_type,
        resource_name=resource_name,
        campaign_id="987654321",
        ad_group_id="",
        dismissed=False,
        impact_metadata={},
        last_seen_at=timezone.now(),
    )


@pytest.mark.django_db
def test_dismiss_sets_fields(api_client, user, tenant):
    rec = _make_rec(tenant)
    _authenticate(api_client, user)

    response = api_client.post(
        reverse("google-ads-recommendation-dismiss", args=[rec.pk]),
        {},
        format="json",
    )
    assert response.status_code == 200, response.content
    rec.refresh_from_db()
    assert rec.dismissed is True
    assert rec.dismissed_at is not None
    assert rec.dismissed_by_id == user.id
    body = response.json()
    assert body["id"] == rec.pk
    assert body["dismissed"] is True
    assert body["dismissed_at"] is not None
    assert body["dismissed_by_user_id"] == str(user.id)


@pytest.mark.django_db
def test_dismiss_tenant_isolation(api_client, tenant):
    seed_default_roles()
    rec = _make_rec(tenant)

    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_user = User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
        password="password123",
    )
    assign_role(other_user, Role.ADMIN)

    _authenticate(api_client, other_user)
    response = api_client.post(
        reverse("google-ads-recommendation-dismiss", args=[rec.pk]),
        {},
        format="json",
    )
    assert response.status_code == 404

    rec.refresh_from_db()
    assert rec.dismissed is False
    assert rec.dismissed_at is None
    assert rec.dismissed_by_id is None


@pytest.mark.django_db
def test_dismiss_is_idempotent(api_client, user, tenant):
    rec = _make_rec(tenant)
    _authenticate(api_client, user)

    url = reverse("google-ads-recommendation-dismiss", args=[rec.pk])
    first = api_client.post(url, {}, format="json")
    second = api_client.post(url, {}, format="json")

    assert first.status_code == 200, first.content
    assert second.status_code == 200, second.content

    rec.refresh_from_db()
    assert rec.dismissed is True

    audit_entries = AuditLog.all_objects.filter(
        tenant=tenant,
        action="google_ads_recommendation_dismissed",
        resource_type="google_ads_recommendation",
        resource_id=str(rec.pk),
    )
    assert audit_entries.count() == 2


@pytest.mark.django_db
def test_dismiss_writes_audit(api_client, user, tenant):
    rec = _make_rec(tenant)
    _authenticate(api_client, user)

    response = api_client.post(
        reverse("google-ads-recommendation-dismiss", args=[rec.pk]),
        {},
        format="json",
    )
    assert response.status_code == 200, response.content

    log = AuditLog.all_objects.filter(
        tenant=tenant,
        action="google_ads_recommendation_dismissed",
        resource_type="google_ads_recommendation",
        resource_id=str(rec.pk),
    ).first()
    assert log is not None
    assert log.metadata.get("resource_name") == rec.resource_name
    assert log.metadata.get("customer_id") == rec.customer_id
    assert log.metadata.get("recommendation_type") == rec.recommendation_type


@pytest.mark.django_db
def test_list_returns_new_fields(api_client, user, tenant):
    _make_rec(tenant, resource_name="customers/1234567890/recommendations/r1")
    _make_rec(
        tenant,
        resource_name="customers/1234567890/recommendations/r2",
        recommendation_type="CAMPAIGN_BUDGET",
    )
    _authenticate(api_client, user)

    response = api_client.get(reverse("google-ads-recommendations"))
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["count"] == 2
    for row in body["results"]:
        assert "id" in row
        assert "dismissed_at" in row
        assert "dismissed_by_user_id" in row


def _scan_py_files_for(pattern: str, backend_root: Path) -> list[Path]:
    """Scan .py files under the backend for ``pattern``.

    Excludes the tests dir (this regression guard is legitimately referenced
    here), virtualenvs, __pycache__, and vendored data (non-.py) files such as
    the Google Ads schema reference text shipped under integrations/data/.
    """
    excluded = {"tests", ".venv", ".venv-tests", "__pycache__", "node_modules"}
    hits: list[Path] = []
    for path in backend_root.rglob("*.py"):
        if any(part in excluded for part in path.relative_to(backend_root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern in text:
            hits.append(path)
    return hits


def test_dismiss_has_no_sdk_call():
    """Regression guard: no Google Ads SDK dismiss call in production backend."""
    backend_root = Path(__file__).resolve().parent.parent

    camel_hits = _scan_py_files_for("DismissRecommendation", backend_root)
    assert camel_hits == [], (
        f"DismissRecommendation found in production backend code: {camel_hits}"
    )

    snake_hits = _scan_py_files_for("dismiss_recommendation", backend_root)
    assert snake_hits == [], (
        f"dismiss_recommendation found in production backend code: {snake_hits}"
    )

    # Sanity: the external grep-style check also returns no hits when run with
    # the same exclusions, mirroring the manual pre-deploy verification step.
    result = subprocess.run(
        [
            "grep",
            "-R",
            "-l",
            "--include=*.py",
            "--exclude-dir=tests",
            "--exclude-dir=.venv",
            "--exclude-dir=.venv-tests",
            "--exclude-dir=__pycache__",
            "--exclude-dir=node_modules",
            "DismissRecommendation",
            str(backend_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, (
        f"DismissRecommendation found in production backend code (grep):\n{result.stdout}"
    )
