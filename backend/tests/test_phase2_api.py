from __future__ import annotations

import csv
import json
from io import StringIO
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, Role, Tenant, User, assign_role, seed_default_roles
from analytics.models import (
    AISummary,
    Ad,
    AdAccount,
    AdSet,
    Campaign,
    DashboardDefinition,
    RawPerformanceRecord,
    ReportDefinition,
    ReportExportJob,
    TenantMetricsSnapshot,
)
from analytics.reporting_templates import build_slb_monthly_report_layout
from analytics.tasks import run_report_export_job
from integrations.models import (
    AirbyteConnection,
    AlertRuleDefinition,
    MetaConnection,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
    PlatformCredential,
)


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


def assert_redacted_report_audit_metadata(metadata, *, allow_blocking_reason_details=False):
    assert metadata["redacted"] is True
    serialized = json.dumps(metadata, default=str).lower()
    for forbidden in [
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "delivery_emails",
        "ops@example.com",
        "layout",
        "pages",
        "widgets",
        "report_snapshot",
        "rows",
    ]:
        if allow_blocking_reason_details and forbidden == "widgets":
            continue
        assert forbidden not in serialized


def assert_report_mutation_audit_metadata_is_redacted(metadata, *, expected_fields):
    assert metadata == {"fields": sorted(expected_fields), "redacted": True}
    serialized = json.dumps(metadata, default=str).lower()
    for forbidden in [
        "weekly performance pack",
        "executive weekly kpi rollup",
        "updated executive copy",
        "ops@example.com",
        "campaign_summary",
        "budget_pacing",
        "secret",
        "access_token",
        "refresh_token",
    ]:
        assert forbidden not in serialized


def assert_report_payload_excludes_sensitive_values(payload):
    serialized = json.dumps(payload, default=str).lower()
    for forbidden in [
        "access_token",
        "refresh_token",
        "client_secret",
        "page_token",
        "raw_payload",
        "user_id",
        "profile_id",
        "viewer_id",
        "actor_id",
        "delivery_emails",
        "ops@example.com",
        "recipient@example.com",
        "super-secret-value",
        "secret-token-value",
        "raw-provider-payload",
    ]:
        assert forbidden not in serialized


def block_live_network_calls(monkeypatch):
    def fail_network_call(*_args, **_kwargs):
        raise AssertionError("reporting preview/export/parity must not open live network connections")

    import socket
    import urllib.request

    monkeypatch.setattr(socket, "create_connection", fail_network_call)
    monkeypatch.setattr(socket.socket, "connect", fail_network_call)
    monkeypatch.setattr(urllib.request, "urlopen", fail_network_call)

    try:
        import requests
    except ImportError:  # pragma: no cover - optional dependency guard
        requests = None
    if requests is not None:
        monkeypatch.setattr(requests.sessions.Session, "request", fail_network_call)

    try:
        import httpx
    except ImportError:  # pragma: no cover - optional dependency guard
        httpx = None
    if httpx is not None:
        monkeypatch.setattr(httpx.Client, "request", fail_network_call)
        monkeypatch.setattr(httpx.AsyncClient, "request", fail_network_call)


def slb_parity_pass_row() -> dict:
    return {
        "dataset": "paid_meta_ads",
        "widget_id": "paid_summary",
        "metric": "spend",
        "label": "Spend",
        "adinsights_value": 100,
        "source_value": 100,
        "absolute_delta": 0,
        "absolute_delta_magnitude": 0,
        "percentage_delta": 0,
        "accepted_tolerance_percent": 1,
        "result": "pass",
        "explanation": "DashThis fixed-range value matched stored aggregate spend.",
    }


def slb_source_health_pass() -> dict:
    return {
        "schema_version": "slb_source_health.v1",
        "stored_aggregate_only": True,
        "no_live_provider_calls": True,
        "meta_credentials": {
            "credential_count": 1,
            "token_status_counts": {"valid": 1},
            "has_valid_credential": True,
            "has_reauth_required": False,
            "required_scope_coverage": {
                "present": [
                    "ads_read",
                    "business_management",
                    "pages_read_engagement",
                    "pages_show_list",
                ],
                "missing": [],
            },
            "latest_validated_at": "2026-06-16T10:00:00Z",
            "latest_expires_at": "2026-08-16T10:00:00Z",
        },
        "meta_page_connection": {
            "connection_count": 1,
            "active_count": 1,
            "inactive_count": 0,
            "has_active_connection": True,
            "required_scope_coverage": {
                "present": ["pages_read_engagement", "pages_show_list"],
                "missing": [],
            },
            "latest_token_expires_at": None,
        },
        "meta_airbyte": {
            "connection_count": 1,
            "active_count": 1,
            "inactive_count": 0,
            "last_job_status_counts": {"succeeded": 1},
            "latest_synced_at": "2026-06-16T10:00:00Z",
            "latest_completed_at": "2026-06-16T10:00:00Z",
            "sanitized_error_categories": {},
        },
        "stored_assets": {
            "ad_account_count": 1,
            "meta_page_count": 1,
            "analyzable_page_count": 1,
            "selected_default_page_count": 1,
        },
        "stored_rows": {
            "paid_meta_ads": {"row_count": 31, "min_date": "2026-05-01", "max_date": "2026-05-31"},
            "organic_facebook_page": {
                "row_count": 31,
                "min_date": "2026-05-01",
                "max_date": "2026-05-31",
            },
            "organic_facebook_posts": {
                "row_count": 10,
                "post_count": 5,
                "min_date": "2026-05-01",
                "max_date": "2026-05-31",
            },
            "content_ops": {
                "row_count": 4,
                "published_post_count": 4,
                "min_date": "2026-05-01",
                "max_date": "2026-05-31",
            },
            "warehouse_snapshots": [
                {
                    "source": "warehouse",
                    "generated_at": "2026-06-16T10:00:00Z",
                    "campaign_row_count": 31,
                    "campaign_trend_count": 31,
                    "has_summary": True,
                }
            ],
        },
        "recommended_next_actions": [
            "Run fixed-range evidence bundle, export, parity, and adversarial checks."
        ],
    }


def seed_paid_report_snapshot(*, tenant: Tenant) -> TenantMetricsSnapshot:
    return TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "summary": {
                    "totalSpend": 100,
                    "totalImpressions": 1000,
                    "totalReach": 750,
                    "totalClicks": 50,
                },
                "trend": [
                    {"date": "2026-03-01", "spend": 40, "clicks": 20},
                    {"date": "2026-03-31", "spend": 60, "clicks": 30},
                ],
                "rows": [
                    {
                        "date": "2026-03-01",
                        "campaign": "SLB Awareness",
                        "spend": 40,
                        "impressions": 400,
                        "reach": 300,
                        "clicks": 20,
                    },
                    {
                        "date": "2026-03-31",
                        "campaign": "SLB Conversion",
                        "spend": 60,
                        "impressions": 600,
                        "reach": 450,
                        "clicks": 30,
                    },
                ],
            }
        },
    )


def paid_report_v1_layout() -> dict:
    return {
        "schema_version": "report.v1",
        "template_key": "slb_monthly_social_report",
        "catalog_schema_version": "reporting_catalog.v1",
        "pages": [
            {
                "id": "paid_meta_ads",
                "title": "Paid Meta Ads performance",
                "sections": [
                    {
                        "id": "paid_meta_ads_widgets",
                        "type": "widget_group",
                        "widget_ids": ["paid_summary"],
                    }
                ],
            }
        ],
        "widgets": [
            {
                "id": "paid_summary",
                "type": "kpi",
                "dataset": "paid_meta_ads",
                "metrics": ["spend", "impressions", "reach", "clicks"],
                "dimensions": [],
                "filters": {
                    "date_range": "custom",
                    "start_date": "2026-03-01",
                    "end_date": "2026-03-31",
                },
                "coverage_policy": "render_with_warning",
                "visual": {"title": "Paid summary", "source_labels": True},
            }
        ],
    }


def create_viewer(*, tenant: Tenant, email: str) -> User:
    return create_user_with_role(tenant=tenant, email=email, role_name=Role.VIEWER)


def create_user_with_role(*, tenant: Tenant, email: str, role_name: str) -> User:
    seed_default_roles()
    user = User.objects.create_user(
        username=email,
        email=email,
        tenant=tenant,
        password="password123",
    )
    assign_role(user, role_name)
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


def test_report_create_update_audit_events_store_field_names_only(api_client, user, tenant):
    authenticate(api_client, user)

    create_payload = {
        "name": "Weekly performance pack",
        "description": "Executive weekly KPI rollup",
        "filters": {"range": "last_7_days", "channel": ["META", "GOOGLE"]},
        "layout": {"widgets": ["campaign_summary", "budget_pacing"]},
        "delivery_emails": ["ops@example.com"],
        "is_active": True,
    }
    create_response = api_client.post(
        reverse("report-definition-list"),
        create_payload,
        format="json",
    )
    assert create_response.status_code == 201
    report_id = create_response.json()["id"]

    update_payload = {
        "description": "Updated executive copy",
        "layout": {"widgets": ["campaign_summary"]},
        "delivery_emails": ["ops@example.com"],
    }
    update_response = api_client.patch(
        reverse("report-definition-detail", args=[report_id]),
        update_payload,
        format="json",
    )
    assert update_response.status_code == 200

    create_event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_created",
        resource_type="report_definition",
        resource_id=report_id,
    )
    update_event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_updated",
        resource_type="report_definition",
        resource_id=report_id,
    )

    assert_report_mutation_audit_metadata_is_redacted(
        create_event.metadata,
        expected_fields=[
            "delivery_emails",
            "description",
            "filters",
            "is_active",
            "layout",
            "name",
        ],
    )
    assert_report_mutation_audit_metadata_is_redacted(
        update_event.metadata,
        expected_fields=["delivery_emails", "description", "layout"],
    )


def test_create_slb_monthly_report_template(api_client, user, tenant):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("report-definition-slb-monthly-template"),
        {"name": "SLB June report", "date_range": "last_month"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "SLB June report"
    assert payload["layout"]["schema_version"] == "report.v1"
    assert payload["layout"]["template_key"] == "slb_monthly_social_report"
    widget_datasets = {widget["dataset"] for widget in payload["layout"]["widgets"]}
    assert {"paid_meta_ads", "organic_facebook_page", "content_ops"} <= widget_datasets
    assert "organic_instagram" not in widget_datasets
    page_ids = {page["id"] for page in payload["layout"]["pages"]}
    assert "appendix" in page_ids
    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="report_template_created",
        resource_type="report_definition",
    ).exists()


