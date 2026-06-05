from __future__ import annotations

import csv
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, Role, Tenant, User, assign_role, seed_default_roles
from analytics.models import AISummary, DashboardDefinition, ReportDefinition, ReportExportJob
from analytics.tasks import run_report_export_job
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


def test_generic_report_csv_export_creates_downloadable_artifact(tenant, tmp_path, monkeypatch):
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="Pilot report",
        filters={"range": "last_7_days", "platforms": ["meta"]},
    )
    job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
    )
    generated_at = timezone.now()
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant",
        lambda tenant_id: (
            {
                "campaign": {
                    "summary": {"currency": "JMD", "totalSpend": 120},
                    "rows": [
                        {
                            "platform": "Meta",
                            "name": "=Pilot campaign",
                            "impressions": 500,
                            "clicks": 20,
                            "ctr": 4,
                            "spend": 120,
                            "conversions": 2,
                            "cpa": 60,
                        },
                        {
                            "platform": "Google Ads",
                            "name": "Filtered campaign",
                            "impressions": 500,
                            "clicks": 20,
                            "spend": 120,
                        },
                    ],
                }
            },
            generated_at,
            "fetched",
        ),
    )

    result = run_report_export_job.run(str(job.id))

    job.refresh_from_db()
    artifact = tmp_path / job.artifact_path.lstrip("/")
    assert result["status"] == ReportExportJob.STATUS_COMPLETED
    assert job.status == ReportExportJob.STATUS_COMPLETED
    assert artifact.exists()
    rows = list(csv.DictReader(artifact.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["campaign"] == "'=Pilot campaign"
    assert all(row["campaign"] != "Filtered campaign" for row in rows)
    assert job.metadata["row_count"] == 1
    assert job.metadata["source"] == "aggregate_snapshot"
    assert job.metadata["selected_platforms"] == ["meta"]


@pytest.mark.parametrize("export_format", [ReportExportJob.FORMAT_PDF, ReportExportJob.FORMAT_PNG])
def test_generic_visual_report_exports_verify_renderer_artifacts(
    tenant, tmp_path, monkeypatch, export_format
):
    report = ReportDefinition.objects.create(tenant=tenant, name="Visual report")
    job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=export_format,
    )
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant",
        lambda tenant_id: (
            {"campaign": {"summary": {"currency": "USD"}, "rows": []}},
            timezone.now(),
            "default",
        ),
    )

    def fake_render(command, **_kwargs):
        pdf_path = command[command.index("--out") + 1]
        png_path = command[command.index("--png") + 1]
        Path(pdf_path).write_bytes(b"pdf artifact")
        Path(png_path).write_bytes(b"png artifact")

    monkeypatch.setattr("analytics.tasks.subprocess.run", fake_render)

    result = run_report_export_job.run(str(job.id))

    job.refresh_from_db()
    assert result["status"] == ReportExportJob.STATUS_COMPLETED
    assert (tmp_path / job.artifact_path.lstrip("/")).stat().st_size > 0


def test_generic_report_export_fails_without_renderer_artifact(tenant, tmp_path, monkeypatch):
    report = ReportDefinition.objects.create(tenant=tenant, name="Missing artifact report")
    job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_PDF,
    )
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant",
        lambda tenant_id: (
            {"campaign": {"summary": {}, "rows": []}},
            timezone.now(),
            "default",
        ),
    )
    monkeypatch.setattr("analytics.tasks.subprocess.run", lambda *args, **kwargs: None)

    result = run_report_export_job.run(str(job.id))

    job.refresh_from_db()
    assert result["status"] == ReportExportJob.STATUS_FAILED
    assert job.status == ReportExportJob.STATUS_FAILED
    assert job.artifact_path == ""
    assert job.error_message == "Export generation failed (FileNotFoundError)."


def test_generic_report_export_enqueue_failure_is_sanitized(api_client, user, tenant, monkeypatch):
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(tenant=tenant, name="Queue failure report")

    def fail_enqueue(_job_id):
        raise RuntimeError("redis://user:secret-value@queue.invalid")

    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", fail_enqueue)

    response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == ReportExportJob.STATUS_FAILED
    assert response.json()["error_message"] == "Export scheduling failed (RuntimeError)."
    assert "secret-value" not in str(response.json())


def test_generic_report_download_returns_non_empty_artifact(
    api_client, user, tenant, tmp_path, monkeypatch
):
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(tenant=tenant, name="Download report")
    job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
        status=ReportExportJob.STATUS_COMPLETED,
        artifact_path=f"/exports/{tenant.id}/{report.id}/download.csv",
    )
    artifact = tmp_path / job.artifact_path.lstrip("/")
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"campaign,spend\r\nPilot,12\r\n")
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)

    response = api_client.get(reverse("report-export-download", args=[job.id]))

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"campaign,spend\r\nPilot,12\r\n"
    assert "download.csv" in response["Content-Disposition"]


