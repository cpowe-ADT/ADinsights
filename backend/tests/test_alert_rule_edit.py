from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, Tenant, seed_default_roles
from integrations.models import AlertRuleDefinition


def authenticate(api_client, user):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _make_rule(tenant, *, name="High CPA", metric="cpa", threshold=15):
    return AlertRuleDefinition.objects.create(
        tenant=tenant,
        name=name,
        metric=metric,
        comparison_operator=AlertRuleDefinition.OPERATOR_GREATER_THAN,
        threshold=threshold,
        lookback_hours=6,
    )


def test_patch_alert_rule_updates_fields_and_audits(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.patch(
        reverse("alerts-detail", args=[rule.id]),
        {"name": "Renamed rule", "threshold": "42.50"},
        format="json",
    )

    assert response.status_code == 200, response.content
    rule.refresh_from_db()
    assert rule.name == "Renamed rule"
    assert rule.threshold == Decimal("42.50")

    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="alert_rule_updated",
        resource_type="alert_rule_definition",
        resource_id=str(rule.id),
    ).exists()


def test_patch_rejects_blank_name(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.patch(
        reverse("alerts-detail", args=[rule.id]),
        {"name": "   "},
        format="json",
    )

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.name == "High CPA"


def test_patch_rejects_blank_metric(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    response = api_client.patch(
        reverse("alerts-detail", args=[rule.id]),
        {"metric": ""},
        format="json",
    )

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.metric == "cpa"


def test_patch_does_not_allow_paused_until_mutation(api_client, user, tenant):
    rule = _make_rule(tenant)
    authenticate(api_client, user)

    future_iso = (timezone.now() + timedelta(hours=4)).isoformat()
    response = api_client.patch(
        reverse("alerts-detail", args=[rule.id]),
        {"paused_until": future_iso},
        format="json",
    )

    # Field is read_only, so the request succeeds but the field is ignored.
    assert response.status_code == 200, response.content
    rule.refresh_from_db()
    assert rule.paused_until is None
    assert rule.is_active is True

    # Confirm the action endpoint IS able to set paused_until.
    pause_response = api_client.post(
        reverse("alerts-pause", args=[rule.id]),
        {"duration_hours": 24},
        format="json",
    )
    assert pause_response.status_code == 200, pause_response.content
    rule.refresh_from_db()
    assert rule.paused_until is not None
    assert rule.is_active is False


def test_delete_alert_rule_tenant_scoped(api_client, user, tenant):
    seed_default_roles()
    own_rule = _make_rule(tenant, name="Own rule")

    other_tenant = Tenant.objects.create(name="Other tenant")
    other_rule = AlertRuleDefinition.objects.create(
        tenant=other_tenant,
        name="Foreign rule",
        metric="ctr",
        comparison_operator=AlertRuleDefinition.OPERATOR_LESS_THAN,
        threshold=2,
        lookback_hours=12,
    )

    authenticate(api_client, user)

    foreign_delete = api_client.delete(
        reverse("alerts-detail", args=[other_rule.id])
    )
    assert foreign_delete.status_code == 404
    assert AlertRuleDefinition.all_objects.filter(id=other_rule.id).exists()

    own_delete = api_client.delete(reverse("alerts-detail", args=[own_rule.id]))
    assert own_delete.status_code == 204

    refetch = api_client.get(reverse("alerts-detail", args=[own_rule.id]))
    assert refetch.status_code == 404