def test_report_template_registry_and_generic_create_path(api_client, user):
    authenticate(api_client, user)

    registry_response = api_client.get(reverse("report-definition-templates"))

    assert registry_response.status_code == 200
    registry_payload = registry_response.json()
    assert registry_payload["schema_version"] == "report_template_registry.v1"
    assert registry_payload["templates"][0]["template_key"] == "slb_monthly_social_report"
    assert registry_payload["templates"][0]["supported_datasets"] == [
        "paid_meta_ads",
        "organic_facebook_page",
        "content_ops",
    ]

    create_response = api_client.post(
        reverse("report-definition-from-template"),
        {
            "template_key": "slb_monthly_social_report",
            "name": "Generic SLB report",
            "date_range": "last_month",
        },
        format="json",
    )

    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["name"] == "Generic SLB report"
    assert payload["layout"]["template_key"] == "slb_monthly_social_report"


def test_report_v1_layout_validation_rejects_unknown_widget_reference(api_client, user):
    authenticate(api_client, user)
    layout = build_slb_monthly_report_layout(date_range="last_month")
    layout["pages"][0]["sections"][0]["widget_ids"] = ["missing_widget"]

    response = api_client.post(
        reverse("report-definition-list"),
        {
            "name": "Invalid SLB report",
            "description": "Bad widget reference",
            "filters": {"date_range": "last_month"},
            "layout": layout,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "references unknown widget 'missing_widget'" in str(response.json())


def test_report_preview_returns_ordered_report_v1_pages(api_client, user, tenant):
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB preview",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    response = api_client.post(reverse("report-definition-preview", args=[report.id]), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["schema_version"] == "report.v1"
    assert payload["pages"][0]["id"] == "cover"
    assert payload["pages"][-1]["id"] == "appendix"
    assert payload["coverage_summary"]["by_status"]
    assert payload["export_ready"] is False
    assert any("content_ops" in reason and "missing_history" in reason for reason in payload["blocking_reasons"])
    assert any(
        "organic_facebook_page" in reason and "missing_history" in reason
        for reason in payload["blocking_reasons"]
    )
    datasets = {row["dataset"] for row in payload["coverage_summary"]["datasets"]}
    assert {"paid_meta_ads", "organic_facebook_page", "content_ops"} <= datasets
    content_ops_coverage = next(
        row for row in payload["coverage_summary"]["datasets"] if row["dataset"] == "content_ops"
    )
    assert content_ops_coverage["row_count"] == 0
    assert content_ops_coverage["covered_start_date"] is None
    assert content_ops_coverage["covered_end_date"] is None
    assert content_ops_coverage["statuses"] == {"missing_history": 1}


def test_report_preview_marks_require_full_coverage_widget_blocked(api_client, user, tenant):
    authenticate(api_client, user)
    layout = build_slb_monthly_report_layout(date_range="last_month")
    layout["widgets"][1]["coverage_policy"] = "require_full_coverage"
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB blocked preview",
        filters={"date_range": "last_month"},
        layout=layout,
    )

    response = api_client.post(reverse("report-definition-preview", args=[report.id]), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["export_ready"] is False
    assert any("require_full_coverage" in reason for reason in payload["blocking_reasons"])
    blocked_widgets = [
        widget
        for page in payload["pages"]
        for section in page["sections"]
        for widget in section["widgets"]
        if widget["status"] == "blocked"
    ]
    assert blocked_widgets


def test_report_v1_export_stores_preview_metadata(api_client, user, tenant, monkeypatch):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB export metadata",
        filters={"date_range": "custom", "start_date": "2026-03-01", "end_date": "2026-03-31"},
        layout=paid_report_v1_layout(),
    )
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)

    response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["metadata"]["report_preview"]["report_schema_version"] == "report.v1"
    assert payload["metadata"]["report_preview"]["template_key"] == "slb_monthly_social_report"
    assert payload["metadata"]["report_preview"]["preview_hash"]
    assert payload["metadata"]["report_preview"]["coverage_summary"]["by_status"]
    assert payload["metadata"]["report_preview"]["report_snapshot"]["pages"][0]["id"] == "paid_meta_ads"
    assert (
        payload["metadata"]["report_preview"]["report_snapshot"]["preview_hash"]
        == payload["metadata"]["report_preview"]["preview_hash"]
    )


@pytest.mark.parametrize(
    "export_format",
    [ReportExportJob.FORMAT_CSV, ReportExportJob.FORMAT_PDF, ReportExportJob.FORMAT_PNG],
)
def test_report_v1_completed_export_preserves_preview_snapshot_hash(
    api_client, user, tenant, tmp_path, monkeypatch, export_format
):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB export reproducibility",
        filters={"date_range": "custom", "start_date": "2026-03-01", "end_date": "2026-03-31"},
        layout=paid_report_v1_layout(),
    )
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant",
        lambda tenant_id: (
            {"campaign": {"summary": {}, "rows": []}},
            timezone.now(),
            "fetched",
        ),
    )

    preview_response = api_client.post(
        reverse("report-definition-preview", args=[report.id]),
        {},
        format="json",
    )
    export_response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": export_format},
        format="json",
    )
    job_id = export_response.json()["id"]

    if export_format in {ReportExportJob.FORMAT_PDF, ReportExportJob.FORMAT_PNG}:

        def fake_render(command, **_kwargs):
            pdf_path = command[command.index("--out") + 1]
            png_path = command[command.index("--png") + 1]
            Path(pdf_path).write_bytes(b"pdf artifact")
            Path(png_path).write_bytes(b"png artifact")

        monkeypatch.setattr("analytics.tasks.subprocess.run", fake_render)

    result = run_report_export_job.run(job_id)

    job = ReportExportJob.all_objects.get(id=job_id)
    artifact = tmp_path / job.artifact_path.lstrip("/")
    report_preview = job.metadata["report_preview"]
    assert preview_response.status_code == 200
    assert export_response.status_code == 201
    assert result["status"] == ReportExportJob.STATUS_COMPLETED
    assert artifact.exists()
    assert artifact.stat().st_size > 0
    assert report_preview["preview_hash"] == preview_response.json()["preview_hash"]
    assert report_preview["report_snapshot"]["preview_hash"] == preview_response.json()["preview_hash"]
    assert report_preview["report_snapshot"]["pages"][0]["id"] == "paid_meta_ads"


def test_report_diagnostics_returns_aggregate_dataset_status(api_client, user, tenant):
    authenticate(api_client, user)
    generated_at = timezone.now()
    PlatformCredential.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        access_token_enc=b"encrypted",
        access_token_nonce=b"nonce",
        access_token_tag=b"tag",
        dek_key_version="test",
        token_status=PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
        token_status_reason="Raw Meta debug_token error should not be exposed.",
        granted_scopes=["ads_read", "pages_show_list"],
        last_validated_at=generated_at,
    )
    AirbyteConnection.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        name="Meta destination",
        connection_id=uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        is_active=True,
        last_job_status="failed",
        last_job_error="Connection to host.docker.internal:5435 refused. Raw path should not leak.",
    )
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=generated_at,
        payload={
            "campaign": {
                "summary": {"totalSpend": 1200, "totalClicks": 80},
                "trend": [{"date": "2026-05-31", "spend": 1200, "clicks": 80}],
                "rows": [{"date": "2026-05-31", "campaign": "SLB Awareness", "spend": 1200}],
            }
        },
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB diagnostics",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )
    ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_PDF,
        metadata={
            "preview_hash": "hash-1",
            "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
        },
    )

    response = api_client.get(reverse("report-definition-diagnostics", args=[report.id]))

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["schema_version"] == "report.v1"
    assert payload["preview_hash"]
    assert {row["dataset"] for row in payload["datasets"]} >= {
        "paid_meta_ads",
        "organic_facebook_page",
        "content_ops",
    }
    paid_diagnostics = next(row for row in payload["datasets"] if row["dataset"] == "paid_meta_ads")
    assert paid_diagnostics["last_successful_sync_at"] == generated_at.isoformat()
    content_ops_diagnostics = next(row for row in payload["datasets"] if row["dataset"] == "content_ops")
    assert content_ops_diagnostics["coverage_status"] == "missing_history"
    assert content_ops_diagnostics["row_count"] == 0
    assert content_ops_diagnostics["retained_range"] == {"start_date": None, "end_date": None}
    assert payload["source_health"]["stored_aggregate_only"] is True
    assert payload["source_health"]["no_live_provider_calls"] is True
    assert payload["source_health"]["meta_credentials"]["has_reauth_required"] is True
    assert payload["source_health"]["meta_airbyte"]["sanitized_error_categories"] == {
        "destination_connection_refused": 1
    }
    assert "Reconnect Meta OAuth credentials" in " ".join(
        payload["source_health"]["recommended_next_actions"]
    )
    assert_report_payload_excludes_sensitive_values(payload)
    serialized_payload = json.dumps(payload, default=str).lower()
    assert "host.docker.internal" not in serialized_payload
    assert "debug_token" not in serialized_payload
    assert "act_123" not in serialized_payload
    assert payload["export_history"][0]["delivery_status"] == "rendered"
    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="report_diagnostics_viewed",
        resource_type="report_definition",
    ).exists()


