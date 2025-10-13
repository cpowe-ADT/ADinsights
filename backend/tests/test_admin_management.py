from __future__ import annotations

from django.urls import reverse

from accounts.models import AuditLog, Tenant
from integrations.models import AlertRuleDefinition, CampaignBudget


def authenticate(api_client, user):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def list_results(response):
    body = response.json()
    if isinstance(body, list):
        return body
    return body.get("results", [])


def test_campaign_budget_crud_and_audit_log(api_client, user, tenant):
    authenticate(api_client, user)

    payload = {
        "name": "Brand Awareness",
        "monthly_target": "1000.50",
        "currency": "usd",
        "is_active": True,
    }

    create_response = api_client.post(
        reverse("campaignbudget-list"), payload, format="json"
    )
    assert create_response.status_code == 201
    created = create_response.json()
    budget_id = created["id"]
    assert created["currency"] == "USD"

    list_response = api_client.get(reverse("campaignbudget-list"))
    assert list_response.status_code == 200
    results = list_results(list_response)
    assert len(results) == 1
    assert results[0]["name"] == "Brand Awareness"
    assert results[0]["monthly_target"] == "1000.50"

    created_log = AuditLog.all_objects.get(
        tenant=tenant,
        action="campaign_budget_created",
        resource_id=str(budget_id),
    )
    assert created_log.metadata == {
        "redacted": True,
        "fields": ["currency", "is_active", "monthly_target", "name"],
    }

    update_response = api_client.patch(
        reverse("campaignbudget-detail", args=[budget_id]),
        {"is_active": False},
        format="json",
    )
    assert update_response.status_code == 200
    updated_log = AuditLog.all_objects.get(
        tenant=tenant,
        action="campaign_budget_updated",
        resource_id=str(budget_id),
    )
    assert updated_log.metadata == {
        "redacted": True,
        "fields": ["is_active"],
    }

    delete_response = api_client.delete(
        reverse("campaignbudget-detail", args=[budget_id])
    )
    assert delete_response.status_code == 204
    assert not CampaignBudget.objects.filter(id=budget_id).exists()
    deleted_log = AuditLog.all_objects.get(
        tenant=tenant,
        action="campaign_budget_deleted",
        resource_id=str(budget_id),
    )
    assert deleted_log.metadata == {"redacted": True, "fields": []}


def test_campaign_budget_rls_enforced(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    CampaignBudget.objects.create(
        tenant=other_tenant,
        name="Other Budget",
        monthly_target=500,
        currency="USD",
    )

    authenticate(api_client, user)

    CampaignBudget.objects.create(
        tenant=tenant,
        name="Tenant Budget",
        monthly_target=250,
        currency="USD",
    )

    response = api_client.get(reverse("campaignbudget-list"))
    assert response.status_code == 200
    body = list_results(response)
    names = [row["name"] for row in body]
    assert "Tenant Budget" in names
    assert "Other Budget" not in names


def test_campaign_budget_validation(api_client, user):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("campaignbudget-list"),
        {
            "name": "Invalid Budget",
            "monthly_target": "-10.00",
            "currency": "usd",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "monthly_target" in response.json()


def test_create_and_list_alert_rule(api_client, user, tenant):
    authenticate(api_client, user)

    payload = {
        "name": "High CPA",
        "metric": "cpa",
        "comparison_operator": "gt",
        "threshold": "150.00",
        "lookback_hours": 24,
        "severity": "high",
    }

    create_response = api_client.post(
        reverse("alertruledefinition-list"), payload, format="json"
    )
    assert create_response.status_code == 201
    data = create_response.json()
    assert data["metric"] == "cpa"

    list_response = api_client.get(reverse("alertruledefinition-list"))
    assert list_response.status_code == 200
    body = list_results(list_response)
    assert len(body) == 1
    assert body[0]["name"] == "High CPA"


def test_alert_rule_rls_enforced(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Second Tenant")
    AlertRuleDefinition.objects.create(
        tenant=other_tenant,
        name="Other Rule",
        metric="cpc",
        comparison_operator=AlertRuleDefinition.OPERATOR_GREATER_THAN,
        threshold=10,
        lookback_hours=12,
        severity=AlertRuleDefinition.SEVERITY_LOW,
    )

    authenticate(api_client, user)

    AlertRuleDefinition.objects.create(
        tenant=tenant,
        name="Tenant Rule",
        metric="ctr",
        comparison_operator=AlertRuleDefinition.OPERATOR_LESS_THAN,
        threshold=5,
        lookback_hours=6,
        severity=AlertRuleDefinition.SEVERITY_MEDIUM,
    )

    response = api_client.get(reverse("alertruledefinition-list"))
    assert response.status_code == 200
    body = list_results(response)
    names = [row["name"] for row in body]
    assert "Tenant Rule" in names
    assert "Other Rule" not in names


def test_alert_rule_validation(api_client, user):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alertruledefinition-list"),
        {
            "name": "Invalid Rule",
            "metric": "cpa",
            "comparison_operator": "gt",
            "threshold": "0",
            "lookback_hours": 0,
        },
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert "threshold" in body
    assert "lookback_hours" in body


def test_alert_rule_audit_logging(api_client, user, tenant):
    authenticate(api_client, user)

    create_response = api_client.post(
        reverse("alertruledefinition-list"),
        {
            "name": "Logging Rule",
            "metric": "roas",
            "comparison_operator": "lt",
            "threshold": "0.90",
            "lookback_hours": 48,
        },
        format="json",
    )
    assert create_response.status_code == 201
    alert_id = create_response.json()["id"]

    audit_entries = AuditLog.all_objects.filter(
        tenant=tenant,
        action="alert_rule_created",
        resource_id=str(alert_id),
    )
    assert audit_entries.count() == 1
    metadata = audit_entries.first().metadata
    assert metadata["redacted"] is True
    assert "threshold" in metadata["fields"]
    assert "0.90" not in str(metadata)

    update_response = api_client.patch(
        reverse("alertruledefinition-detail", args=[alert_id]),
        {"severity": "high"},
        format="json",
    )
    assert update_response.status_code == 200

    update_entries = AuditLog.all_objects.filter(
        tenant=tenant,
        action="alert_rule_updated",
        resource_id=str(alert_id),
    )
    assert update_entries.count() == 1
    update_metadata = update_entries.first().metadata
    assert update_metadata["redacted"] is True
    assert update_metadata["fields"] == ["severity"]


def test_alert_rule_choices_validation(api_client, user):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("alertruledefinition-list"),
        {
            "name": "Bad Operator",
            "metric": "cpa",
            "comparison_operator": "invalid",
            "threshold": "10",
            "lookback_hours": 12,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "comparison_operator" in response.json()
