from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, Role, Tenant, User, assign_role, seed_default_roles
from analytics.models import AISummary, DashboardDefinition, ReportDefinition
from integrations.models import AirbyteConnection, AlertRuleDefinition


def authenticate(api_client, user):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.email, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def list_payload(response):
    data = response.json()
    if isinstance(data, list):
        return data
    return data.get("results", data)


def create_viewer(*, tenant: Tenant, email: str) -> User:
    seed_default_roles()
    user = User.objects.create_user(
        username=email,
        email=email,
        tenant=tenant,
        password="password123",
    )
    assign_role(user, Role.VIEWER)
    return user


def test_reports_crud_and_export_request(api_client, user, tenant):
    authenticate(api_client, user)

    payload = {
        "name": "Weekly performance pack",
        "description": "Executive weekly KPI rollup",
        "filters": {"range": "last_7_days", "channel": ["META", "GOOGLE"]},
        "layout": {"widgets": ["campaign_summary", "budget_pacing"]},
        "is_active": True,
    }
    create_response = api_client.post(reverse("report-definition-list"), payload, format="json")
    assert create_response.status_code == 201
    report_id = create_response.json()["id"]

    list_response = api_client.get(reverse("report-definition-list"))
    assert list_response.status_code == 200
    rows = list_payload(list_response)
    assert any(row["id"] == report_id for row in rows)

    export_response = api_client.post(
        reverse("report-definition-exports", args=[report_id]),
        {"export_format": "csv"},
        format="json",
    )
    assert export_response.status_code == 201
    assert export_response.json()["report_id"] == report_id

    export_list = api_client.get(reverse("report-definition-exports", args=[report_id]))
    assert export_list.status_code == 200
    assert len(export_list.json()) == 1

    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="report_created",
        resource_type="report_definition",
    ).exists()
    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="report_export_requested",
        resource_type="report_export_job",
    ).exists()