def test_report_diagnostics_prefers_valid_meta_credential_over_stale_reauth_records(
    api_client, user, tenant
):
    authenticate(api_client, user)
    generated_at = timezone.now()
    PlatformCredential.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_current",
        access_token_enc=b"encrypted",
        access_token_nonce=b"nonce",
        access_token_tag=b"tag",
        dek_key_version="test",
        token_status=PlatformCredential.TOKEN_STATUS_VALID,
        granted_scopes=[
            "ads_read",
            "business_management",
            "pages_read_engagement",
            "pages_show_list",
        ],
        last_validated_at=generated_at,
    )
    PlatformCredential.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_stale",
        access_token_enc=b"encrypted",
        access_token_nonce=b"nonce",
        access_token_tag=b"tag",
        dek_key_version="test",
        token_status=PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
        token_status_reason="Raw Meta debug_token error should not be exposed.",
        granted_scopes=["ads_read", "pages_show_list"],
        last_validated_at=generated_at - timedelta(days=1),
    )
    meta_connection = MetaConnection.objects.create(
        tenant=tenant,
        user=user,
        app_scoped_user_id="app-user-current",
        token_enc=b"encrypted",
        token_nonce=b"nonce",
        token_tag=b"tag",
        dek_key_version="test",
        scopes=["pages_read_engagement", "pages_show_list"],
        is_active=True,
    )
    current_page = MetaPage(
        tenant=tenant,
        connection=meta_connection,
        page_id="page-current",
        name="Current Page",
        can_analyze=True,
        is_default=True,
    )
    current_page.set_raw_page_token("page-token-current")
    current_page.save()
    MetaPage.objects.create(
        tenant=tenant,
        connection=meta_connection,
        page_id="page-stale",
        name="Stale Page",
        page_token_enc=b"encrypted",
        page_token_nonce=b"nonce",
        page_token_tag=b"tag",
        dek_key_version="test",
        can_analyze=True,
        is_default=False,
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB diagnostics current credential",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    response = api_client.get(reverse("report-definition-diagnostics", args=[report.id]))

    assert response.status_code == 200
    source_health = response.json()["source_health"]
    assert source_health["meta_credentials"]["has_valid_credential"] is True
    assert source_health["meta_credentials"]["has_reauth_required"] is True
    assert source_health["meta_page_connection"]["has_usable_page_auth"] is True
    actions = " ".join(source_health["recommended_next_actions"])
    assert "Reconnect Meta OAuth credentials" not in actions
    assert "Reconnect/select the Facebook Page" not in actions
    assert "Backfill Facebook Page Insights stored rows" in actions
    assert "Backfill Facebook post insight rows" in actions


def test_report_diagnostics_explains_empty_graph_page_insights_after_sync(
    api_client, user, tenant
):
    authenticate(api_client, user)
    generated_at = timezone.now()
    PlatformCredential.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_current",
        access_token_enc=b"encrypted",
        access_token_nonce=b"nonce",
        access_token_tag=b"tag",
        dek_key_version="test",
        token_status=PlatformCredential.TOKEN_STATUS_VALID,
        granted_scopes=[
            "ads_read",
            "business_management",
            "pages_read_engagement",
            "pages_show_list",
        ],
        last_validated_at=generated_at,
    )
    meta_connection = MetaConnection.objects.create(
        tenant=tenant,
        user=user,
        app_scoped_user_id="app-user-current",
        token_enc=b"encrypted",
        token_nonce=b"nonce",
        token_tag=b"tag",
        dek_key_version="test",
        scopes=["pages_read_engagement", "pages_show_list"],
        is_active=True,
    )
    current_page = MetaPage(
        tenant=tenant,
        connection=meta_connection,
        page_id="page-current",
        name="Current Page",
        can_analyze=True,
        is_default=True,
        last_synced_at=generated_at,
        last_posts_synced_at=generated_at,
    )
    current_page.set_raw_page_token("page-token-current")
    current_page.save()
    MetaPost.objects.create(
        tenant=tenant,
        page=current_page,
        post_id="page-current_1",
        created_time=generated_at,
        last_synced_at=generated_at,
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB diagnostics synced empty organic",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    response = api_client.get(reverse("report-definition-diagnostics", args=[report.id]))

    assert response.status_code == 200
    actions = " ".join(response.json()["source_health"]["recommended_next_actions"])
    assert "Meta Page Insights sync has run, but Graph returned no Page insight metric rows" in actions
    assert "Backfill Facebook Page Insights stored rows" not in actions
    assert "Facebook posts are stored, but Meta returned no post insight metric rows" in actions


def test_scheduled_report_dry_run_creates_sanitized_export_evidence(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB scheduled dry-run",
        filters={"date_range": "custom", "start_date": "2026-03-01", "end_date": "2026-03-31"},
        layout=paid_report_v1_layout(),
        schedule_enabled=True,
        delivery_emails=["ops@example.com"],
    )
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)

    response = api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report.id]),
        {"export_format": "pdf"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == ReportExportJob.STATUS_QUEUED
    assert payload["metadata"]["delivery_status"]["mode"] == "dry_run"
    assert payload["metadata"]["report_preview"]["report_snapshot"]["preview_hash"]
    report.refresh_from_db()
    assert report.last_scheduled_at is not None
    assert AuditLog.all_objects.filter(
        tenant=tenant,
        action="report_scheduled_dry_run_requested",
        resource_type="report_export_job",
    ).exists()


def test_scheduled_report_dry_run_completion_marks_rendered_without_email(
    api_client, user, tenant, tmp_path, monkeypatch
):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB scheduled rendered dry-run",
        filters={"date_range": "custom", "start_date": "2026-03-01", "end_date": "2026-03-31"},
        layout=paid_report_v1_layout(),
        schedule_enabled=True,
        delivery_emails=["ops@example.com"],
    )
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant",
        lambda tenant_id: (
            {"campaign": {"summary": {}, "rows": []}},
            timezone.now(),
            "fetched",
        ),
    )

    def fail_email_send(*_args, **_kwargs):
        raise AssertionError("scheduled report dry-run must not send client email")

    monkeypatch.setattr("analytics.tasks.send_daily_summary_email", fail_email_send)

    response = api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )
    job_id = response.json()["id"]

    result = run_report_export_job.run(job_id)

    job = ReportExportJob.all_objects.get(id=job_id)
    artifact = tmp_path / job.artifact_path.lstrip("/")
    delivery_status = job.metadata["delivery_status"]
    serialized_metadata = json.dumps(job.metadata, default=str).lower()
    assert response.status_code == 201
    assert result["status"] == ReportExportJob.STATUS_COMPLETED
    assert job.status == ReportExportJob.STATUS_COMPLETED
    assert artifact.exists()
    assert artifact.stat().st_size > 0
    assert delivery_status["mode"] == "dry_run"
    assert delivery_status["status"] == "rendered"
    assert delivery_status["sanitized"] is True
    assert delivery_status["rendered_at"]
    assert "ops@example.com" not in serialized_metadata
    assert "delivery_emails" not in serialized_metadata


def test_scheduled_report_dry_run_blocks_by_coverage_without_enqueueing_export(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    layout = build_slb_monthly_report_layout(date_range="last_month")
    layout["widgets"][1]["coverage_policy"] = "require_full_coverage"
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB scheduled blocked dry-run",
        filters={"date_range": "last_month"},
        layout=layout,
        schedule_enabled=True,
        delivery_emails=["ops@example.com"],
    )

    def fail_export_enqueue(*_args, **_kwargs):
        raise AssertionError("coverage-blocked dry-run must not enqueue export rendering")

    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", fail_export_enqueue)

    response = api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report.id]),
        {"export_format": "pdf"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    serialized_metadata = json.dumps(payload["metadata"], default=str).lower()
    assert payload["status"] == ReportExportJob.STATUS_FAILED
    assert payload["error_message"] == "Scheduled dry-run blocked by coverage."
    assert payload["artifact_path"] == ""
    assert payload["metadata"]["delivery_status"] == {
        "mode": "dry_run",
        "status": "blocked_by_coverage",
        "sanitized": True,
    }
    assert any("require_full_coverage" in reason for reason in payload["metadata"]["blocking_reasons"])
    assert "ops@example.com" not in serialized_metadata
    assert "delivery_emails" not in serialized_metadata
    report.refresh_from_db()
    assert report.last_scheduled_at is not None


def test_report_preview_export_diagnostics_dry_run_and_parity_outputs_are_redacted(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB redaction surface",
        description="super-secret-value should not appear in report outputs",
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "access_token": "secret-token-value",
            "raw_payload": "raw-provider-payload",
        },
        layout=paid_report_v1_layout(),
        schedule_enabled=True,
        delivery_emails=["ops@example.com", "recipient@example.com"],
    )
    ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_PDF,
        metadata={
            "report_preview": {
                "preview_hash": "hash-unsafe",
                "blocking_reasons": [],
                "report_snapshot": {
                    "access_token": "secret-token-value",
                    "raw_payload": "raw-provider-payload",
                    "user_id": "user-1",
                },
            },
            "delivery_status": {
                "mode": "dry_run",
                "status": "rendered",
                "recipient": "ops@example.com",
            },
        },
    )

    preview_response = api_client.post(
        reverse("report-definition-preview", args=[report.id]),
        {},
        format="json",
    )
    diagnostics_response = api_client.get(reverse("report-definition-diagnostics", args=[report.id]))
    export_response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )
    dry_run_response = api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report.id]),
        {"export_format": "pdf"},
        format="json",
    )
    parity_output = StringIO()
    call_command(
        "slb_report_parity_evidence",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=parity_output,
    )
    evidence_bundle_output = StringIO()
    call_command(
        "slb_report_evidence_bundle",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=evidence_bundle_output,
    )

    assert preview_response.status_code == 200
    assert diagnostics_response.status_code == 200
    assert export_response.status_code == 201
    assert dry_run_response.status_code == 201
    assert_report_payload_excludes_sensitive_values(preview_response.json())
    assert_report_payload_excludes_sensitive_values(diagnostics_response.json())
    assert_report_payload_excludes_sensitive_values(export_response.json()["metadata"])
    assert_report_payload_excludes_sensitive_values(dry_run_response.json()["metadata"])
    assert_report_payload_excludes_sensitive_values(json.loads(parity_output.getvalue()))
    assert_report_payload_excludes_sensitive_values(json.loads(evidence_bundle_output.getvalue()))
    assert export_response.json()["metadata"]["report_preview"]["report_snapshot"]["pages"]
    assert dry_run_response.json()["metadata"]["delivery_status"] == {
        "mode": "dry_run",
        "status": "queued",
        "sanitized": True,
    }


def test_report_preview_export_dry_run_and_parity_do_not_call_live_providers(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)
    seed_paid_report_snapshot(tenant=tenant)
    block_live_network_calls(monkeypatch)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB stored-data-only report",
        filters={"date_range": "custom", "start_date": "2026-03-01", "end_date": "2026-03-31"},
        layout=paid_report_v1_layout(),
        schedule_enabled=True,
    )

    preview_response = api_client.post(
        reverse("report-definition-preview", args=[report.id]),
        {},
        format="json",
    )
    export_response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )
    dry_run_response = api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report.id]),
        {"export_format": "pdf"},
        format="json",
    )
    parity_output = StringIO()
    call_command(
        "slb_report_parity_evidence",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=parity_output,
    )
    evidence_bundle_output = StringIO()
    call_command(
        "slb_report_evidence_bundle",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=evidence_bundle_output,
    )

    assert preview_response.status_code == 200
    assert export_response.status_code == 201
    assert dry_run_response.status_code == 201
    assert preview_response.json()["preview_hash"]
    assert export_response.json()["metadata"]["report_preview"]["report_snapshot"]["pages"]
    assert dry_run_response.json()["metadata"]["report_preview"]["report_snapshot"]["pages"]
    assert json.loads(parity_output.getvalue())["rows"]
    assert json.loads(evidence_bundle_output.getvalue())["parity_rows"]


