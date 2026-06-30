from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, Tenant, User, assign_role, seed_default_roles, Role
from integrations.models import AlertRuleDefinition


def authenticate(api_client, user):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _make_rule(tenant, *, name="High CPA", metric="cpa", is_active=True, paused_until=None):
    return AlertRuleDefinition.objects.create(
        tenant=tenant,
        name=name,
        metric=metric,
        comparison_operator=AlertRuleDefinition.OPERATOR_GREATER_THAN,
        threshold=15,
        lookback_hours=6,
        is_active=is_active,
        paused_until=paused_until,
    )


def test_pause_with_duration_hours_sets_paused_until_future(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    before = timezone.now()
    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"duration_hours": 24},
        format="json",
    )
    after = timezone.now()

    assert response.status_code == 200, response.content
    rule.refresh_from_db()
    assert rule.is_active is False
    assert rule.paused_until is not None
    expected_low = before + timedelta(hours=24) - timedelta(seconds=5)
    expected_high = after + timedelta(hours=24) + timedelta(seconds=5)
    assert expected_low <= rule.paused_until <= expected_high


def test_pause_with_duration_hours_zero_rejected(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"duration_hours": 0},
        format="json",
    )

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_with_duration_hours_above_cap_rejected(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"duration_hours": 1000},
        format="json",
    )

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_with_duration_hours_boolean_rejected(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"duration_hours": True},
        format="json",
    )

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_with_explicit_pause_until_iso(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    target = timezone.now() + timedelta(hours=2)
    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"pause_until": target.isoformat()},
        format="json",
    )

    assert response.status_code == 200, response.content
    rule.refresh_from_db()
    assert rule.is_active is False
    assert rule.paused_until is not None
    delta = abs((rule.paused_until - target).total_seconds())
    assert delta < 1.0


def test_pause_with_pause_until_naive_rejected(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    naive = (timezone.now() + timedelta(hours=2)).replace(tzinfo=None)
    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"pause_until": naive.isoformat()},
        format="json",
    )

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_with_pause_until_in_past_rejected(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    past = timezone.now() - timedelta(hours=1)
    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"pause_until": past.isoformat()},
        format="json",
    )

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_with_both_fields_rejected(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    target = timezone.now() + timedelta(hours=2)
    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"pause_until": target.isoformat(), "duration_hours": 24},
        format="json",
    )

    assert response.status_code == 400
    body = response.json()
    detail = body.get("detail", "")
    assert "pause_until" in detail and "duration_hours" in detail
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_with_empty_body_indefinite(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {},
        format="json",
    )

    assert response.status_code == 200, response.content
    rule.refresh_from_db()
    assert rule.is_active is False
    assert rule.paused_until is None


def test_resume_clears_paused_until_and_activates(api_client, user, tenant):
    future = timezone.now() + timedelta(hours=4)
    rule = _make_rule(tenant, is_active=False, paused_until=future)
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alerts-resume", args=[rule.id]),
        {},
        format="json",
    )

    assert response.status_code == 200, response.content
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_is_tenant_isolated(api_client, tenant):
    seed_default_roles()
    rule = _make_rule(tenant, name="Tenant A rule")

    other_tenant = Tenant.objects.create(name="Tenant B")
    other_user = User.objects.create_user(
        username="b@example.com",
        email="b@example.com",
        tenant=other_tenant,
        password="password123",
    )
    assign_role(other_user, Role.ADMIN)

    authenticate(api_client, other_user)

    pause_response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"duration_hours": 24},
        format="json",
    )
    assert pause_response.status_code == 404

    resume_response = api_client.post(
        reverse("alerts-resume", args=[rule.id]),
        {},
        format="json",
    )
    assert resume_response.status_code == 404

    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


def test_pause_emits_audit_log(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"duration_hours": 12},
        format="json",
    )
    assert response.status_code == 200, response.content

    rule.refresh_from_db()
    expected_iso = rule.paused_until.isoformat()
    log = AuditLog.all_objects.filter(
        tenant=tenant,
        action="alert_rule_paused",
        resource_type="alert_rule_definition",
        resource_id=str(rule.id),
    ).first()
    assert log is not None
    assert log.metadata.get("paused_until") == expected_iso


def test_resume_emits_audit_log(api_client, user, tenant):
    future = timezone.now() + timedelta(hours=2)
    rule = _make_rule(tenant, is_active=False, paused_until=future)
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alerts-resume", args=[rule.id]),
        {},
        format="json",
    )
    assert response.status_code == 200, response.content

    log = AuditLog.all_objects.filter(
        tenant=tenant,
        action="alert_rule_resumed",
        resource_type="alert_rule_definition",
        resource_id=str(rule.id),
    ).first()
    assert log is not None
    assert "resumed_at" in log.metadata


@pytest.mark.django_db
def test_active_for_eval_auto_resumes_expired_pauses(tenant):
    past = timezone.now() - timedelta(hours=1)
    future = timezone.now() + timedelta(hours=1)
    rule_expired = _make_rule(tenant, name="Expired pause", is_active=False, paused_until=past)
    rule_future = _make_rule(tenant, name="Future pause", is_active=False, paused_until=future)

    active_qs = AlertRuleDefinition.active_for_eval()
    active_ids = set(active_qs.values_list("id", flat=True))

    assert rule_expired.id in active_ids
    assert rule_future.id not in active_ids

    rule_expired.refresh_from_db()
    rule_future.refresh_from_db()

    assert rule_expired.is_active is True
    assert rule_expired.paused_until is None

    assert rule_future.is_active is False
    assert rule_future.paused_until is not None
    delta = abs((rule_future.paused_until - future).total_seconds())
    assert delta < 1.0


@pytest.mark.django_db
def test_active_for_eval_excludes_indefinitely_paused(tenant):
    rule = _make_rule(tenant, name="Indefinite pause", is_active=False, paused_until=None)

    active_qs = AlertRuleDefinition.active_for_eval()
    active_ids = set(active_qs.values_list("id", flat=True))

    assert rule.id not in active_ids
    rule.refresh_from_db()
    assert rule.is_active is False
    assert rule.paused_until is None


@pytest.mark.django_db
def test_active_for_eval_includes_active_rows(tenant):
    rule = _make_rule(tenant, name="Active rule", is_active=True, paused_until=None)

    active_qs = AlertRuleDefinition.active_for_eval()
    active_ids = set(active_qs.values_list("id", flat=True))

    assert rule.id in active_ids