def test_alerts_endpoint_is_tenant_scoped(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    AlertRuleDefinition.objects.create(
        tenant=other_tenant,
        name="Other tenant rule",
        metric="cpa",
        comparison_operator=AlertRuleDefinition.OPERATOR_GREATER_THAN,
        threshold=15,
        lookback_hours=6,
    )
    AlertRuleDefinition.objects.create(
        tenant=tenant,
        name="Tenant rule",
        metric="ctr",
        comparison_operator=AlertRuleDefinition.OPERATOR_LESS_THAN,
        threshold=2,
        lookback_hours=12,
    )

    authenticate(api_client, user)

    response = api_client.get(reverse("alerts-list"))
    assert response.status_code == 200
    names = [row["name"] for row in list_payload(response)]
    assert "Tenant rule" in names
    assert "Other tenant rule" not in names


def test_summaries_list_and_refresh(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Another Tenant")
    AISummary.objects.create(
        tenant=other_tenant,
        title="Other summary",
        summary="Other tenant summary",
        source="daily_summary",
    )
    AISummary.objects.create(
        tenant=tenant,
        title="Current summary",
        summary="Current tenant summary",
        source="daily_summary",
    )

    authenticate(api_client, user)

    list_response = api_client.get(reverse("ai-summary-list"))
    assert list_response.status_code == 200
    listed = list_payload(list_response)
    assert any(row["title"] == "Current summary" for row in listed)
    assert all(row["title"] != "Other summary" for row in listed)

    refresh_response = api_client.post(reverse("ai-summary-refresh"), {}, format="json")
    assert refresh_response.status_code == 201
    assert refresh_response.json()["source"] == "manual_refresh"


def test_sync_health_and_health_overview_endpoints(api_client, user, tenant):
    stale_time = timezone.now() - timedelta(hours=5)
    AirbyteConnection.objects.create(
        tenant=tenant,
        provider="META",
        name="Meta metrics",
        connection_id=uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        is_active=True,
        last_synced_at=stale_time,
        last_job_status="failed",
        last_job_error="boom",
    )

    authenticate(api_client, user)

    sync_response = api_client.get(reverse("ops-sync-health"))
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["counts"]["total"] == 1
    assert sync_payload["rows"][0]["state"] == "failed"

    overview_response = api_client.get(reverse("ops-health-overview"))
    assert overview_response.status_code == 200
    keys = {card["key"] for card in overview_response.json()["cards"]}
    assert {"api", "airbyte", "dbt", "timezone"}.issubset(keys)


def test_dashboard_library_endpoint(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    DashboardDefinition.objects.create(
        tenant=other_tenant,
        name="Other tenant dashboard",
        description="Should not leak",
        template_key=DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
        filters={"accountId": "act_1"},
        layout={"widgets": ["kpis"]},
        default_metric=DashboardDefinition.METRIC_SPEND,
        created_by=user,
        updated_by=user,
    )
    DashboardDefinition.objects.create(
        tenant=tenant,
        name="Saved Meta dashboard",
        description="Saved dashboard for dashboard library",
        template_key=DashboardDefinition.TEMPLATE_META_CREATIVE_INSIGHTS,
        filters={"accountId": "act_791712443035541"},
        layout={"widgets": ["creative_table"]},
        default_metric=DashboardDefinition.METRIC_CTR,
        created_by=user,
        updated_by=user,
    )
    ReportDefinition.objects.create(
        tenant=tenant,
        name="Saved report",
        description="Saved report for dashboard library",
        created_by=user,
        updated_by=user,
    )

    authenticate(api_client, user)

    response = api_client.get(reverse("dashboard-library"))
    assert response.status_code == 200
    payload = response.json()
    assert {"generatedAt", "systemTemplates", "savedDashboards"} == set(payload.keys())
    assert any(item["route"].startswith("/dashboards/create?template=") for item in payload["systemTemplates"])
    assert any(item["route"].startswith("/dashboards/saved/") for item in payload["savedDashboards"])
    assert any(item["name"] == "Saved Meta dashboard" for item in payload["savedDashboards"])
    assert all(item["name"] != "Saved report" for item in payload["savedDashboards"])


def test_dashboard_library_bootstraps_default_presets_idempotently(api_client, user, tenant):
    authenticate(api_client, user)

    first_response = api_client.get(reverse("dashboard-library"))
    assert first_response.status_code == 200
    first_payload = first_response.json()
    preset_names = {item["name"] for item in first_payload["savedDashboards"]}
    assert preset_names == {
        "Executive overview (30 days)",
        "Campaign review (7 days)",
        "Budget pacing (MTD)",
    }
    assert DashboardDefinition.objects.filter(tenant=tenant, is_active=True).count() == 3
    assert all(
        dashboard.created_by is None and dashboard.updated_by is None
        for dashboard in DashboardDefinition.objects.filter(tenant=tenant)
    )

    second_response = api_client.get(reverse("dashboard-library"))
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert {item["name"] for item in second_payload["savedDashboards"]} == preset_names
    assert DashboardDefinition.objects.filter(tenant=tenant, is_active=True).count() == 3


def test_dashboard_definitions_crud_duplicate_and_recent(api_client, user, tenant):
    authenticate(api_client, user)

    payload = {
        "name": "SLB executive dashboard",
        "description": "Saved Meta dashboard",
        "template_key": DashboardDefinition.TEMPLATE_META_EXECUTIVE_OVERVIEW,
        "filters": {
            "accountId": "act_791712443035541",
            "dateRange": "90d",
            "channels": ["Meta Ads"],
            "campaignQuery": "",
        },
        "layout": {"routeKind": "campaigns", "widgets": ["kpis", "trend", "campaign_table"]},
        "default_metric": DashboardDefinition.METRIC_SPEND,
        "is_active": True,
    }

    create_response = api_client.post(
        reverse("dashboard-definition-list"),
        payload,
        format="json",
    )
    assert create_response.status_code == 201
    dashboard_id = create_response.json()["id"]

    list_response = api_client.get(reverse("dashboard-definition-list"))
    assert list_response.status_code == 200
    assert any(row["id"] == dashboard_id for row in list_payload(list_response))

    patch_response = api_client.patch(
        reverse("dashboard-definition-detail", args=[dashboard_id]),
        {"name": "SLB renamed dashboard", "default_metric": DashboardDefinition.METRIC_CTR},
        format="json",
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "SLB renamed dashboard"
    assert patch_response.json()["default_metric"] == DashboardDefinition.METRIC_CTR

    duplicate_response = api_client.post(
        reverse("dashboard-definition-duplicate", args=[dashboard_id]),
        {},
        format="json",
    )
    assert duplicate_response.status_code == 201
    duplicate_id = duplicate_response.json()["id"]
    assert duplicate_response.json()["name"] == "SLB renamed dashboard Copy"

    recent_response = api_client.get(reverse("dashboard-recent"), {"limit": 5})
    assert recent_response.status_code == 200
    recent_routes = [row["route"] for row in recent_response.json()]
    assert f"/dashboards/saved/{dashboard_id}" in recent_routes
    assert f"/dashboards/saved/{duplicate_id}" in recent_routes

    delete_response = api_client.delete(reverse("dashboard-definition-detail", args=[duplicate_id]))
    assert delete_response.status_code == 204

    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="dashboard_definition_created",
        resource_type="dashboard_definition",
    ).exists()
    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="dashboard_definition_updated",
        resource_type="dashboard_definition",
    ).exists()
    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="dashboard_definition_duplicated",
        resource_type="dashboard_definition",
    ).exists()
    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="dashboard_definition_deleted",
        resource_type="dashboard_definition",
    ).exists()


def test_dashboard_definitions_require_dashboard_edit_privilege(api_client, tenant):
    viewer = create_viewer(tenant=tenant, email="viewer@example.com")
    authenticate(api_client, viewer)

    response = api_client.post(
        reverse("dashboard-definition-list"),
        {
            "name": "Viewer dashboard",
            "description": "Should fail",
            "template_key": DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
            "filters": {},
            "layout": {"widgets": ["kpis"]},
            "default_metric": DashboardDefinition.METRIC_SPEND,
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 403


def test_web_analytics_endpoints_available(api_client, user):
    authenticate(api_client, user)

    ga4_response = api_client.get("/api/analytics/web/ga4/")
    assert ga4_response.status_code == 200
    assert ga4_response.json()["source"] == "ga4"

    search_console_response = api_client.get("/api/analytics/web/search-console/")
    assert search_console_response.status_code == 200
    assert search_console_response.json()["source"] == "search_console"