@pytest.mark.parametrize(
    ("route_name", "payload", "expected_message"),
    [
        ("report-definition-preview", {}, "Report preview quota exceeded"),
        ("report-definition-exports", {"export_format": "csv"}, "Report export quota exceeded"),
        (
            "report-definition-scheduled-dry-run",
            {"export_format": "pdf"},
            "Scheduled report dry-run quota exceeded",
        ),
    ],
)
def test_report_actions_return_sanitized_quota_blocks(
    api_client, user, tenant, monkeypatch, route_name, payload, expected_message
):
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB quota block",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )
    monkeypatch.setattr("analytics.phase2_views._check_report_action_quota", lambda **_kwargs: (False, 999))

    response = api_client.post(reverse(route_name, args=[report.id]), payload, format="json")

    assert response.status_code == 429
    serialized = str(response.json())
    assert expected_message in serialized
    assert "999" in serialized
    assert "traceback" not in serialized.lower()
    assert "select " not in serialized.lower()
    assert "access_token" not in serialized.lower()
    assert "secret" not in serialized.lower()


def test_report_privileges_allow_viewer_read_but_block_export(api_client, tenant):
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="Viewer report",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )
    viewer = create_viewer(tenant=tenant, email="viewer@example.com")
    authenticate(api_client, viewer)

    detail_response = api_client.get(reverse("report-definition-detail", args=[report.id]))
    export_response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )

    assert detail_response.status_code == 200
    assert export_response.status_code == 403


def test_report_privileges_separate_view_preview_export_edit_schedule_delete(
    api_client, tenant, monkeypatch
):
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="Role-separated SLB report",
        filters={"date_range": "custom", "start_date": "2026-03-01", "end_date": "2026-03-31"},
        layout=paid_report_v1_layout(),
    )

    viewer = create_viewer(tenant=tenant, email="viewer2@example.com")
    authenticate(api_client, viewer)

    assert api_client.get(reverse("report-definition-detail", args=[report.id])).status_code == 200
    assert api_client.get(reverse("report-definition-exports", args=[report.id])).status_code == 200
    assert api_client.post(reverse("report-definition-preview", args=[report.id]), {}, format="json").status_code == 403
    assert api_client.get(reverse("report-definition-diagnostics", args=[report.id])).status_code == 403
    assert api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    ).status_code == 403
    assert api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report.id]),
        {"export_format": "pdf"},
        format="json",
    ).status_code == 403
    assert api_client.post(
        reverse("report-definition-toggle-schedule", args=[report.id]),
        {"enabled": True},
        format="json",
    ).status_code == 403
    assert api_client.patch(
        reverse("report-definition-detail", args=[report.id]),
        {"description": "viewer should not edit"},
        format="json",
    ).status_code == 403
    assert api_client.delete(reverse("report-definition-detail", args=[report.id])).status_code == 403

    analyst = create_user_with_role(tenant=tenant, email="analyst@example.com", role_name=Role.ANALYST)
    authenticate(api_client, analyst)

    assert api_client.post(reverse("report-definition-preview", args=[report.id]), {}, format="json").status_code == 200
    assert api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    ).status_code == 201
    assert api_client.patch(
        reverse("report-definition-detail", args=[report.id]),
        {"description": "analyst edit allowed"},
        format="json",
    ).status_code == 200
    assert api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report.id]),
        {"export_format": "pdf"},
        format="json",
    ).status_code == 403
    assert api_client.delete(reverse("report-definition-detail", args=[report.id])).status_code == 403


def test_report_admin_schedule_and_delete_are_audited_with_redacted_metadata(api_client, user, tenant):
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="Admin audited report",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    schedule_response = api_client.post(
        reverse("report-definition-toggle-schedule", args=[report.id]),
        {"enabled": True},
        format="json",
    )
    delete_response = api_client.delete(reverse("report-definition-detail", args=[report.id]))

    assert schedule_response.status_code == 200
    assert schedule_response.json()["schedule_enabled"] is True
    assert delete_response.status_code == 204
    schedule_event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_schedule_toggled",
        resource_type="report_definition",
        resource_id=report.id,
    )
    delete_event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_deleted",
        resource_type="report_definition",
        resource_id=report.id,
    )
    assert schedule_event.metadata == {"schedule_enabled": True}
    assert delete_event.metadata == {"fields": [], "redacted": True}
    assert "layout" not in str(schedule_event.metadata)
    assert "layout" not in str(delete_event.metadata)