def test_generic_report_download_rejects_empty_or_cross_tenant_artifact(
    api_client, user, tenant, tmp_path, monkeypatch
):
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(tenant=tenant, name="Empty report")
    empty_job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
        status=ReportExportJob.STATUS_COMPLETED,
        artifact_path=f"/exports/{tenant.id}/{report.id}/empty.csv",
    )
    artifact = tmp_path / empty_job.artifact_path.lstrip("/")
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"")
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)

    empty_response = api_client.get(reverse("report-export-download", args=[empty_job.id]))
    assert empty_response.status_code == 404

    other_tenant = Tenant.objects.create(name="Other Export Tenant")
    other_report = ReportDefinition.objects.create(tenant=other_tenant, name="Other report")
    other_job = ReportExportJob.objects.create(
        tenant=other_tenant,
        report=other_report,
        export_format=ReportExportJob.FORMAT_CSV,
        status=ReportExportJob.STATUS_COMPLETED,
        artifact_path=f"/exports/{other_tenant.id}/{other_report.id}/other.csv",
    )
    tenant_response = api_client.get(reverse("report-export-download", args=[other_job.id]))
    assert tenant_response.status_code == 404


def test_generic_report_download_rejects_prefix_sibling_path_traversal(
    api_client, user, tenant, tmp_path, monkeypatch
):
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(tenant=tenant, name="Unsafe report")
    job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
        status=ReportExportJob.STATUS_COMPLETED,
        artifact_path=f"/exports/../../{tmp_path.name}-escaped.csv",
    )
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)

    response = api_client.get(reverse("report-export-download", args=[job.id]))

    assert response.status_code == 500
    assert response.json()["detail"] == "Export artifact path is unsafe."


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


def test_ga4_web_insights_isolates_rows_by_tenant(api_client, user, tenant):
    """GA4WebInsightsView must return only the authenticated tenant's rows.

    See docs/runbooks/ga4-operations.md § Architecture — dashboard path tenant isolation.
    The view reads `agg_ga4_daily` via raw SQL with `WHERE tenant_id = %s`; this test seeds
    two tenants' rows and asserts only the authed tenant's rows come back.
    """
    from django.db import connection

    other_tenant = Tenant.objects.create(name="Other Tenant")

    with connection.cursor() as cursor:
        # agg_ga4_daily is a dbt mart that exists only when `enable_ga4=true`. Create a
        # transient table matching the mart schema for this test; the surrounding
        # django_db transaction rolls it back on teardown.
        cursor.execute(
            """
            CREATE TEMPORARY TABLE agg_ga4_daily (
                tenant_id UUID NOT NULL,
                date_day DATE NOT NULL,
                property_id TEXT NOT NULL,
                channel_group TEXT NOT NULL,
                country TEXT NOT NULL,
                city TEXT NOT NULL,
                campaign_name TEXT NOT NULL,
                sessions NUMERIC NOT NULL,
                engaged_sessions NUMERIC NOT NULL,
                conversions NUMERIC NOT NULL,
                purchase_revenue NUMERIC NOT NULL,
                engagement_rate NUMERIC NOT NULL,
                conversion_rate NUMERIC NOT NULL
            )
            """
        )
        cursor.executemany(
            """
            INSERT INTO agg_ga4_daily
              (tenant_id, date_day, property_id, channel_group, country, city,
               campaign_name, sessions, engaged_sessions, conversions,
               purchase_revenue, engagement_rate, conversion_rate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    str(tenant.id),
                    "2026-04-20",
                    "11111",
                    "Organic Search",
                    "JM",
                    "Kingston",
                    "brand",
                    100,
                    75,
                    5,
                    250,
                    0.75,
                    0.05,
                ),
                (
                    str(other_tenant.id),
                    "2026-04-20",
                    "22222",
                    "Paid Search",
                    "JM",
                    "Montego Bay",
                    "leak_canary",
                    999,
                    500,
                    99,
                    9999,
                    0.5,
                    0.1,
                ),
            ],
        )

        authenticate(api_client, user)
        response = api_client.get("/api/analytics/web/ga4/")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ga4"
    assert body["status"] == "ok", body
    rows = body["rows"]

    assert len(rows) == 1, f"Expected exactly 1 row for authed tenant, got {len(rows)}: {rows}"
    assert str(rows[0]["tenant_id"]) == str(tenant.id)
    assert rows[0]["property_id"] == "11111"
    assert rows[0]["campaign_name"] == "brand"
    # Leak canary: the other tenant's distinctive campaign must never appear.
    assert not any(row.get("campaign_name") == "leak_canary" for row in rows)
    assert not any(str(row.get("tenant_id")) == str(other_tenant.id) for row in rows)