def test_report_workflow_audit_events_store_only_redacted_metadata(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    monkeypatch.setattr("analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None)
    seed_paid_report_snapshot(tenant=tenant)

    template_response = api_client.post(
        reverse("report-definition-slb-monthly-template"),
        {
            "name": "Audited SLB workflow",
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        format="json",
    )
    assert template_response.status_code == 201
    report_id = template_response.json()["id"]
    report = ReportDefinition.objects.get(id=report_id)
    report.filters = {"date_range": "custom", "start_date": "2026-03-01", "end_date": "2026-03-31"}
    report.layout = paid_report_v1_layout()
    report.delivery_emails = ["ops@example.com"]
    report.schedule_enabled = True
    report.save(update_fields=["filters", "layout", "delivery_emails", "schedule_enabled", "updated_at"])

    preview_response = api_client.post(
        reverse("report-definition-preview", args=[report_id]),
        {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        format="json",
    )
    diagnostics_response = api_client.get(reverse("report-definition-diagnostics", args=[report_id]))
    export_response = api_client.post(
        reverse("report-definition-exports", args=[report_id]),
        {"export_format": "csv"},
        format="json",
    )
    dry_run_response = api_client.post(
        reverse("report-definition-scheduled-dry-run", args=[report_id]),
        {"export_format": "pdf"},
        format="json",
    )

    assert preview_response.status_code == 200
    assert diagnostics_response.status_code == 200
    assert export_response.status_code == 201
    assert dry_run_response.status_code == 201

    blocked_layout = build_slb_monthly_report_layout(date_range="last_month")
    blocked_layout["widgets"][1]["coverage_policy"] = "require_full_coverage"
    blocked_report = ReportDefinition.objects.create(
        tenant=tenant,
        name="Audited blocked SLB export",
        filters={"date_range": "last_month"},
        layout=blocked_layout,
    )
    blocked_response = api_client.post(
        reverse("report-definition-exports", args=[blocked_report.id]),
        {"export_format": "png"},
        format="json",
    )
    assert blocked_response.status_code == 409

    expected_events = {
        "report_template_created": {"template_key", "fields", "redacted"},
        "report_previewed": {"schema_version", "export_ready", "preview_hash", "redacted"},
        "report_diagnostics_viewed": {"schema_version", "export_ready", "redacted"},
        "report_export_requested": {"fields", "report_id", "redacted"},
        "report_scheduled_dry_run_requested": {
            "delivery_status",
            "export_format",
            "report_id",
            "redacted",
        },
    }
    for action, expected_keys in expected_events.items():
        event = (
            AuditLog.all_objects.filter(tenant=tenant, action=action)
            .order_by("-created_at")
            .first()
        )
        assert event is not None
        assert set(event.metadata.keys()) == expected_keys
        assert_redacted_report_audit_metadata(event.metadata)

    blocked_event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_export_blocked",
        resource_type="report_definition",
        resource_id=blocked_report.id,
    )
    assert set(blocked_event.metadata.keys()) == {
        "blocking_reasons",
        "export_format",
        "redacted",
    }
    assert_redacted_report_audit_metadata(
        blocked_event.metadata,
        allow_blocking_reason_details=True,
    )


@pytest.mark.parametrize(
    ("method", "route_name", "payload"),
    [
        ("get", "report-definition-detail", None),
        ("post", "report-definition-preview", {}),
        ("get", "report-definition-diagnostics", None),
        ("get", "report-definition-exports", None),
        ("post", "report-definition-exports", {"export_format": "csv"}),
        ("post", "report-definition-scheduled-dry-run", {"export_format": "pdf"}),
        ("post", "report-definition-toggle-schedule", {"enabled": True}),
        ("patch", "report-definition-detail", {"description": "cross tenant edit"}),
        ("delete", "report-definition-detail", None),
    ],
)
def test_report_actions_reject_cross_tenant_report_ids(
    api_client, user, method, route_name, payload
):
    other_tenant = Tenant.objects.create(name="Other Report Tenant")
    other_report = ReportDefinition.objects.create(
        tenant=other_tenant,
        name="Other tenant SLB report",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )
    authenticate(api_client, user)

    request = getattr(api_client, method)
    if payload is None:
        response = request(reverse(route_name, args=[other_report.id]))
    else:
        response = request(reverse(route_name, args=[other_report.id]), payload, format="json")

    assert response.status_code == 404
    assert str(other_report.id) not in str(response.json() if hasattr(response, "json") else "")


def test_report_export_history_filters_mismatched_tenant_jobs(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Other Export History Tenant")
    authenticate(api_client, user)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="Tenant-scoped export history report",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )
    own_job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
    )
    mismatched_job = ReportExportJob.objects.create(
        tenant=other_tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_PDF,
    )

    response = api_client.get(reverse("report-definition-exports", args=[report.id]))

    assert response.status_code == 200
    job_ids = {row["id"] for row in response.json()}
    assert str(own_job.id) in job_ids
    assert str(mismatched_job.id) not in job_ids


def test_slb_report_parity_evidence_command_outputs_manual_comparison_rows(tenant):
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB parity",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )
    output = StringIO()

    call_command(
        "slb_report_parity_evidence",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["report_id"] == str(report.id)
    assert payload["date_range"]["start_date"] == "2026-05-01"
    assert payload["preview_hash"]
    assert payload["rows"]
    assert all(row["dashthis_value"] is None for row in payload["rows"])
    assert all(row["result"] == "blocked_missing_dashthis_value" for row in payload["rows"])
    assert not {
        "cover_period",
        "recommendations",
        "appendix_data_notes",
    } & {row["widget_id"] for row in payload["rows"]}
    event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_parity_evidence_generated",
        resource_type="report_definition",
        resource_id=report.id,
    )
    assert set(event.metadata.keys()) == {
        "end_date",
        "preview_hash",
        "redacted",
        "row_count",
        "start_date",
    }
    assert event.metadata["row_count"] == len(payload["rows"])
    assert_redacted_report_audit_metadata(event.metadata)


def test_slb_report_target_intake_command_outputs_redacted_g1_candidate(tenant, monkeypatch):
    block_live_network_calls(monkeypatch)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB target intake",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "client_id": "client-123",
            "account_id": "act_123",
            "page_id": "page-123",
            "workspace_id": "workspace-123",
            "access_token": "secret-token-value",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
        schedule_enabled=True,
        schedule_cron="0 8 1 * *",
        delivery_emails=["ops@example.com", "client@example.com"],
    )
    output = StringIO()

    call_command("slb_report_target_intake", "--report-id", str(report.id), stdout=output)

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_target_intake.v1"
    assert payload["status"] == "candidate_ready_for_operator_confirmation"
    assert payload["report"] == {
        "id": str(report.id),
        "tenant_id": str(tenant.id),
        "is_active": True,
        "schema_version": "report.v1",
        "template_key": "slb_monthly_social_report",
        "catalog_schema_version": "reporting_catalog.v1",
    }
    assert payload["date_range"]["report_filter"] == {
        "date_range": "custom",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }
    assert payload["source_scope_presence"] == {
        "client_id_present": True,
        "account_id_present": True,
        "page_id_present": True,
        "workspace_id_present": True,
        "delivery_recipient_count": 2,
    }
    assert payload["datasets"]["missing_required_active_v1"] == []
    assert payload["guardrails"]["report_v1"] is True
    assert payload["guardrails"]["slb_template"] is True
    assert payload["guardrails"]["instagram_deferred"] is True
    assert payload["guardrails"]["no_sensitive_patterns_detected"] is False
    assert payload["schedule"]["schedule_enabled"] is True
    assert payload["schedule"]["schedule_cron_present"] is True
    assert "raj_mira_g0_clearance" in payload["operator_fields_still_required"]
    assert_report_payload_excludes_sensitive_values(payload)


def test_slb_report_target_intake_command_flags_invalid_or_instagram_targets(tenant):
    layout = build_slb_monthly_report_layout(date_range="last_month")
    layout["widgets"].append(
        {
            "id": "instagram_reach",
            "type": "kpi",
            "dataset": "organic_instagram",
            "metrics": ["instagram_reach"],
            "dimensions": [],
            "filters": {"date_range": "last_month"},
            "coverage_policy": "render_with_warning",
            "visual": {"title": "Instagram Reach", "source_labels": True},
        }
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB invalid instagram target",
        filters={"date_range": "last_month"},
        layout=layout,
    )
    output = StringIO()

    call_command("slb_report_target_intake", "--report-id", str(report.id), stdout=output)

    payload = json.loads(output.getvalue())
    assert payload["status"] == "invalid_report_layout"
    assert payload["validation_errors"]
    assert "organic_instagram" in str(payload["validation_errors"])
    assert payload["guardrails"]["instagram_deferred"] is False


def test_slb_report_history_probe_command_outputs_monthly_and_90_day_matrix(
    tenant, user, monkeypatch
):
    block_live_network_calls(monkeypatch)
    generated_at = timezone.now()
    PlatformCredential.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        access_token_enc=b"encrypted",
        access_token_nonce=b"nonce",
        access_token_tag=b"tag",
        dek_key_version="test",
        token_status=PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
        token_status_reason="Raw Meta debug_token error should not be exposed.",
        granted_scopes=["ads_read", "pages_show_list"],
        last_validated_at=generated_at,
    )
    meta_connection = MetaConnection.objects.create(
        tenant=tenant,
        user=user,
        app_scoped_user_id="app-user-1",
        token_enc=b"encrypted",
        token_nonce=b"nonce",
        token_tag=b"tag",
        dek_key_version="test",
        scopes=["pages_show_list"],
        is_active=True,
    )
    MetaPage.objects.create(
        tenant=tenant,
        connection=meta_connection,
        page_id="page-1",
        name="SLB Page",
        page_token_enc=b"encrypted",
        page_token_nonce=b"nonce",
        page_token_tag=b"tag",
        dek_key_version="test",
        can_analyze=True,
        is_default=True,
    )
    AirbyteConnection.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        name="Meta destination",
        connection_id=uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        is_active=True,
        last_job_status="failed",
        last_job_error="Connection to host.docker.internal:5435 refused. Raw path should not leak.",
    )
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=generated_at,
        payload={
            "campaign": {
                "summary": {"totalSpend": 1200, "totalClicks": 80},
                "trend": [
                    {"date": "2026-03-15", "spend": 300, "clicks": 20},
                    {"date": "2026-05-31", "spend": 900, "clicks": 60},
                ],
                "rows": [
                    {"date": "2026-03-15", "campaign": "SLB March", "spend": 300},
                    {"date": "2026-05-31", "campaign": "SLB May", "spend": 900},
                ],
            }
        },
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB history probe",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "access_token": "secret-token-value",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
    )
    output = StringIO()

    call_command(
        "slb_report_history_probe",
        "--report-id",
        str(report.id),
        "--primary-start-date",
        "2026-05-01",
        "--primary-end-date",
        "2026-05-31",
        "--history-start-date",
        "2026-03-01",
        "--history-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_history_probe.v1"
    assert payload["probes"]["primary_month"]["date_range"] == {
        "date_range": "custom",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }
    assert payload["probes"]["retained_90_day"]["date_range"] == {
        "date_range": "custom",
        "start_date": "2026-03-01",
        "end_date": "2026-05-31",
    }
    matrix = {row["dataset"]: row for row in payload["dataset_matrix"]}
    assert set(matrix) == {"paid_meta_ads", "organic_facebook_page", "content_ops"}
    assert matrix["paid_meta_ads"]["primary_row_count"] > 0
    assert matrix["paid_meta_ads"]["history_row_count"] > 0
    assert matrix["organic_facebook_page"]["decision"] == "blocked_retained_history"
    assert matrix["content_ops"]["decision"] == "blocked_retained_history"
    source_health = payload["source_health"]
    assert source_health["stored_aggregate_only"] is True
    assert source_health["no_live_provider_calls"] is True
    assert source_health["meta_credentials"]["credential_count"] == 1
    assert source_health["meta_credentials"]["has_reauth_required"] is True
    assert source_health["meta_credentials"]["required_scope_coverage"]["missing"] == [
        "business_management",
        "pages_read_engagement",
    ]
    assert source_health["meta_page_connection"]["has_active_connection"] is True
    assert source_health["meta_page_connection"]["required_scope_coverage"]["missing"] == [
        "pages_read_engagement"
    ]
    assert source_health["meta_airbyte"]["sanitized_error_categories"] == {
        "destination_connection_refused": 1
    }
    assert source_health["stored_assets"] == {
        "ad_account_count": 0,
        "meta_page_count": 1,
        "analyzable_page_count": 1,
        "selected_default_page_count": 1,
    }
    assert source_health["stored_rows"]["organic_facebook_page"]["row_count"] == 0
    assert source_health["stored_rows"]["content_ops"]["row_count"] == 0
    assert "Reconnect Meta OAuth credentials" in " ".join(
        source_health["recommended_next_actions"]
    )
    assert_report_payload_excludes_sensitive_values(payload)
    serialized_payload = json.dumps(payload, default=str).lower()
    assert "host.docker.internal" not in serialized_payload
    assert "debug_token" not in serialized_payload
    assert "act_123" not in serialized_payload
    assert "page-1" not in serialized_payload
    event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_history_probe_generated",
        resource_type="report_definition",
        resource_id=report.id,
    )
    assert event.metadata == {
        "redacted": True,
        "primary_start_date": "2026-05-01",
        "primary_end_date": "2026-05-31",
        "history_start_date": "2026-03-01",
        "history_end_date": "2026-05-31",
    }
    assert_redacted_report_audit_metadata(event.metadata)


def test_slb_report_evidence_bundle_command_outputs_fixed_target_bundle(tenant, tmp_path):
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB evidence bundle",
        filters={
            "date_range": "last_month",
            "delivery_emails": ["ops@example.com"],
            "access_token": "secret-token-value",
        },
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )
    artifact = tmp_path / "slb-report.csv"
    artifact.write_text("section,value\npaid,1\n", encoding="utf-8")
    ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
        status=ReportExportJob.STATUS_COMPLETED,
        artifact_path=str(artifact),
        completed_at=timezone.now(),
        metadata={
            "preview_hash": "preview-hash-from-export",
            "report_preview": {
                "preview_hash": "preview-hash-from-export",
                "blocking_reasons": [],
                "report_snapshot": {"preview_hash": "snapshot-hash-from-export"},
            },
            "delivery_status": {
                "mode": "dry_run",
                "status": "rendered",
                "sanitized": True,
                "recipient": "ops@example.com",
            },
        },
    )
    output = StringIO()

    call_command(
        "slb_report_evidence_bundle",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_evidence_bundle.v1"
    assert payload["report"]["id"] == str(report.id)
    assert payload["date_range"] == {
        "date_range": "custom",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }
    assert payload["diagnostics"]["date_range"] == payload["date_range"]
    assert payload["rendering"]["page_count"] == 8
    assert payload["rendering"]["widget_count"] == 10
    assert payload["coverage_summary"]["datasets"]
    assert payload["diagnostics"]["datasets"]
    assert payload["diagnostics"]["source_health"]["schema_version"] == "slb_source_health.v1"
    assert payload["diagnostics"]["source_health"]["stored_aggregate_only"] is True
    assert payload["diagnostics"]["source_health"]["no_live_provider_calls"] is True
    assert payload["parity_rows"]
    assert payload["exports"][0]["artifact_present"] is True
    assert payload["exports"][0]["artifact_size_bytes"] == artifact.stat().st_size
    assert payload["exports"][0]["preview_hash"] == "preview-hash-from-export"
    assert payload["exports"][0]["snapshot_preview_hash"] == "snapshot-hash-from-export"
    assert payload["exports"][0]["delivery_status"] == {
        "mode": "dry_run",
        "sanitized": True,
        "status": "rendered",
    }
    assert_report_payload_excludes_sensitive_values(payload)
    event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_evidence_bundle_generated",
        resource_type="report_definition",
        resource_id=report.id,
    )
    assert set(event.metadata.keys()) == {
        "end_date",
        "parity_row_count",
        "preview_hash",
        "redacted",
        "start_date",
    }
    assert event.metadata["parity_row_count"] == len(payload["parity_rows"])
    assert_redacted_report_audit_metadata(event.metadata)


def test_slb_report_parity_compare_command_computes_deltas_and_blocks_missing_values(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "parity_rows": [
            {
                "page_id": "executive_summary",
                "section_id": "executive_summary_widgets",
                "widget_id": "paid_summary",
                "dataset": "paid_meta_ads",
                "metric": "spend",
                "label": "Spend",
                "coverage_status": "fresh",
                "source_label": "Stored warehouse snapshot",
                "adinsights_value": 100,
            },
            {
                "page_id": "executive_summary",
                "section_id": "executive_summary_widgets",
                "widget_id": "paid_summary",
                "dataset": "paid_meta_ads",
                "metric": "clicks",
                "label": "Clicks",
                "coverage_status": "fresh",
                "source_label": "Stored warehouse snapshot",
                "adinsights_value": 80,
            },
            {
                "page_id": "organic_facebook",
                "section_id": "organic_facebook_widgets",
                "widget_id": "organic_page_summary",
                "dataset": "organic_facebook_page",
                "metric": "page_reach",
                "label": "Page reach",
                "coverage_status": "missing_history",
                "source_label": "Stored Page Insights",
                "adinsights_value": 5,
            },
            {
                "page_id": "content_activity",
                "section_id": "content_activity_widgets",
                "widget_id": "content_activity_summary",
                "dataset": "content_ops",
                "metric": "published_posts",
                "label": "Published posts",
                "coverage_status": "fresh",
                "source_label": "Content Ops snapshots",
                "adinsights_value": 10,
            },
            {
                "page_id": "content_activity",
                "section_id": "content_activity_widgets",
                "widget_id": "content_activity_summary",
                "dataset": "content_ops",
                "metric": "content_items_created",
                "label": "Content items created",
                "coverage_status": "fresh",
                "source_label": "Content Ops snapshots",
                "adinsights_value": 6,
            },
        ],
    }
    comparison_values = {
        "schema_version": "slb_comparison_values.v1",
        "source_reference": "ops@example.com access_token=secret-token-value",
        "rows": [
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "spend",
                "label": "Spend",
                "dashthis_value": 101,
                "accepted_tolerance_percent": 1,
                "explanation": "DashThis May 2026 redacted export.",
            },
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "clicks",
                "label": "Clicks",
                "source_value": 100,
                "accepted_tolerance_percent": 2,
                "explanation": "Click source total.",
            },
            {
                "dataset": "content_ops",
                "widget_id": "content_activity_summary",
                "metric": "published_posts",
                "label": "Published posts",
                "comparison_value": 10,
                "accepted_tolerance_absolute": 0,
                "explanation": "Internal count should match exactly.",
            },
            {
                "dataset": "content_ops",
                "widget_id": "content_activity_summary",
                "metric": "content_items_created",
                "label": "Content items created",
                "comparison_value": 6,
                "explanation": "Missing approved tolerance should block.",
            },
        ],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    comparison_path = tmp_path / "comparison-values.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    comparison_path.write_text(json.dumps(comparison_values), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_parity_compare",
        "--evidence-bundle",
        str(evidence_path),
        "--comparison-values",
        str(comparison_path),
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_parity_comparison.v1"
    assert payload["source_reference"] == "redacted"
    assert payload["row_count"] == 5
    assert payload["result_summary"] == {
        "blocked_metric_semantics": 1,
        "blocked_missing_dashthis_value": 1,
        "fail": 1,
        "pass": 2,
    }
    rows_by_metric = {row["metric"]: row for row in payload["rows"]}
    assert rows_by_metric["spend"]["result"] == "pass"
    assert rows_by_metric["spend"]["absolute_delta"] == -1
    assert rows_by_metric["clicks"]["result"] == "fail"
    assert rows_by_metric["clicks"]["percentage_delta"] == 20
    assert rows_by_metric["page_reach"]["result"] == "blocked_missing_dashthis_value"
    assert rows_by_metric["published_posts"]["result"] == "pass"
    assert rows_by_metric["content_items_created"]["result"] == "blocked_metric_semantics"
    assert_report_payload_excludes_sensitive_values(payload)


def test_slb_report_parity_compare_command_does_not_call_live_providers(tmp_path, monkeypatch):
    block_live_network_calls(monkeypatch)
    evidence_path = tmp_path / "evidence-bundle.json"
    comparison_path = tmp_path / "comparison-values.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "slb_evidence_bundle.v1",
                "report": {"id": "report-1"},
                "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
                "preview_hash": "preview-hash-1",
                "parity_rows": [
                    {
                        "dataset": "paid_meta_ads",
                        "widget_id": "paid_summary",
                        "metric": "spend",
                        "label": "Spend",
                        "adinsights_value": 100,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    comparison_path.write_text(
        json.dumps(
            {
                "schema_version": "slb_comparison_values.v1",
                "rows": [
                    {
                        "dataset": "paid_meta_ads",
                        "widget_id": "paid_summary",
                        "metric": "spend",
                        "label": "Spend",
                        "dashthis_value": 100,
                        "accepted_tolerance_percent": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = StringIO()

    call_command(
        "slb_report_parity_compare",
        "--evidence-bundle",
        str(evidence_path),
        "--comparison-values",
        str(comparison_path),
        stdout=output,
    )

    assert json.loads(output.getvalue())["result_summary"] == {"pass": 1}


def test_slb_report_evidence_validate_command_passes_complete_artifacts(tmp_path, monkeypatch):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
        ],
        "diagnostics": {
            "source_health": slb_source_health_pass(),
        },
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 1,
        "result_summary": {"pass": 1},
        "rows": [slb_parity_pass_row()],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_evidence_validation.v1"
    assert payload["evidence"] == {
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "parity_preview_hash": "preview-hash-1",
    }
    assert payload["readiness_status"] == "pass"
    assert payload["blocker_count"] == 0
    assert {check["code"] for check in payload["checks"]} >= {
        "bundle_schema",
        "coverage_datasets",
        "date_range",
        "exports",
        "instagram",
        "parity",
        "rendering",
        "sensitive_payload",
        "source_health",
    }


def test_slb_report_evidence_validate_requires_diagnostics_source_health(tmp_path, monkeypatch):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
        ],
        "diagnostics": {},
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 1,
        "result_summary": {"pass": 1},
        "rows": [slb_parity_pass_row()],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    assert any(row["code"] == "source_health" for row in payload["blockers"])


def test_slb_report_evidence_validate_requires_export_preview_and_snapshot_hashes(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "different-snapshot-hash",
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
        ],
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 1,
        "result_summary": {"pass": 1},
        "rows": [slb_parity_pass_row()],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    blockers = {(row["code"], row["message"]) for row in payload["blockers"]}
    assert ("export_hash", "csv export preview_hash is required.") in blockers
    assert ("export_hash", "csv export snapshot_preview_hash is required.") in blockers
    assert ("export_hash", "pdf snapshot_preview_hash differs from bundle.") in blockers
    assert any(row["code"] == "exports" and "csv" in row["message"] for row in payload["blockers"])
    assert any(row["code"] == "exports" and "pdf" in row["message"] for row in payload["blockers"])


def test_slb_report_evidence_validate_requires_parity_preview_hash_match(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
        ],
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "different-preview-hash",
        "row_count": 1,
        "result_summary": {"pass": 1},
        "rows": [slb_parity_pass_row()],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    assert {
        "code": "parity_hash",
        "message": "Parity comparison preview_hash does not match evidence bundle.",
    } in payload["blockers"]


def test_slb_report_evidence_validate_requires_parity_report_identity_match(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
        ],
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": {"id": "other-report", "template_key": "other_template"},
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 1,
        "result_summary": {"pass": 1},
        "rows": [slb_parity_pass_row()],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    assert {
        "code": "report_identity",
        "message": "Parity comparison report.id does not match evidence bundle.",
    } in payload["blockers"]
    assert {
        "code": "report_identity",
        "message": "Parity comparison report.template_key does not match evidence bundle.",
    } in payload["blockers"]


def test_slb_report_evidence_validate_requires_parity_row_summary_consistency(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
        ],
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 3,
        "result_summary": {"pass": 3},
        "rows": [{"result": "pass"}, {"result": "fail"}],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    assert {
        "code": "parity_rows",
        "message": "Parity comparison row_count does not match rows length.",
    } in payload["blockers"]
    assert {
        "code": "parity_results",
        "message": "Parity result_summary does not match row results.",
    } in payload["blockers"]


def test_slb_report_evidence_validate_rejects_unsupported_parity_results(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
        ],
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 1,
        "result_summary": {"waived": 1},
        "rows": [{"result": "waived"}],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    assert {
        "code": "parity_results",
        "message": "Parity has unsupported result labels: waived.",
    } in payload["blockers"]
    assert {
        "code": "parity_results",
        "message": "Parity comparison must include at least one passing row.",
    } in payload["blockers"]


def test_slb_report_evidence_validate_requires_substantive_pass_rows(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 2}, "row_count": 8},
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 10,
            "pages": [
                {"id": "cover"},
                {"id": "executive_summary"},
                {"id": "paid_meta_ads"},
                {"id": "organic_facebook"},
                {"id": "top_posts"},
                {"id": "content_activity"},
                {"id": "recommendations"},
                {"id": "appendix"},
            ],
        },
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "delivery_status": {"mode": "dry_run", "status": "rendered", "sanitized": True},
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
            },
        ],
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 1,
        "result_summary": {"pass": 1},
        "rows": [{"result": "pass"}],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    blockers = {(row["code"], row["message"]) for row in payload["blockers"]}
    assert ("parity_pass_row", "Parity pass row 0 is missing dataset.") in blockers
    assert ("parity_pass_row", "Parity pass row 0 is missing source_value.") in blockers
    assert ("parity_pass_row", "Parity pass row 0 is missing accepted tolerance.") in blockers
    assert ("parity_pass_row", "Parity pass row 0 is missing explanation.") in blockers


def test_slb_report_evidence_validate_command_surfaces_cancellation_blockers(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {"date_range": "custom", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"missing_history": 1}, "row_count": 0},
                {"dataset": "organic_facebook_page", "statuses": {"fresh": 1}, "row_count": 3},
            ]
        },
        "rendering": {"widget_count": 0, "pages": [{"id": "cover"}]},
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": False,
                "artifact_size_bytes": 0,
                "preview_hash": "different-hash",
                "snapshot_preview_hash": "different-hash",
                "delivery_status": {"mode": "dry_run", "status": "failed", "sanitized": True},
            }
        ],
        "raw_payload": "user_id=123 access_token=secret-token-value",
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "date_range": {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        "preview_hash": "preview-hash-1",
        "row_count": 2,
        "result_summary": {"pass": 1, "fail": 1, "blocked_missing_dashthis_value": 1},
        "rows": [],
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    parity_path = tmp_path / "parity-comparison.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    parity_path.write_text(json.dumps(parity_comparison), encoding="utf-8")
    output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--parity-comparison",
        str(parity_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    codes = {row["code"] for row in payload["blockers"]}
    assert {
        "coverage_datasets",
        "coverage_row_count",
        "coverage_status",
        "date_range",
        "exports",
        "export_hash",
        "parity_results",
        "rendering_pages",
        "rendering_widgets",
        "scheduled_dry_run",
        "sensitive_payload",
    } <= codes


def test_report_v1_export_blocks_when_required_coverage_missing(api_client, user, tenant):
    authenticate(api_client, user)
    layout = build_slb_monthly_report_layout(date_range="last_month")
    layout["widgets"][1]["coverage_policy"] = "require_full_coverage"
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB blocked export",
        filters={"date_range": "last_month"},
        layout=layout,
    )

    response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )

    assert response.status_code == 409
    assert "require_full_coverage" in str(response.json())
    assert not ReportExportJob.all_objects.filter(report=report).exists()


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


def test_generic_report_export_preserves_report_contract_metadata(
    tenant, tmp_path, monkeypatch
):
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB contract report",
        filters={"range": "last_month", "platforms": ["meta"]},
        layout={
            "schema_version": "report.v1",
            "template_key": "slb_monthly_social_report",
            "catalog_schema_version": "reporting_catalog.v1",
            "coverage": {
                "paid_meta_ads": {
                    "coverage_status": "fresh",
                    "covered_end_date": "2026-06-15",
                }
            },
        },
    )
    job = ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
    )
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant",
        lambda tenant_id: (
            {"campaign": {"summary": {}, "rows": []}},
            timezone.now(),
            "fetched",
        ),
    )

    result = run_report_export_job.run(str(job.id))

    job.refresh_from_db()
    assert result["status"] == ReportExportJob.STATUS_COMPLETED
    assert job.metadata["report_schema_version"] == "report.v1"
    assert job.metadata["report_template_key"] == "slb_monthly_social_report"
    assert job.metadata["catalog_schema_version"] == "reporting_catalog.v1"
    assert job.metadata["coverage"]["paid_meta_ads"]["coverage_status"] == "fresh"


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


def test_reporting_catalog_endpoint_requires_authentication(api_client):
    response = api_client.get(reverse("dashboard-reporting-catalog"))

    assert response.status_code == 401


def test_reporting_catalog_endpoint_returns_governed_registry(api_client, user):
    authenticate(api_client, user)

    response = api_client.get(reverse("dashboard-reporting-catalog"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "reporting_catalog.v1"
    assert payload["dashboard_schema_version"] == "dashboard.v1"
    assert {"datasets", "metrics", "dimensions", "widgets", "compatibility"} <= set(payload)
    assert any(dataset["key"] == "paid_meta_ads" for dataset in payload["datasets"])
    assert any(
        metric["dataset"] == "paid_meta_ads" and metric["key"] == "spend"
        for metric in payload["metrics"]
    )
    assert payload["compatibility"]["table"] == {
        "requires_row_limit": True,
        "max_row_limit": 500,
    }
    assert "render_with_warning" in payload["coverage_policies"]
    assert payload["source_metric_semantics"]["organic_facebook_page"]["page"]["page_reach"] == [
        "page_total_media_view_unique",
        "page_impressions_unique",
    ]
    assert "post_reactions_by_type_total" in payload["source_metric_semantics"]["organic_facebook_page"]["post"][
        "post_reactions_like"
    ]


def dashboard_preview_widget(**overrides):
    today = timezone.localdate().isoformat()
    widget = {
        "id": "paid_spend_kpi",
        "type": "kpi",
        "dataset": "paid_meta_ads",
        "metrics": ["spend", "clicks"],
        "dimensions": [],
        "filters": {
            "date_range": "custom",
            "start_date": today,
            "end_date": today,
        },
        "coverage_policy": "render_with_warning",
        "visual": {"title": "Paid KPIs", "source_labels": True},
    }
    widget.update(overrides)
    return widget


def test_dashboard_widget_preview_requires_authentication(api_client):
    response = api_client.post(reverse("dashboard-widget-preview"), {}, format="json")

    assert response.status_code == 401


def test_dashboard_widget_preview_returns_stored_aggregate_data(api_client, user, tenant):
    today = timezone.localdate().isoformat()
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "summary": {
                    "currency": "JMD",
                    "totalSpend": 1200,
                    "totalClicks": 80,
                },
                "trend": [{"date": today, "spend": 1200, "clicks": 80}],
                "rows": [{"date": today, "campaign": "SLB Awareness", "spend": 1200, "clicks": 80}],
            }
        },
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {"widget": dashboard_preview_widget()},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["widget_id"] == "paid_spend_kpi"
    assert payload["dataset"] == "paid_meta_ads"
    assert payload["data"]["kind"] == "kpi"
    assert payload["data"]["metrics"][0] == {
        "key": "spend",
        "label": "Spend",
        "value": 1200,
    }
    assert payload["coverage"]["coverage_status"] == "fresh"
    assert payload["coverage"]["row_count"] == 1


def test_dashboard_widget_preview_renders_synced_posts_without_post_insights(
    api_client,
    user,
    tenant,
):
    connection = MetaConnection(
        tenant=tenant,
        user=user,
        app_scoped_user_id="slb-app-user",
        scopes=["pages_show_list", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("meta-user-token")
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="slb-page",
        name="Students' Loan Bureau",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token("meta-page-token")
    page.save()
    MetaPost.all_objects.create(
        tenant=tenant,
        page=page,
        post_id="slb-page_123",
        message="Real synced SLB post",
        created_time=datetime(2026, 5, 10, 15, 30, tzinfo=dt_timezone.utc),
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(
                id="top_posts_table",
                type="data_table",
                dataset="organic_facebook_page",
                dimensions=["post"],
                metrics=["post_impressions", "post_clicks"],
                filters={
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                visual={"row_limit": 10, "title": "Top posts"},
            ),
            "page_id": "slb-page",
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["kind"] == "table"
    assert payload["data"]["columns"] == ["post", "date", "content", "post_impressions", "post_clicks"]
    assert payload["data"]["rows"] == [
        {
            "post": "slb-page_123",
            "date": "2026-05-10",
            "content": "Real synced SLB post",
            "post_impressions": None,
            "post_clicks": None,
        }
    ]
    assert payload["coverage"]["row_count"] == 1
    assert payload["coverage"]["coverage_status"] == "partial"
    assert payload["coverage"]["source_label"] == "Facebook Page synced posts"
    assert payload["coverage"]["coverage_note"] == (
        "Facebook Page posts are stored, but post insight metric rows are unavailable "
        "for this range."
    )


def test_dashboard_widget_preview_uses_null_values_for_missing_organic_kpis(
    api_client,
    user,
):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(
                id="organic_page_summary",
                type="kpi",
                dataset="organic_facebook_page",
                dimensions=[],
                metrics=["page_reach", "page_impressions"],
                filters={
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
            )
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["coverage"]["coverage_status"] == "missing_history"
    assert payload["data"]["metrics"] == [
        {"key": "page_reach", "label": "Page Reach", "value": None},
        {"key": "page_impressions", "label": "Page Impressions", "value": None},
    ]


def test_dashboard_widget_preview_maps_v24_post_reaction_breakdowns(
    api_client,
    user,
    tenant,
):
    connection = MetaConnection(
        tenant=tenant,
        user=user,
        app_scoped_user_id="slb-app-user",
        scopes=["pages_show_list", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("meta-user-token")
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="slb-page",
        name="Students' Loan Bureau",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token("meta-page-token")
    page.save()
    post = MetaPost.all_objects.create(
        tenant=tenant,
        page=page,
        post_id="slb-page_123",
        message="V24 reactions post",
        created_time=datetime(2026, 5, 10, 15, 30, tzinfo=dt_timezone.utc),
    )
    metric_time = datetime(2026, 5, 10, 23, 59, tzinfo=dt_timezone.utc)
    for breakdown_key, value in {"like": 4, "love": 2}.items():
        MetaPostInsightPoint.all_objects.create(
            tenant=tenant,
            post=post,
            metric_key="post_reactions_by_type_total",
            period="lifetime",
            end_time=metric_time,
            value_num=value,
            value_json={breakdown_key: value},
            breakdown_key=breakdown_key,
            breakdown_key_normalized=breakdown_key,
            breakdown_json={"key": breakdown_key, "value": value},
        )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(
                id="top_posts_table",
                type="data_table",
                dataset="organic_facebook_page",
                dimensions=["post"],
                metrics=["post_reactions_like", "post_reactions_love"],
                filters={
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                visual={"row_limit": 10, "title": "Top posts"},
            ),
            "page_id": "slb-page",
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["columns"] == ["post", "date", "content", "post_reactions_like", "post_reactions_love"]
    assert payload["data"]["rows"] == [
        {
            "post": "slb-page_123",
            "date": "2026-05-10",
            "content": "V24 reactions post",
            "post_reactions_like": 4.0,
            "post_reactions_love": 2.0,
        }
    ]
    assert payload["coverage"]["coverage_status"] == "partial"


def test_dashboard_widget_preview_prefers_fresh_meta_direct_paid_snapshot(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate().isoformat()
    outside_range = (timezone.localdate() - timedelta(days=7)).isoformat()
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=timezone.now() - timedelta(days=2),
        payload={
            "campaign": {
                "summary": {"totalSpend": 1200, "totalClicks": 80},
                "trend": [{"date": today, "spend": 1200, "clicks": 80}],
                "rows": [{"date": today, "campaign": "Old Warehouse", "spend": 1200}],
            }
        },
    )
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="meta_direct",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "summary": {"totalSpend": 9999, "totalClicks": 999},
                "trend": [
                    {"date": outside_range, "spend": 6000, "clicks": 600},
                    {"date": today, "spend": 2400, "clicks": 140},
                ],
                "rows": [
                    {
                        "date": outside_range,
                        "campaign": "Out of Range Meta Direct",
                        "spend": 6000,
                        "clicks": 600,
                    },
                    {
                        "date": today,
                        "campaign": "Fresh Meta Direct",
                        "spend": 2400,
                        "clicks": 140,
                    },
                ],
            }
        },
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {"widget": dashboard_preview_widget()},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["metrics"][0]["value"] == 2400
    assert payload["data"]["metrics"][1]["value"] == 140
    assert payload["coverage"]["source_label"] == "Direct Meta stored snapshot"
    assert payload["coverage"]["row_count"] == 1


def test_dashboard_widget_preview_uses_stored_direct_meta_rows_when_snapshot_is_stale(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate()
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="meta_direct",
        generated_at=timezone.now() - timedelta(days=1),
        payload={
            "campaign": {
                "summary": {"totalSpend": 10, "totalClicks": 1},
                "trend": [{"date": today.isoformat(), "spend": 10, "clicks": 1}],
                "rows": [{"date": today.isoformat(), "campaign": "Old Snapshot", "spend": 10}],
            }
        },
    )
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="SLB Meta Account",
        currency="USD",
        status="ACTIVE",
    )
    campaign = Campaign.objects.create(
        tenant=tenant,
        ad_account=account,
        external_id="cmp-raw",
        name="Fresh Raw Campaign",
        platform="meta",
        account_external_id=account.external_id,
        status="ACTIVE",
        objective="OUTCOME_AWARENESS",
        currency="USD",
    )
    adset = AdSet.objects.create(
        tenant=tenant,
        campaign=campaign,
        external_id="adset-raw",
        name="Fresh Raw Ad Set",
        status="ACTIVE",
    )
    ad = Ad.objects.create(
        tenant=tenant,
        adset=adset,
        external_id="ad-raw",
        name="Fresh Raw Ad",
        status="ACTIVE",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        campaign=campaign,
        adset=adset,
        ad=ad,
        external_id=ad.external_id,
        source="meta",
        level="ad",
        date=today,
        impressions=1000,
        reach=800,
        clicks=50,
        spend=75,
        conversions=5,
        currency="USD",
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {"widget": dashboard_preview_widget()},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["metrics"][0]["value"] == 75
    assert payload["data"]["metrics"][1]["value"] == 50
    assert payload["coverage"]["source_label"] == "Direct Meta stored snapshot"
    assert payload["coverage"]["coverage_status"] == "fresh"
    assert payload["coverage"]["covered_end_date"] == today.isoformat()


def test_dashboard_widget_preview_applies_top_level_account_scope_to_paid_rows(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate()
    selected = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_111",
        account_id="111",
        name="Selected Meta Account",
        currency="USD",
        status="ACTIVE",
    )
    other = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_222",
        account_id="222",
        name="Other Meta Account",
        currency="USD",
        status="ACTIVE",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=selected,
        external_id="selected-ad",
        source="meta",
        level="ad",
        date=today,
        impressions=1000,
        reach=800,
        clicks=50,
        spend=75,
        currency="USD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=other,
        external_id="other-ad",
        source="meta",
        level="ad",
        date=today,
        impressions=2000,
        reach=1400,
        clicks=90,
        spend=125,
        currency="USD",
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(),
            "account_id": "act_111",
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["metrics"][0]["value"] == 75
    assert payload["data"]["metrics"][1]["value"] == 50
    assert payload["coverage"]["row_count"] == 1


def test_dashboard_widget_preview_excludes_undated_paid_rows_from_bounded_kpis(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate().isoformat()
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="meta_direct",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "summary": {"totalSpend": 999999, "totalClicks": 9999},
                "trend": [{"date": today, "spend": 1200, "clicks": 80}],
                "rows": [
                    {
                        "campaign": "Undated lifetime aggregate",
                        "spend": 999999,
                        "clicks": 9999,
                    }
                ],
            }
        },
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {"widget": dashboard_preview_widget()},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["metrics"][0]["value"] == 1200
    assert payload["data"]["metrics"][1]["value"] == 80
    assert payload["coverage"]["row_count"] == 1
    assert payload["coverage"]["covered_start_date"] == today
    assert payload["coverage"]["covered_end_date"] == today


def test_dashboard_widget_preview_includes_bounded_paid_campaign_table_rows(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate()
    in_range_start = (today - timedelta(days=2)).isoformat()
    in_range_end = today.isoformat()
    outside_start = (today - timedelta(days=8)).isoformat()
    outside_end = (today - timedelta(days=7)).isoformat()
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="meta_direct",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "rows": [
                    {
                        "name": "SLB Bounded Campaign",
                        "startDate": in_range_start,
                        "endDate": in_range_end,
                        "spend": 145.89,
                        "impressions": 192294,
                        "reach": 110000,
                        "clicks": 3813,
                        "ctr": 0.019828,
                        "cpc": 0.038259,
                    },
                    {
                        "name": "Old Campaign",
                        "startDate": outside_start,
                        "endDate": outside_end,
                        "spend": 500,
                        "clicks": 50,
                    },
                    {
                        "campaign": "Undated Lifetime Aggregate",
                        "spend": 999999,
                        "clicks": 9999,
                    },
                ]
            }
        },
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(
                id="paid_campaign_table",
                type="data_table",
                dimensions=["campaign"],
                metrics=["spend", "impressions", "reach", "clicks", "ctr", "cpc"],
                visual={"row_limit": 10, "title": "Paid campaigns"},
            )
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["kind"] == "table"
    assert payload["data"]["rows"] == [
        {
            "campaign": "SLB Bounded Campaign",
            "spend": 145.89,
            "impressions": 192294,
            "reach": 110000,
            "clicks": 3813,
            "ctr": 0.019828,
            "cpc": 0.038259,
        }
    ]
    assert payload["coverage"]["row_count"] == 1
    assert payload["coverage"]["covered_start_date"] == in_range_start
    assert payload["coverage"]["covered_end_date"] == in_range_end


def test_dashboard_widget_preview_rejects_invalid_metric(api_client, user):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(
                dataset="organic_facebook_page",
                metrics=["spend"],
            )
        },
        format="json",
    )

    assert response.status_code == 400
    assert "metric 'spend' not valid for organic_facebook_page" in str(response.json())


def test_dashboard_widget_preview_rejects_cross_tenant_account_reference(
    api_client, user, tenant
):
    other_tenant = Tenant.objects.create(name="Other Preview Tenant")
    AdAccount.all_objects.create(
        tenant=other_tenant,
        external_id="act_other",
        account_id="other",
        name="Other account",
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {"widget": dashboard_preview_widget(), "account_id": "act_other"},
        format="json",
    )

    assert response.status_code == 400
    assert "account_id does not belong to the authenticated tenant" in str(response.json())


def test_dashboard_widget_preview_blocks_missing_history_when_policy_requires_full_coverage(
    api_client, user
):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(
                coverage_policy="require_full_coverage",
            )
        },
        format="json",
    )

    assert response.status_code == 409
    assert "require_full_coverage blocks coverage_status not_previously_synced" in str(
        response.json()
    )


def test_dashboard_widget_preview_labels_disconnected_sources_with_history(
    api_client, user, tenant
):
    today = timezone.localdate().isoformat()
    AirbyteConnection.objects.create(
        tenant=tenant,
        provider="META",
        name="Meta inactive",
        connection_id=uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        is_active=False,
    )
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "summary": {"totalSpend": 1200},
                "trend": [{"date": today, "spend": 1200}],
                "rows": [{"date": today, "campaign": "SLB", "spend": 1200}],
            }
        },
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {"widget": dashboard_preview_widget(metrics=["spend"])},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["coverage"]["coverage_status"] == "source_disconnected"
    assert payload["coverage"]["history_status"] == "available"
    assert "disconnected" in payload["warnings"][0]


def test_dashboard_widget_preview_keeps_partial_coverage_when_source_disconnected(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate()
    AirbyteConnection.objects.create(
        tenant=tenant,
        provider="META",
        name="Meta inactive",
        connection_id=uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        is_active=False,
    )
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "summary": {"totalSpend": 1200},
                "trend": [{"date": today.isoformat(), "spend": 1200}],
                "rows": [{"date": today.isoformat(), "campaign": "SLB", "spend": 1200}],
            }
        },
    )
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-widget-preview"),
        {
            "widget": dashboard_preview_widget(
                metrics=["spend"],
                filters={
                    "date_range": "custom",
                    "start_date": (today - timedelta(days=1)).isoformat(),
                    "end_date": today.isoformat(),
                },
            )
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["coverage"]["coverage_status"] == "partial"
    assert "partial retained history" in payload["warnings"][0]


def test_dashboard_definitions_accept_dashboard_v1_layout(api_client, user):
    authenticate(api_client, user)

    payload = {
        "name": "Catalog-backed dashboard",
        "description": "Saved dashboard.v1 config",
        "template_key": DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
        "filters": {},
        "layout": {
            "schema_version": "dashboard.v1",
            "layout": {
                "columns": 12,
                "slots": [
                    {
                        "id": "slot_spend_trend",
                        "widget_id": "spend_trend",
                        "cols": 8,
                        "rows": 2,
                    }
                ],
            },
            "widgets": [
                {
                    "id": "spend_trend",
                    "type": "line_chart",
                    "dataset": "paid_meta_ads",
                    "metrics": ["spend"],
                    "dimensions": ["date"],
                    "filters": {"date_range": "last_90d"},
                    "coverage_policy": "render_with_warning",
                    "visual": {"title": "Spend trend", "source_labels": True},
                }
            ],
        },
        "default_metric": DashboardDefinition.METRIC_SPEND,
        "is_active": True,
    }

    response = api_client.post(reverse("dashboard-definition-list"), payload, format="json")

    assert response.status_code == 201
    assert response.json()["layout"]["schema_version"] == "dashboard.v1"


def test_dashboard_definitions_dashboard_v1_remains_tenant_scoped(api_client, user, tenant):
    other_tenant = Tenant.objects.create(name="Other Dashboard Tenant")
    DashboardDefinition.objects.create(
        tenant=other_tenant,
        name="Other tenant catalog dashboard",
        template_key=DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
        layout={
            "schema_version": "dashboard.v1",
            "widgets": [
                {
                    "id": "other_spend",
                    "type": "kpi",
                    "dataset": "paid_meta_ads",
                    "metrics": ["spend"],
                    "filters": {"date_range": "last_90d"},
                }
            ],
        },
        default_metric=DashboardDefinition.METRIC_SPEND,
    )
    own_dashboard = DashboardDefinition.objects.create(
        tenant=tenant,
        name="Own catalog dashboard",
        template_key=DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
        layout={
            "schema_version": "dashboard.v1",
            "widgets": [
                {
                    "id": "own_spend",
                    "type": "kpi",
                    "dataset": "paid_meta_ads",
                    "metrics": ["spend"],
                    "filters": {"date_range": "last_90d"},
                }
            ],
        },
        default_metric=DashboardDefinition.METRIC_SPEND,
    )
    authenticate(api_client, user)

    response = api_client.get(reverse("dashboard-definition-list"))

    assert response.status_code == 200
    dashboard_ids = {row["id"] for row in list_payload(response)}
    assert str(own_dashboard.id) in dashboard_ids
    assert not DashboardDefinition.objects.filter(tenant=other_tenant, id__in=dashboard_ids).exists()


def test_dashboard_definitions_reject_invalid_dashboard_v1_layout(api_client, user):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("dashboard-definition-list"),
        {
            "name": "Invalid catalog dashboard",
            "template_key": DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
            "filters": {},
            "layout": {
                "schema_version": "dashboard.v1",
                "widgets": [
                    {
                        "id": "bad_table",
                        "type": "data_table",
                        "dataset": "paid_meta_ads",
                        "metrics": ["spend"],
                        "dimensions": ["campaign"],
                        "filters": {"date_range": "last_90d"},
                    }
                ],
            },
            "default_metric": DashboardDefinition.METRIC_SPEND,
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "data_table widgets require row_limit" in str(response.json()["layout"])


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
