from __future__ import annotations

import csv
import json
from io import StringIO
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    AuditLog,
    Role,
    Tenant,
    User,
    assign_role,
    seed_default_roles,
)
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
    SavedReportLayout,
    TenantMetricsSnapshot,
)
from analytics import reporting_report_preview as report_preview_module
from analytics.reporting_templates import build_slb_monthly_report_layout
from analytics.tasks import run_report_export_job
from content_ops.models import (
    ContentDraft,
    ContentDraftVersion,
    ContentWorkspace,
    OrganicPostMetricSnapshot,
    PublishedPost,
)
from integrations.models import (
    AirbyteConnection,
    AlertRuleDefinition,
    Client,
    ClientPlatformAccount,
    MetaConnection,
    MetaInsightPoint,
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


def assert_redacted_report_audit_metadata(
    metadata, *, allow_blocking_reason_details=False
):
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


def report_metric_availability_by_key(dataset_payload):
    return {
        row["key"]: row for row in dataset_payload["metric_availability"]["metrics"]
    }


def block_live_network_calls(monkeypatch):
    def fail_network_call(*_args, **_kwargs):
        raise AssertionError(
            "reporting preview/export/parity must not open live network connections"
        )

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


def slb_evidence_bundle_pass() -> dict:
    return {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 240,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
        ],
        "diagnostics": {"source_health": slb_source_health_pass()},
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
            "paid_meta_ads": {
                "row_count": 31,
                "min_date": "2026-05-01",
                "max_date": "2026-05-31",
            },
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
        "remediation_actions": [],
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


def seed_slb_warning_ready_sources(*, tenant: Tenant, user: User) -> None:
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="SLB Meta Account",
        currency="USD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        external_id="paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=1200,
        impressions=5000,
        reach=4200,
        clicks=80,
    )

    connection = MetaConnection(
        tenant=tenant, user=user, app_scoped_user_id="meta-user"
    )
    connection.set_raw_token("meta-user-token")
    connection.scopes = ["pages_show_list", "pages_read_engagement"]
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="page-123",
        name="SLB Facebook Page",
        can_analyze=True,
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    MetaInsightPoint.objects.create(
        tenant=tenant,
        page=page,
        metric_key="page_follows",
        period="day",
        end_time=datetime(2026, 5, 31, 12, tzinfo=dt_timezone.utc),
        value_num=6023,
    )
    post = MetaPost.objects.create(
        tenant=tenant,
        page=page,
        post_id="page-123_1",
        message="Stored post with edge engagement",
        created_time=datetime(2026, 5, 10, 12, tzinfo=dt_timezone.utc),
        last_synced_at=timezone.now(),
    )
    for metric_key, value in {
        "post_reactions_total": 16,
        "post_comments_total": 0,
        "post_shares_total": 8,
    }.items():
        MetaPostInsightPoint.objects.create(
            tenant=tenant,
            post=post,
            metric_key=metric_key,
            period="lifetime",
            end_time=datetime(2026, 5, 10, 12, tzinfo=dt_timezone.utc),
            value_num=value,
        )

    workspace = ContentWorkspace.all_objects.create(tenant=tenant, name="SLB Content")
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="SLB May post",
        state=ContentDraft.STATE_PUBLISHED,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="SLB May post",
    )
    PublishedPost.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        draft=draft,
        version=version,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id="page-123_1",
        published_at=datetime(2026, 5, 10, 12, tzinfo=dt_timezone.utc),
        reporting_link_state=PublishedPost.REPORTING_LINKED,
    )


def seed_slb_paid_only_sources(*, tenant: Tenant, user: User) -> None:
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="SLB Meta Account",
        currency="USD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        external_id="paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=1200,
        impressions=5000,
        reach=4200,
        clicks=80,
    )
    connection = MetaConnection(
        tenant=tenant, user=user, app_scoped_user_id="meta-user"
    )
    connection.set_raw_token("meta-user-token")
    connection.scopes = ["pages_show_list", "pages_read_engagement"]
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="page-123",
        name="SLB Facebook Page",
        can_analyze=True,
        is_default=True,
        last_synced_at=timezone.now(),
        last_posts_synced_at=timezone.now(),
    )
    page.set_raw_page_token("page-token")
    page.save()


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
    create_response = api_client.post(
        reverse("report-definition-list"), payload, format="json"
    )
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


def test_report_create_update_audit_events_store_field_names_only(
    api_client, user, tenant
):
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
    widgets_by_id = {widget["id"]: widget for widget in payload["layout"]["widgets"]}
    assert widgets_by_id["organic_page_summary"]["metrics"] == ["page_follows"]
    assert widgets_by_id["organic_post_engagement_summary"]["metrics"] == [
        "post_reactions",
        "post_comments",
        "post_shares",
    ]
    assert widgets_by_id["top_posts_table"]["metrics"] == [
        "post_reactions",
        "post_comments",
        "post_shares",
    ]
    assert (
        "unavailable in ADinsights until Meta approves"
        in widgets_by_id["organic_reach_impressions_note"]["visual"]["body"]
    )
    organic_metrics = {
        metric
        for widget in payload["layout"]["widgets"]
        if widget["dataset"] == "organic_facebook_page"
        for metric in widget["metrics"]
    }
    assert {"page_reach", "page_impressions", "post_impressions"} - organic_metrics == {
        "page_reach",
        "page_impressions",
        "post_impressions",
    }
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
    assert (
        registry_payload["templates"][0]["template_key"] == "slb_monthly_social_report"
    )
    assert registry_payload["templates"][0]["supported_datasets"] == [
        "paid_meta_ads",
        "organic_facebook_page",
        "content_ops",
    ]
    assert registry_payload["templates"][0]["export_policy"][
        "warning_only_coverage_statuses"
    ]["organic_facebook_page"] == [
        "missing_history",
        "not_previously_synced",
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


def test_report_data_availability_returns_stored_source_scope(api_client, user, tenant):
    authenticate(api_client, user)
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="SLB Meta Account",
        currency="USD",
    )
    for day in (1, 31):
        RawPerformanceRecord.objects.create(
            tenant=tenant,
            ad_account=account,
            external_id=f"paid-{day}",
            date=datetime(2026, 5, day).date(),
            level="campaign",
            source="meta",
            spend=10,
            impressions=100,
            clicks=5,
        )
    connection = MetaConnection(
        tenant=tenant, user=user, app_scoped_user_id="meta-user"
    )
    connection.set_raw_token("meta-user-token")
    connection.scopes = ["pages_show_list", "pages_read_engagement"]
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="page-123",
        name="SLB Facebook Page",
        can_analyze=True,
        is_default=True,
        last_synced_at=timezone.now(),
        last_posts_synced_at=timezone.now(),
    )
    page.set_raw_page_token("page-token")
    page.save()
    for day in (1, 31):
        MetaInsightPoint.objects.create(
            tenant=tenant,
            page=page,
            metric_key="page_media_view",
            period="day",
            end_time=datetime(2026, 5, day, 12, tzinfo=dt_timezone.utc),
            value_num=100,
        )
    post = MetaPost.objects.create(
        tenant=tenant,
        page=page,
        post_id="page-123_1",
        message="May update",
        created_time=datetime(2026, 5, 15, 12, tzinfo=dt_timezone.utc),
        last_synced_at=timezone.now(),
    )
    MetaPostInsightPoint.objects.create(
        tenant=tenant,
        post=post,
        metric_key="post_clicks",
        period="lifetime",
        end_time=datetime(2026, 5, 15, 12, tzinfo=dt_timezone.utc),
        value_num=7,
    )

    response = api_client.get(
        reverse("report-definition-data-availability"),
        {
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "report_data_availability.v1"
    assert payload["stored_aggregate_only"] is True
    assert payload["no_live_provider_calls"] is True
    assert payload["requested"]["account_id"] == "act_123"
    assert payload["requested"]["page_id"] == "page-123"
    assert payload["datasets"]["paid_meta_ads"]["row_count"] == 2
    assert payload["datasets"]["paid_meta_ads"]["coverage_status"] == "partial"
    assert payload["datasets"]["paid_meta_ads"]["coverage_gap"]["missing_day_count"] == 29
    assert payload["datasets"]["paid_meta_ads"]["coverage_note"] == (
        "Stored rows are missing 29 requested days "
        "from 2026-05-02 through 2026-05-30."
    )
    assert (
        payload["datasets"]["paid_meta_ads"]["available_accounts"][0]["account_id"]
        == "123"
    )
    paid_metrics = report_metric_availability_by_key(
        payload["datasets"]["paid_meta_ads"]
    )
    assert paid_metrics["spend"]["availability_state"] == "available"
    assert paid_metrics["ctr"]["availability_state"] == "available"
    assert paid_metrics["conversion_value"]["availability_state"] == "callable_no_data"
    assert payload["datasets"]["organic_facebook_page"]["row_count"] == 2
    assert (
        payload["datasets"]["organic_facebook_page"]["coverage_status"] == "partial"
    )
    assert (
        payload["datasets"]["organic_facebook_page"]["coverage_gap"][
            "missing_day_count"
        ]
        == 29
    )
    assert payload["datasets"]["organic_facebook_page"]["coverage_note"] == (
        "Stored rows are missing 29 requested days "
        "from 2026-05-02 through 2026-05-30."
    )
    assert (
        payload["datasets"]["organic_facebook_page"]["available_pages"][0]["page_id"]
        == "page-123"
    )
    page_metrics = report_metric_availability_by_key(
        payload["datasets"]["organic_facebook_page"]
    )
    assert page_metrics["page_impressions"]["availability_state"] == "permission_gated"
    assert page_metrics["page_impressions"]["row_count"] == 0
    assert "page_media_view" in page_metrics["page_impressions"]["source_metric_keys"]
    assert page_metrics["page_follows"]["availability_state"] == "callable_no_data"
    assert payload["datasets"]["organic_facebook_posts"]["post_count"] == 1
    assert payload["datasets"]["organic_facebook_posts"]["row_count"] == 1
    post_metrics = report_metric_availability_by_key(
        payload["datasets"]["organic_facebook_posts"]
    )
    assert post_metrics["post_activity"]["availability_state"] == "available"
    assert post_metrics["post_clicks"]["availability_state"] == "available"
    assert "content_ops" not in payload["blocking_datasets"]
    assert "content_ops" in payload["warning_datasets"]
    assert "organic_facebook_posts" in payload["blocking_datasets"]
    assert payload["eligible_for_report_export"] is False
    assert_report_payload_excludes_sensitive_values(payload)


def test_report_data_availability_blocks_partial_required_source(
    api_client, user, tenant
):
    authenticate(api_client, user)
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="SLB Meta Account",
        currency="USD",
    )
    for day in (1, 31):
        RawPerformanceRecord.objects.create(
            tenant=tenant,
            ad_account=account,
            external_id=f"paid-partial-{day}",
            date=datetime(2026, 5, day).date(),
            level="campaign",
            source="meta",
            spend=10,
            impressions=100,
            clicks=5,
        )
    connection = MetaConnection(
        tenant=tenant, user=user, app_scoped_user_id="meta-user"
    )
    connection.set_raw_token("meta-user-token")
    connection.scopes = ["pages_show_list", "pages_read_engagement"]
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="page-123",
        name="SLB Facebook Page",
        can_analyze=True,
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    for day in (1, 31):
        MetaInsightPoint.objects.create(
            tenant=tenant,
            page=page,
            metric_key="page_media_view",
            period="day",
            end_time=datetime(2026, 5, day, 12, tzinfo=dt_timezone.utc),
            value_num=100,
        )
    MetaPost.objects.create(
        tenant=tenant,
        page=page,
        post_id="page-123_1",
        message="Stored post without insights",
        created_time=datetime(2026, 5, 15, 12, tzinfo=dt_timezone.utc),
        last_synced_at=timezone.now(),
    )

    workspace = ContentWorkspace.all_objects.create(tenant=tenant, name="SLB Content")
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="SLB May post",
        state=ContentDraft.STATE_PUBLISHED,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="SLB May post",
    )
    published_post = PublishedPost.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        draft=draft,
        version=version,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id="page-123_1",
        published_at=datetime(2026, 5, 15, 12, tzinfo=dt_timezone.utc),
        reporting_link_state=PublishedPost.REPORTING_LINKED,
    )
    for day in (1, 31):
        OrganicPostMetricSnapshot.all_objects.create(
            tenant=tenant,
            published_post=published_post,
            metric_date=datetime(2026, 5, day).date(),
            channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
            impressions=100,
            reach=80,
            engagements=10,
            clicks=3,
            source="meta_page_post_insights",
        )

    response = api_client.get(
        reverse("report-definition-data-availability"),
        {
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["datasets"]["paid_meta_ads"]["coverage_status"] == "partial"
    assert payload["datasets"]["paid_meta_ads"]["coverage_gap"]["missing_day_count"] == 29
    assert (
        payload["datasets"]["organic_facebook_page"]["coverage_status"] == "partial"
    )
    assert (
        payload["datasets"]["organic_facebook_page"]["coverage_gap"][
            "missing_day_count"
        ]
        == 29
    )
    assert payload["datasets"]["content_ops"]["coverage_status"] == "partial"
    assert payload["datasets"]["content_ops"]["coverage_gap"]["missing_day_count"] == 29
    assert payload["datasets"]["organic_facebook_posts"]["coverage_status"] == "partial"
    assert "paid_meta_ads" in payload["warning_datasets"]
    assert "organic_facebook_page" in payload["blocking_datasets"]
    assert "content_ops" in payload["blocking_datasets"]
    assert "organic_facebook_posts" in payload["blocking_datasets"]
    assert payload["eligible_for_report_export"] is False


def test_report_data_availability_treats_partial_paid_meta_as_warning(
    api_client, user, tenant
):
    authenticate(api_client, user)
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="SLB Meta Account",
        currency="USD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        external_id="paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=10,
        impressions=100,
        clicks=5,
    )
    connection = MetaConnection(
        tenant=tenant, user=user, app_scoped_user_id="meta-user"
    )
    connection.set_raw_token("meta-user-token")
    connection.scopes = ["pages_show_list", "pages_read_engagement"]
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="page-123",
        name="SLB Facebook Page",
        can_analyze=True,
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    post = MetaPost.objects.create(
        tenant=tenant,
        page=page,
        post_id="page-123_1",
        message="Stored post with edge engagement",
        created_time=datetime(2026, 5, 15, 12, tzinfo=dt_timezone.utc),
        last_synced_at=timezone.now(),
    )
    for day in range(1, 32):
        MetaInsightPoint.objects.create(
            tenant=tenant,
            page=page,
            metric_key="page_follows",
            period="day",
            end_time=datetime(2026, 5, day, 12, tzinfo=dt_timezone.utc),
            value_num=100,
        )
        MetaPostInsightPoint.objects.create(
            tenant=tenant,
            post=post,
            metric_key="post_reactions_total",
            period="lifetime",
            end_time=datetime(2026, 5, day, 12, tzinfo=dt_timezone.utc),
            value_num=7,
        )

    workspace = ContentWorkspace.all_objects.create(tenant=tenant, name="SLB Content")
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="SLB May post",
        state=ContentDraft.STATE_PUBLISHED,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="SLB May post",
    )
    published_post = PublishedPost.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        draft=draft,
        version=version,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id="page-123_1",
        published_at=datetime(2026, 5, 15, 12, tzinfo=dt_timezone.utc),
        reporting_link_state=PublishedPost.REPORTING_LINKED,
    )
    for day in range(1, 32):
        OrganicPostMetricSnapshot.all_objects.create(
            tenant=tenant,
            published_post=published_post,
            metric_date=datetime(2026, 5, day).date(),
            channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
            impressions=100,
            reach=80,
            engagements=10,
            clicks=3,
            source="meta_page_post_insights",
        )

    response = api_client.get(
        reverse("report-definition-data-availability"),
        {
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["datasets"]["paid_meta_ads"]["coverage_status"] == "partial"
    assert payload["datasets"]["paid_meta_ads"]["coverage_gap"] == {
        "requested_day_count": 31,
        "covered_day_count": 1,
        "missing_day_count": 30,
        "missing_start_date": "2026-05-01",
        "missing_end_date": "2026-05-30",
        "missing_dates": [
            "2026-05-01",
            "2026-05-02",
            "2026-05-03",
            "2026-05-04",
            "2026-05-05",
            "2026-05-06",
            "2026-05-07",
            "2026-05-08",
            "2026-05-09",
            "2026-05-10",
            "2026-05-11",
            "2026-05-12",
            "2026-05-13",
            "2026-05-14",
            "2026-05-15",
            "2026-05-16",
            "2026-05-17",
            "2026-05-18",
            "2026-05-19",
            "2026-05-20",
            "2026-05-21",
            "2026-05-22",
            "2026-05-23",
            "2026-05-24",
            "2026-05-25",
            "2026-05-26",
            "2026-05-27",
            "2026-05-28",
            "2026-05-29",
            "2026-05-30",
        ],
        "missing_dates_truncated": False,
        "has_leading_gap": True,
        "has_trailing_gap": False,
    }
    assert payload["warning_datasets"] == ["paid_meta_ads"]
    assert payload["blocking_datasets"] == []
    assert payload["eligible_for_report_export"] is True


def test_report_data_availability_diagnoses_requested_paid_account_without_rows(
    api_client, user, tenant
):
    authenticate(api_client, user)
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_791712443035541",
        account_id="791712443035541",
        name="Students' Loan Bureau (SLB)",
        currency="JMD",
    )
    other_account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_697812007883214",
        account_id="697812007883214",
        name="JDIC Meta Account",
        currency="JMD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=other_account,
        external_id="jdic-paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=10,
        impressions=100,
        clicks=5,
    )

    response = api_client.get(
        reverse("report-definition-data-availability"),
        {
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_791712443035541",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    paid = payload["datasets"]["paid_meta_ads"]
    assert paid["row_count"] == 0
    assert paid["coverage_status"] == "missing_history"
    paid_metrics = report_metric_availability_by_key(paid)
    assert paid_metrics["spend"]["availability_state"] == "callable_no_data"
    assert paid_metrics["reach"]["availability_state"] == "callable_no_data"
    assert paid["available_accounts"][0]["external_id"] == "act_697812007883214"
    assert paid["scope_diagnostic"]["code"] == "requested_account_no_rows"
    assert paid["scope_diagnostic"]["available_account_count"] == 1
    requested_account = paid["scope_diagnostic"]["requested_account"]
    assert requested_account["id"]
    assert requested_account["account_id"] == "791712443035541"
    assert requested_account["external_id"] == "act_791712443035541"
    assert requested_account["name"] == "Students' Loan Bureau (SLB)"
    assert requested_account["currency"] == "JMD"
    assert paid["scope_diagnostic"]["credential_status"] == {
        "status": "missing",
        "provider": "META",
        "matched_account_id": None,
        "token_status": None,
        "last_validated_at": None,
    }
    assert "paid_meta_ads" not in payload["blocking_datasets"]
    assert "paid_meta_ads" in payload["warning_datasets"]
    assert payload["eligible_for_report_export"] is True
    assert_report_payload_excludes_sensitive_values(payload)


def test_report_data_availability_scopes_paid_rows_by_client_link(
    api_client, user, tenant
):
    authenticate(api_client, user)
    selected_account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="SLB Meta Account",
        currency="JMD",
    )
    other_account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_999",
        account_id="999",
        name="Other Meta Account",
        currency="JMD",
    )
    client = Client.all_objects.create(tenant=tenant, name="SLB", slug="slb")
    ClientPlatformAccount.all_objects.create(
        tenant=tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS,
        external_id="act_123",
    )
    for account in (selected_account, other_account):
        RawPerformanceRecord.objects.create(
            tenant=tenant,
            ad_account=account,
            external_id=f"paid-{account.account_id}",
            date=datetime(2026, 5, 31).date(),
            level="campaign",
            source="meta",
            spend=10,
            impressions=100,
            clicks=5,
        )

    response = api_client.get(
        reverse("report-definition-data-availability"),
        {
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-31",
            "end_date": "2026-05-31",
            "client_id": str(client.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    paid = payload["datasets"]["paid_meta_ads"]
    assert paid["row_count"] == 1
    assert paid["coverage_status"] == "fresh"
    assert "scope_diagnostic" not in paid
    assert {account["external_id"] for account in paid["available_accounts"]} == {
        "act_123",
        "act_999",
    }
    assert "paid_meta_ads" not in payload["blocking_datasets"]
    assert "paid_meta_ads" not in payload["warning_datasets"]
    assert_report_payload_excludes_sensitive_values(payload)


def test_report_data_availability_treats_missing_slb_organic_content_as_warnings(
    api_client, user, tenant
):
    authenticate(api_client, user)
    seed_slb_paid_only_sources(tenant=tenant, user=user)

    response = api_client.get(
        reverse("report-definition-data-availability"),
        {
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["datasets"]["paid_meta_ads"]["coverage_status"] == "partial"
    paid_metrics = report_metric_availability_by_key(
        payload["datasets"]["paid_meta_ads"]
    )
    assert paid_metrics["spend"]["availability_state"] == "available"
    assert paid_metrics["conversion_value"]["availability_state"] == "callable_no_data"
    assert (
        payload["datasets"]["organic_facebook_page"]["coverage_status"]
        == "missing_history"
    )
    page_metrics = report_metric_availability_by_key(
        payload["datasets"]["organic_facebook_page"]
    )
    assert page_metrics["page_follows"]["availability_state"] == "callable_no_data"
    assert page_metrics["page_reach"]["availability_state"] == "permission_gated"
    assert (
        payload["datasets"]["organic_facebook_posts"]["coverage_status"]
        == "missing_history"
    )
    post_metrics = report_metric_availability_by_key(
        payload["datasets"]["organic_facebook_posts"]
    )
    assert post_metrics["post_activity"]["availability_state"] == "callable_no_data"
    assert post_metrics["post_reactions"]["availability_state"] == "callable_no_data"
    assert payload["datasets"]["content_ops"]["coverage_status"] == "missing_history"
    content_metrics = report_metric_availability_by_key(
        payload["datasets"]["content_ops"]
    )
    assert (
        content_metrics["published_posts"]["availability_state"] == "callable_no_data"
    )
    assert (
        content_metrics["content_ops_engagements"]["availability_state"]
        == "callable_no_data"
    )
    assert payload["blocking_datasets"] == []
    assert payload["warning_datasets"] == [
        "paid_meta_ads",
        "organic_facebook_page",
        "organic_facebook_posts",
        "content_ops",
    ]
    assert payload["eligible_for_report_export"] is True


def test_report_data_availability_rejects_cross_tenant_page(api_client, user, tenant):
    authenticate(api_client, user)
    other_tenant = Tenant.objects.create(name="Other tenant")
    other_user = create_user_with_role(
        tenant=other_tenant,
        email="other-reporting@example.com",
        role_name=Role.ADMIN,
    )
    connection = MetaConnection(
        tenant=other_tenant, user=other_user, app_scoped_user_id="other"
    )
    connection.set_raw_token("other-token")
    connection.scopes = ["pages_show_list", "pages_read_engagement"]
    connection.save()
    page = MetaPage(
        tenant=other_tenant,
        connection=connection,
        page_id="other-page",
        name="Other Page",
        can_analyze=True,
    )
    page.set_raw_page_token("other-page-token")
    page.save()

    response = api_client.get(
        reverse("report-definition-data-availability"),
        {
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "page_id": "other-page",
        },
    )

    assert response.status_code == 400
    assert "page_id does not belong to the authenticated tenant" in str(response.json())


def test_report_create_from_template_persists_source_scope(api_client, user):
    authenticate(api_client, user)

    response = api_client.post(
        reverse("report-definition-from-template"),
        {
            "template_key": "slb_monthly_social_report",
            "name": "Scoped SLB report",
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["filters"] == {
        "date_range": "custom",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "client_id": "",
        "account_id": "act_123",
        "page_id": "page-123",
        "template_key": "slb_monthly_social_report",
    }


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
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_111",
        account_id="111",
        name="SLB Meta Account",
    )
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_222",
        account_id="222",
        name="Other Meta Account",
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB preview",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    response = api_client.post(
        reverse("report-definition-preview", args=[report.id]), {}, format="json"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["schema_version"] == "report.v1"
    assert payload["pages"][0]["id"] == "cover"
    assert payload["pages"][-1]["id"] == "appendix"
    assert payload["coverage_summary"]["by_status"]
    assert payload["export_ready"] is False
    assert payload["blocking_reasons"]
    assert any(
        "SLB paid Meta widgets require account_id or client_id scope" in reason
        for reason in payload["blocking_reasons"]
    )
    assert not any(
        "content_ops" in reason and "missing_history" in reason
        for reason in payload["blocking_reasons"]
    )
    assert not any(
        "organic_facebook_page" in reason and "missing_history" in reason
        for reason in payload["blocking_reasons"]
    )
    datasets = {row["dataset"] for row in payload["coverage_summary"]["datasets"]}
    assert {"organic_facebook_page", "content_ops"} <= datasets
    paid_widgets = [
        widget
        for page in payload["pages"]
        for section in page["sections"]
        for widget in section["widgets"]
        if widget["dataset"] == "paid_meta_ads"
    ]
    assert paid_widgets
    assert {widget["status"] for widget in paid_widgets} == {"blocked"}
    content_ops_coverage = next(
        row
        for row in payload["coverage_summary"]["datasets"]
        if row["dataset"] == "content_ops"
    )
    assert content_ops_coverage["row_count"] == 0
    assert content_ops_coverage["covered_start_date"] is None
    assert content_ops_coverage["covered_end_date"] is None
    assert content_ops_coverage["statuses"] == {"missing_history": 1}
    top_posts_widget = next(
        widget
        for page in payload["pages"]
        for section in page["sections"]
        for widget in section["widgets"]
        if widget["widget_id"] == "top_posts_table"
    )
    assert top_posts_widget["metrics"] == [
        "post_reactions",
        "post_comments",
        "post_shares",
    ]
    assert top_posts_widget["dimensions"] == ["post"]


def test_report_diagnostics_reuses_cached_preview_snapshot(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    cache.clear()
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_111",
        account_id="111",
        name="SLB Meta Account",
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB cached preview",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    calls = {"count": 0}
    original = report_preview_module._preview_report_widget

    def counted_preview_widget(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        report_preview_module, "_preview_report_widget", counted_preview_widget
    )

    preview_response = api_client.post(
        reverse("report-definition-preview", args=[report.id]), {}, format="json"
    )
    preview_calls = calls["count"]
    diagnostics_response = api_client.get(
        reverse("report-definition-diagnostics", args=[report.id])
    )

    assert preview_response.status_code == 200
    assert diagnostics_response.status_code == 200
    assert preview_calls > 0
    assert calls["count"] == preview_calls


def test_report_preview_cache_invalidates_after_report_update(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    cache.clear()
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_111",
        account_id="111",
        name="SLB Meta Account",
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB cache invalidation",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    calls = {"count": 0}
    original = report_preview_module._preview_report_widget

    def counted_preview_widget(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        report_preview_module, "_preview_report_widget", counted_preview_widget
    )

    first_response = api_client.post(
        reverse("report-definition-preview", args=[report.id]), {}, format="json"
    )
    first_calls = calls["count"]
    report.name = "SLB cache invalidation renamed"
    report.save(update_fields=["name", "updated_at"])
    second_response = api_client.post(
        reverse("report-definition-preview", args=[report.id]), {}, format="json"
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_calls > 0
    assert calls["count"] > first_calls


def test_report_preview_marks_require_full_coverage_widget_blocked(
    api_client, user, tenant
):
    authenticate(api_client, user)
    layout = build_slb_monthly_report_layout(date_range="last_month")
    layout["widgets"][1]["coverage_policy"] = "require_full_coverage"
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB blocked preview",
        filters={"date_range": "last_month"},
        layout=layout,
    )

    response = api_client.post(
        reverse("report-definition-preview", args=[report.id]), {}, format="json"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["export_ready"] is False
    assert any(
        "require_full_coverage" in reason for reason in payload["blocking_reasons"]
    )
    blocked_widgets = [
        widget
        for page in payload["pages"]
        for section in page["sections"]
        for widget in section["widgets"]
        if widget["status"] == "blocked"
    ]
    assert blocked_widgets


def test_report_v1_export_stores_preview_metadata(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB export metadata",
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
        layout=paid_report_v1_layout(),
    )
    SavedReportLayout.objects.create(
        tenant=tenant,
        name="Shared fallback layout",
        config={
            "id": f"report-{report.id}",
            "title": "Shared fallback",
            "cols": 12,
            "rowHeight": 64,
            "widgets": [],
        },
        is_shared=True,
    )
    SavedReportLayout.objects.create(
        tenant=tenant,
        name="Requester layout",
        config={
            "id": f"report-{report.id}",
            "title": "Requester export layout",
            "cols": 12,
            "rowHeight": 64,
            "widgets": [
                {
                    "id": "client-note",
                    "type": "note",
                    "title": "Client narrative",
                    "x": 1,
                    "y": 1,
                    "w": 12,
                    "h": 2,
                    "options": {"text": "Rendered from saved layout."},
                }
            ],
        },
        created_by=user,
        updated_by=user,
    )
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )

    response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["metadata"]["report_preview"]["report_schema_version"] == "report.v1"
    assert (
        payload["metadata"]["report_preview"]["template_key"]
        == "slb_monthly_social_report"
    )
    assert payload["metadata"]["report_preview"]["preview_hash"]
    assert payload["metadata"]["report_preview"]["coverage_summary"]["by_status"]
    assert (
        payload["metadata"]["report_preview"]["report_snapshot"]["pages"][0]["id"]
        == "paid_meta_ads"
    )
    assert (
        payload["metadata"]["report_preview"]["report_snapshot"]["preview_hash"]
        == payload["metadata"]["report_preview"]["preview_hash"]
    )
    report_layout = payload["metadata"]["report_layout"]
    assert report_layout["schema_version"] == "report_layout_snapshot.v1"
    assert report_layout["source"] == "requester_saved_layout"
    assert report_layout["name"] == "Requester layout"
    assert report_layout["config"]["title"] == "Requester export layout"
    widget_ids = [widget["id"] for widget in report_layout["config"]["widgets"]]
    assert widget_ids[0] == "client-note"
    assert report_layout["governed_widget_append_count"] == 4
    assert "paid_summary-spend" in widget_ids
    assert "paid_summary-impressions" in widget_ids
    assert "paid_summary-reach" in widget_ids
    assert "paid_summary-clicks" in widget_ids
    appended_spend = next(
        widget
        for widget in report_layout["config"]["widgets"]
        if widget["id"] == "paid_summary-spend"
    )
    assert appended_spend["y"] > report_layout["config"]["widgets"][0]["y"]


def test_report_v1_saved_layout_snapshot_uses_declared_table_metrics(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB table export layout",
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
        layout={
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
                            "widget_ids": ["paid_campaign_table"],
                        }
                    ],
                }
            ],
            "widgets": [
                {
                    "id": "paid_campaign_table",
                    "type": "data_table",
                    "dataset": "paid_meta_ads",
                    "metrics": ["spend", "impressions"],
                    "dimensions": ["campaign"],
                    "filters": {
                        "date_range": "custom",
                        "start_date": "2026-03-01",
                        "end_date": "2026-03-31",
                    },
                    "coverage_policy": "render_with_warning",
                    "visual": {"title": "Paid campaigns", "row_limit": 10},
                }
            ],
        },
    )
    SavedReportLayout.objects.create(
        tenant=tenant,
        name="Existing client layout",
        config={
            "id": f"report-{report.id}",
            "title": "Existing client layout",
            "cols": 12,
            "rowHeight": 64,
            "widgets": [
                {
                    "id": "client-note",
                    "type": "note",
                    "title": "Client narrative",
                    "x": 1,
                    "y": 1,
                    "w": 12,
                    "h": 2,
                    "options": {"text": "Keep this client note."},
                }
            ],
        },
        created_by=user,
        updated_by=user,
    )
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )

    response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": "csv"},
        format="json",
    )

    assert response.status_code == 201
    report_layout = response.json()["metadata"]["report_layout"]
    appended_table = next(
        widget
        for widget in report_layout["config"]["widgets"]
        if widget["id"] == "paid_campaign_table"
    )
    assert appended_table["source"]["metrics"] == ["spend", "impressions"]
    assert "campaign" not in appended_table["source"]["metrics"]
    assert "date" not in appended_table["source"]["metrics"]
    assert appended_table["options"]["columns"][0]["key"] == "campaign"
    assert report_layout["governed_widget_append_count"] == 1


@pytest.mark.parametrize(
    "export_format",
    [
        ReportExportJob.FORMAT_CSV,
        ReportExportJob.FORMAT_PDF,
        ReportExportJob.FORMAT_PNG,
    ],
)
def test_report_v1_completed_export_preserves_preview_snapshot_hash(
    api_client, user, tenant, tmp_path, monkeypatch, export_format
):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB export reproducibility",
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
        layout=paid_report_v1_layout(),
    )
    SavedReportLayout.objects.create(
        tenant=tenant,
        name="Export visual layout",
        config={
            "id": f"report-{report.id}",
            "title": "Export visual layout",
            "cols": 12,
            "rowHeight": 64,
            "widgets": [
                {
                    "id": "saved-spend",
                    "type": "kpi",
                    "title": "Saved Spend",
                    "x": 1,
                    "y": 1,
                    "w": 3,
                    "h": 2,
                    "data": 100,
                    "options": {"format": "currency", "currency": "JMD"},
                }
            ],
        },
        created_by=user,
        updated_by=user,
    )
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)

    def fail_aggregate_snapshot_export(_tenant_id):
        raise AssertionError(
            "report.v1 exports must render from report_preview.report_snapshot"
        )

    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant", fail_aggregate_snapshot_export
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
            data_path = Path(command[command.index("--data") + 1])
            render_payload = json.loads(data_path.read_text(encoding="utf-8"))
            pdf_path = command[command.index("--out") + 1]
            png_path = command[command.index("--png") + 1]
            assert render_payload["template"] == "report_v1_snapshot"
            assert any(kpi["label"] == "Spend" for kpi in render_payload["kpis"])
            assert (
                render_payload["reportLayout"]["config"]["title"]
                == "Export visual layout"
            )
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
    assert (
        report_preview["report_snapshot"]["preview_hash"]
        == preview_response.json()["preview_hash"]
    )
    assert report_preview["report_snapshot"]["pages"][0]["id"] == "paid_meta_ads"
    assert job.metadata["report_layout"]["config"]["title"] == "Export visual layout"
    assert job.metadata["report_layout_source"] == "requester_saved_layout"


@pytest.mark.parametrize(
    "export_format",
    [
        ReportExportJob.FORMAT_CSV,
        ReportExportJob.FORMAT_PDF,
        ReportExportJob.FORMAT_PNG,
    ],
)
def test_slb_report_v1_export_completes_with_warning_only_coverage(
    api_client, user, tenant, tmp_path, monkeypatch, export_format
):
    authenticate(api_client, user)
    seed_slb_warning_ready_sources(tenant=tenant, user=user)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB May warning-ready export",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
            "template_key": "slb_monthly_social_report",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
    )
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("analytics.tasks._exports_base_dir", lambda: tmp_path)

    def fail_aggregate_snapshot_export(_tenant_id):
        raise AssertionError(
            "report.v1 exports must render from report_preview.report_snapshot"
        )

    monkeypatch.setattr(
        "analytics.tasks._snapshot_payload_for_tenant", fail_aggregate_snapshot_export
    )

    export_response = api_client.post(
        reverse("report-definition-exports", args=[report.id]),
        {"export_format": export_format},
        format="json",
    )
    assert export_response.status_code == 201
    report_preview = export_response.json()["metadata"]["report_preview"]
    assert report_preview["export_ready"] is True
    assert report_preview["blocking_reasons"] == []
    assert int(report_preview["coverage_summary"]["by_status"]["partial"]) > 0
    snapshot = report_preview["report_snapshot"]
    assert "unavailable in ADinsights until Meta approves" in str(snapshot["pages"])

    if export_format in {ReportExportJob.FORMAT_PDF, ReportExportJob.FORMAT_PNG}:

        def fake_render(command, **_kwargs):
            data_path = Path(command[command.index("--data") + 1])
            render_payload = json.loads(data_path.read_text(encoding="utf-8"))
            pdf_path = command[command.index("--out") + 1]
            png_path = command[command.index("--png") + 1]
            assert render_payload["template"] == "report_v1_snapshot"
            assert any(kpi["label"] == "Page Follows" for kpi in render_payload["kpis"])
            assert any(
                "unavailable in ADinsights until Meta approves" in row["value"]
                for row in render_payload["rows"]
            )
            Path(pdf_path).write_bytes(b"pdf artifact")
            Path(png_path).write_bytes(b"png artifact")

        monkeypatch.setattr("analytics.tasks.subprocess.run", fake_render)

    result = run_report_export_job.run(export_response.json()["id"])

    job = ReportExportJob.all_objects.get(id=export_response.json()["id"])
    artifact = tmp_path / job.artifact_path.lstrip("/")
    assert result["status"] == ReportExportJob.STATUS_COMPLETED
    assert job.status == ReportExportJob.STATUS_COMPLETED
    assert artifact.exists()
    assert artifact.stat().st_size > 0
    assert job.metadata["source"] == "report_v1_snapshot"
    assert job.metadata["row_count"] > 0
    assert (
        job.metadata["report_preview"]["preview_hash"] == report_preview["preview_hash"]
    )
    if export_format == ReportExportJob.FORMAT_CSV:
        rows = list(csv.DictReader(artifact.read_text(encoding="utf-8").splitlines()))
        page_follows_rows = [row for row in rows if row["metric_key"] == "page_follows"]
        assert page_follows_rows
        assert float(page_follows_rows[0]["value"]) == 6023
        assert any(
            "unavailable in ADinsights until Meta approves" in row["value"]
            for row in rows
        )


def test_slb_report_export_evidence_command_exports_paid_only_slb_with_warnings(
    tenant, user, tmp_path, settings, monkeypatch
):
    settings.REPORT_EXPORT_ARTIFACT_ROOT = tmp_path
    seed_slb_paid_only_sources(tenant=tenant, user=user)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB paid-only warning export evidence",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
            "template_key": "slb_monthly_social_report",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
    )

    def fake_render(command, **_kwargs):
        data_path = Path(command[command.index("--data") + 1])
        render_payload = json.loads(data_path.read_text(encoding="utf-8"))
        pdf_path = command[command.index("--out") + 1]
        png_path = command[command.index("--png") + 1]
        assert render_payload["template"] == "report_v1_snapshot"
        assert any(
            "no retained rows" in warning for warning in render_payload["warnings"]
        )
        Path(pdf_path).write_bytes(b"pdf artifact")
        Path(png_path).write_bytes(b"png artifact")

    monkeypatch.setattr("analytics.tasks.subprocess.run", fake_render)
    output = StringIO()

    call_command(
        "slb_report_export_evidence",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_export_evidence_run.v1"
    assert payload["export_ready"] is True
    assert payload["blocking_reasons"] == []
    assert any("no retained rows" in warning for warning in payload["warnings"])
    assert set(payload["exports"]) == {"csv", "pdf", "png"}
    for export_row in payload["exports"].values():
        assert export_row["status"] == ReportExportJob.STATUS_COMPLETED
        assert export_row["byte_count"] > 0
        assert export_row["row_count"] > 0
        assert export_row["preview_hash"] == payload["preview_hash"]
        assert export_row["snapshot_preview_hash"] == payload["preview_hash"]
    assert payload["delivery"]["scheduled_dry_run_status"] == "rendered"
    assert payload["scheduled_dry_run"]["byte_count"] > 0
    assert_report_payload_excludes_sensitive_values(payload)


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
                "rows": [
                    {"date": "2026-05-31", "campaign": "SLB Awareness", "spend": 1200}
                ],
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
            "delivery_status": {
                "mode": "dry_run",
                "status": "rendered",
                "sanitized": True,
            },
        },
    )

    response = api_client.get(
        reverse("report-definition-diagnostics", args=[report.id])
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["schema_version"] == "report.v1"
    assert payload["preview_hash"]
    assert {row["dataset"] for row in payload["datasets"]} >= {
        "paid_meta_ads",
        "organic_facebook_page",
        "content_ops",
    }
    paid_diagnostics = next(
        row for row in payload["datasets"] if row["dataset"] == "paid_meta_ads"
    )
    assert paid_diagnostics["last_successful_sync_at"] == generated_at.isoformat()
    content_ops_diagnostics = next(
        row for row in payload["datasets"] if row["dataset"] == "content_ops"
    )
    assert content_ops_diagnostics["coverage_status"] == "missing_history"
    assert content_ops_diagnostics["row_count"] == 0
    assert content_ops_diagnostics["retained_range"] == {
        "start_date": None,
        "end_date": None,
    }
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

    response = api_client.get(
        reverse("report-definition-diagnostics", args=[report.id])
    )

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
    remediation_actions = source_health["remediation_actions"]
    remediation_codes = {row["code"] for row in remediation_actions}
    assert {
        "manual_meta_organic_csv_import",
        "manual_meta_organic_csv_import_posts",
        "slb_page_insights_backfill",
        "slb_post_engagement_backfill",
        "content_ops_from_synced_posts",
    } <= remediation_codes
    manual_import = next(
        row
        for row in remediation_actions
        if row["code"] == "manual_meta_organic_csv_import"
    )
    assert "import_meta_organic_csv" in manual_import["command_template"]
    assert "<tenant_uuid>" in manual_import["command_template"]
    assert "<facebook_page_id>" in manual_import["command_template"]
    assert "--dry-run" not in manual_import["command_template"]
    assert "import_meta_organic_csv" in manual_import["dry_run_command_template"]
    assert "<tenant_uuid>" in manual_import["dry_run_command_template"]
    assert "<facebook_page_id>" in manual_import["dry_run_command_template"]
    assert "--dry-run" in manual_import["dry_run_command_template"]
    backfill = next(
        row
        for row in remediation_actions
        if row["code"] == "slb_post_engagement_backfill"
    )
    assert "slb_backfill_meta_reporting" in backfill["command_template"]
    assert "--dispatch-mode inline" in backfill["command_template"]
    assert "--dispatch-mode dry-run" in backfill["dry_run_command_template"]
    assert "page-current" not in json.dumps(remediation_actions)


def test_report_diagnostics_source_health_names_selected_paid_account_blocker(
    api_client, user, tenant
):
    authenticate(api_client, user)
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_791712443035541",
        account_id="791712443035541",
        name="Students' Loan Bureau (SLB)",
        currency="JMD",
    )
    other_account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_697812007883214",
        account_id="697812007883214",
        name="JDIC Meta Account",
        currency="JMD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=other_account,
        external_id="jdic-paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=10,
        impressions=100,
        clicks=5,
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB scoped diagnostics",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_791712443035541",
            "template_key": "slb_monthly_social_report",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
    )

    response = api_client.get(
        reverse("report-definition-diagnostics", args=[report.id])
    )

    assert response.status_code == 200
    source_health = response.json()["source_health"]
    paid_scope = source_health["report_scope"]["paid_meta_ads"]
    assert paid_scope["account_scope_present"] is True
    assert paid_scope["client_scope_present"] is False
    assert paid_scope["date_filter_applied"] is True
    assert paid_scope["scoped_rows"]["row_count"] == 0
    assert paid_scope["credential_status"] == {
        "status": "missing",
        "provider": "META",
        "matched": False,
        "token_status": None,
        "last_validated_at": None,
    }
    assert paid_scope["backfill_status"] == "blocked_missing_credential"
    assert "Reconnect/select the selected SLB Meta ad account" in " ".join(
        source_health["recommended_next_actions"]
    )
    paid_backfill = next(
        row
        for row in source_health["remediation_actions"]
        if row["code"] == "slb_paid_meta_backfill"
    )
    assert paid_backfill["dataset"] == "paid_meta_ads"
    assert "slb_backfill_meta_reporting" in paid_backfill["command_template"]
    assert "<meta_ad_account_id>" in paid_backfill["command_template"]
    assert "--dispatch-mode inline" in paid_backfill["command_template"]
    assert "--dispatch-mode dry-run" in paid_backfill["dry_run_command_template"]
    assert paid_backfill["prerequisites"] == [
        "Reconnect/select the selected SLB Meta ad account so a retained credential exists."
    ]
    manual_paid_import = next(
        row
        for row in source_health["remediation_actions"]
        if row["code"] == "manual_meta_paid_csv_import"
    )
    assert manual_paid_import["dataset"] == "paid_meta_ads"
    assert "import_meta_paid_csv" in manual_paid_import["command_template"]
    assert "<meta_ad_account_id>" in manual_paid_import["command_template"]
    assert "--dry-run" not in manual_paid_import["command_template"]
    assert "import_meta_paid_csv" in manual_paid_import["dry_run_command_template"]
    assert "<meta_ad_account_id>" in manual_paid_import["dry_run_command_template"]
    assert "--dry-run" in manual_paid_import["dry_run_command_template"]
    assert manual_paid_import["no_live_provider_calls"] is True
    serialized_source_health = json.dumps(source_health, default=str).lower()
    assert "act_791712443035541" not in serialized_source_health
    assert "791712443035541" not in serialized_source_health
    assert "act_697812007883214" not in serialized_source_health
    assert "697812007883214" not in serialized_source_health
    assert_report_payload_excludes_sensitive_values(response.json())


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

    response = api_client.get(
        reverse("report-definition-diagnostics", args=[report.id])
    )

    assert response.status_code == 200
    actions = " ".join(response.json()["source_health"]["recommended_next_actions"])
    assert (
        "Meta Page Insights sync has run, but Graph returned no Page insight metric rows"
        in actions
    )
    assert "Backfill Facebook Page Insights stored rows" not in actions
    assert (
        "Facebook posts are stored, but Meta returned no post insight metric rows"
        in actions
    )
    source_health = response.json()["source_health"]
    remediation_codes = {row["code"] for row in source_health["remediation_actions"]}
    assert "manual_meta_organic_csv_import" in remediation_codes
    assert "manual_meta_organic_csv_import_posts" in remediation_codes
    assert "content_ops_from_synced_posts" in remediation_codes
    organic_scope = source_health["report_scope"]["organic_facebook_page"]
    assert organic_scope["page_scope_present"] is False
    assert organic_scope["available_page_count"] == 1
    assert organic_scope["matched_page_count"] == 0
    assert organic_scope["backfill_status"] == "blocked_missing_scope"
    assert organic_scope["scoped_rows"]["row_count"] == 0
    organic_page_action = next(
        row
        for row in source_health["remediation_actions"]
        if row["code"] == "manual_meta_organic_csv_import"
    )
    assert organic_page_action["prerequisites"] == [
        "Select the tenant-owned SLB Facebook Page on the report before running this action.",
        "Do not import SLB source values into another tenant Page.",
    ]
    content_ops_action = next(
        row
        for row in source_health["remediation_actions"]
        if row["code"] == "content_ops_from_synced_posts"
    )
    assert content_ops_action["prerequisites"] == []
    assert "--dispatch-mode inline" in content_ops_action["command_template"]
    assert "--dispatch-mode dry-run" in content_ops_action["dry_run_command_template"]
    assert "page-current" not in json.dumps(source_health["remediation_actions"])


def test_report_diagnostics_explains_empty_graph_posts_after_sync(
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
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB diagnostics synced empty posts",
        filters={"date_range": "last_month"},
        layout=build_slb_monthly_report_layout(date_range="last_month"),
    )

    response = api_client.get(
        reverse("report-definition-diagnostics", args=[report.id])
    )

    assert response.status_code == 200
    actions = " ".join(response.json()["source_health"]["recommended_next_actions"])
    assert (
        "Meta Page Insights sync has run, but Graph returned no Page insight metric rows"
        in actions
    )
    assert "Meta Page posts sync has run, but Graph returned no Page posts" in actions
    assert (
        "Content Ops cannot import published activity because Meta returned no Page posts"
        in actions
    )
    assert "Backfill Facebook post insight rows" not in actions
    assert "Generate or backfill Content Ops aggregate snapshots" not in actions
    content_ops_action = next(
        row
        for row in response.json()["source_health"]["remediation_actions"]
        if row["code"] == "content_ops_from_synced_posts"
    )
    assert content_ops_action["prerequisites"] == [
        "Run organic_facebook_posts backfill or manual post CSV import first."
    ]


def test_scheduled_report_dry_run_creates_sanitized_export_evidence(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB scheduled dry-run",
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
        layout=paid_report_v1_layout(),
        schedule_enabled=True,
        delivery_emails=["ops@example.com"],
    )
    SavedReportLayout.objects.create(
        tenant=tenant,
        name="Scheduled requester layout",
        config={
            "id": f"report-{report.id}",
            "title": "Scheduled requester layout",
            "cols": 12,
            "rowHeight": 64,
            "widgets": [
                {
                    "id": "scheduled-note",
                    "type": "note",
                    "title": "Scheduled note",
                    "x": 1,
                    "y": 1,
                    "w": 12,
                    "h": 2,
                    "options": {"text": "Custom scheduled layout."},
                }
            ],
        },
        created_by=user,
        updated_by=user,
    )
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )

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
    assert payload["metadata"]["report_layout"]["governed_widget_append_count"] == 4
    scheduled_widget_ids = [
        widget["id"] for widget in payload["metadata"]["report_layout"]["config"]["widgets"]
    ]
    assert "paid_summary-spend" in scheduled_widget_ids
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
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
        layout=paid_report_v1_layout(),
        schedule_enabled=True,
        delivery_emails=["ops@example.com"],
    )
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
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
        raise AssertionError(
            "coverage-blocked dry-run must not enqueue export rendering"
        )

    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", fail_export_enqueue
    )

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
    assert any(
        "require_full_coverage" in reason
        for reason in payload["metadata"]["blocking_reasons"]
    )
    assert "ops@example.com" not in serialized_metadata
    assert "delivery_emails" not in serialized_metadata
    report.refresh_from_db()
    assert report.last_scheduled_at is not None


def test_report_preview_export_diagnostics_dry_run_and_parity_outputs_are_redacted(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )
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
    diagnostics_response = api_client.get(
        reverse("report-definition-diagnostics", args=[report.id])
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
    assert diagnostics_response.status_code == 200
    assert export_response.status_code == 201
    assert dry_run_response.status_code == 201
    assert_report_payload_excludes_sensitive_values(preview_response.json())
    assert_report_payload_excludes_sensitive_values(diagnostics_response.json())
    assert_report_payload_excludes_sensitive_values(export_response.json()["metadata"])
    assert_report_payload_excludes_sensitive_values(dry_run_response.json()["metadata"])
    assert_report_payload_excludes_sensitive_values(
        json.loads(parity_output.getvalue())
    )
    assert_report_payload_excludes_sensitive_values(
        json.loads(evidence_bundle_output.getvalue())
    )
    assert export_response.json()["metadata"]["report_preview"]["report_snapshot"][
        "pages"
    ]
    assert dry_run_response.json()["metadata"]["delivery_status"] == {
        "mode": "dry_run",
        "status": "queued",
        "sanitized": True,
    }


def test_report_preview_export_dry_run_and_parity_do_not_call_live_providers(
    api_client, user, tenant, monkeypatch
):
    authenticate(api_client, user)
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )
    seed_paid_report_snapshot(tenant=tenant)
    block_live_network_calls(monkeypatch)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB stored-data-only report",
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
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
    assert export_response.json()["metadata"]["report_preview"]["report_snapshot"][
        "pages"
    ]
    assert dry_run_response.json()["metadata"]["report_preview"]["report_snapshot"][
        "pages"
    ]
    assert json.loads(parity_output.getvalue())["rows"]
    assert json.loads(evidence_bundle_output.getvalue())["parity_rows"]


@pytest.mark.parametrize(
    ("route_name", "payload", "expected_message"),
    [
        ("report-definition-preview", {}, "Report preview quota exceeded"),
        (
            "report-definition-exports",
            {"export_format": "csv"},
            "Report export quota exceeded",
        ),
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
    monkeypatch.setattr(
        "analytics.phase2_views._check_report_action_quota",
        lambda **_kwargs: (False, 999),
    )

    response = api_client.post(
        reverse(route_name, args=[report.id]), payload, format="json"
    )

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

    detail_response = api_client.get(
        reverse("report-definition-detail", args=[report.id])
    )
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
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )
    seed_paid_report_snapshot(tenant=tenant)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="Role-separated SLB report",
        filters={
            "date_range": "custom",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
        layout=paid_report_v1_layout(),
    )

    viewer = create_viewer(tenant=tenant, email="viewer2@example.com")
    authenticate(api_client, viewer)

    assert (
        api_client.get(
            reverse("report-definition-detail", args=[report.id])
        ).status_code
        == 200
    )
    assert (
        api_client.get(
            reverse("report-definition-exports", args=[report.id])
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            reverse("report-definition-preview", args=[report.id]), {}, format="json"
        ).status_code
        == 403
    )
    assert (
        api_client.get(
            reverse("report-definition-diagnostics", args=[report.id])
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            reverse("report-definition-exports", args=[report.id]),
            {"export_format": "csv"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            reverse("report-definition-scheduled-dry-run", args=[report.id]),
            {"export_format": "pdf"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            reverse("report-definition-toggle-schedule", args=[report.id]),
            {"enabled": True},
            format="json",
        ).status_code
        == 403
    )
    assert (
        api_client.patch(
            reverse("report-definition-detail", args=[report.id]),
            {"description": "viewer should not edit"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            reverse("report-definition-detail", args=[report.id])
        ).status_code
        == 403
    )

    analyst = create_user_with_role(
        tenant=tenant, email="analyst@example.com", role_name=Role.ANALYST
    )
    authenticate(api_client, analyst)

    assert (
        api_client.post(
            reverse("report-definition-preview", args=[report.id]), {}, format="json"
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            reverse("report-definition-exports", args=[report.id]),
            {"export_format": "csv"},
            format="json",
        ).status_code
        == 201
    )
    assert (
        api_client.patch(
            reverse("report-definition-detail", args=[report.id]),
            {"description": "analyst edit allowed"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            reverse("report-definition-scheduled-dry-run", args=[report.id]),
            {"export_format": "pdf"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            reverse("report-definition-detail", args=[report.id])
        ).status_code
        == 403
    )


def test_report_admin_schedule_and_delete_are_audited_with_redacted_metadata(
    api_client, user, tenant
):
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
    delete_response = api_client.delete(
        reverse("report-definition-detail", args=[report.id])
    )

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
    monkeypatch.setattr(
        "analytics.tasks.run_report_export_job.delay", lambda *_args, **_kwargs: None
    )
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
    report.filters = {
        "date_range": "custom",
        "start_date": "2026-03-01",
        "end_date": "2026-03-31",
    }
    report.layout = paid_report_v1_layout()
    report.delivery_emails = ["ops@example.com"]
    report.schedule_enabled = True
    report.save(
        update_fields=[
            "filters",
            "layout",
            "delivery_emails",
            "schedule_enabled",
            "updated_at",
        ]
    )

    preview_response = api_client.post(
        reverse("report-definition-preview", args=[report_id]),
        {"date_range": "custom", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        format="json",
    )
    diagnostics_response = api_client.get(
        reverse("report-definition-diagnostics", args=[report_id])
    )
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
        "report_previewed": {
            "schema_version",
            "export_ready",
            "preview_hash",
            "redacted",
        },
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
        response = request(
            reverse(route_name, args=[other_report.id]), payload, format="json"
        )

    assert response.status_code == 404
    assert str(other_report.id) not in str(
        response.json() if hasattr(response, "json") else ""
    )


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
    assert all(
        row["result"] == "blocked_missing_dashthis_value" for row in payload["rows"]
    )
    no_data_rows = [
        row
        for row in payload["rows"]
        if row["coverage_status"] in {"missing_history", "not_previously_synced"}
    ]
    assert no_data_rows
    assert all(row["adinsights_value"] is None for row in no_data_rows)
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


def test_slb_report_target_intake_command_outputs_redacted_g1_candidate(
    tenant, monkeypatch
):
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

    call_command(
        "slb_report_target_intake", "--report-id", str(report.id), stdout=output
    )

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

    call_command(
        "slb_report_target_intake", "--report-id", str(report.id), stdout=output
    )

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
    assert (
        payload["probes"]["primary_month"]["data_availability"]["schema_version"]
        == "report_data_availability.v1"
    )
    assert (
        payload["probes"]["primary_month"]["data_availability"]["stored_aggregate_only"]
        is True
    )
    assert (
        payload["probes"]["primary_month"]["data_availability"][
            "no_live_provider_calls"
        ]
        is True
    )
    assert payload["probes"]["retained_90_day"]["date_range"] == {
        "date_range": "custom",
        "start_date": "2026-03-01",
        "end_date": "2026-05-31",
    }
    assert (
        payload["probes"]["retained_90_day"]["data_availability"]["requested"][
            "start_date"
        ]
        == "2026-03-01"
    )
    matrix = {row["dataset"]: row for row in payload["dataset_matrix"]}
    assert set(matrix) == {"paid_meta_ads", "organic_facebook_page", "content_ops"}
    assert matrix["paid_meta_ads"]["primary_row_count"] > 0
    assert matrix["paid_meta_ads"]["history_row_count"] > 0
    assert matrix["paid_meta_ads"]["primary_coverage_gap"] == {
        "requested_day_count": 31,
        "covered_day_count": 1,
        "missing_day_count": 30,
        "missing_start_date": "2026-05-01",
        "missing_end_date": "2026-05-30",
        "missing_dates": [
            "2026-05-01",
            "2026-05-02",
            "2026-05-03",
            "2026-05-04",
            "2026-05-05",
            "2026-05-06",
            "2026-05-07",
            "2026-05-08",
            "2026-05-09",
            "2026-05-10",
            "2026-05-11",
            "2026-05-12",
            "2026-05-13",
            "2026-05-14",
            "2026-05-15",
            "2026-05-16",
            "2026-05-17",
            "2026-05-18",
            "2026-05-19",
            "2026-05-20",
            "2026-05-21",
            "2026-05-22",
            "2026-05-23",
            "2026-05-24",
            "2026-05-25",
            "2026-05-26",
            "2026-05-27",
            "2026-05-28",
            "2026-05-29",
            "2026-05-30",
        ],
        "missing_dates_truncated": False,
        "has_leading_gap": True,
        "has_trailing_gap": False,
    }
    paid_summary = next(
        row
        for row in payload["probes"]["primary_month"]["coverage_summary"]["datasets"]
        if row["dataset"] == "paid_meta_ads"
    )
    assert paid_summary["coverage_gap"]["missing_start_date"] == "2026-05-01"
    assert paid_summary["coverage_gap"]["missing_end_date"] == "2026-05-30"
    assert matrix["paid_meta_ads"]["decision"] == "warning_only_retained_history"
    assert (
        matrix["organic_facebook_page"]["decision"] == "warning_only_no_aggregate_rows"
    )
    assert matrix["content_ops"]["decision"] == "warning_only_no_aggregate_rows"
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
    assert source_health["meta_page_connection"]["required_scope_coverage"][
        "missing"
    ] == ["pages_read_engagement"]
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


def test_slb_report_history_probe_includes_paid_scope_data_availability(
    tenant, monkeypatch
):
    block_live_network_calls(monkeypatch)
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_791712443035541",
        account_id="791712443035541",
        name="Students' Loan Bureau (SLB)",
        currency="JMD",
    )
    other_account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_697812007883214",
        account_id="697812007883214",
        name="JDIC Meta Account",
        currency="JMD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=other_account,
        external_id="jdic-paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=10,
        impressions=100,
        clicks=5,
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB scoped history probe",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_791712443035541",
            "template_key": "slb_monthly_social_report",
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
    primary_availability = payload["probes"]["primary_month"]["data_availability"]
    history_availability = payload["probes"]["retained_90_day"]["data_availability"]
    assert primary_availability["requested"]["account_id"] == "act_791712443035541"
    assert history_availability["requested"]["account_id"] == "act_791712443035541"
    assert primary_availability["requested"]["start_date"] == "2026-05-01"
    assert history_availability["requested"]["start_date"] == "2026-03-01"
    assert payload["probes"]["primary_month"]["export_ready"] is True
    assert payload["probes"]["primary_month"]["blocking_reasons"] == []
    assert "paid_meta_ads" not in primary_availability["blocking_datasets"]
    assert "paid_meta_ads" in primary_availability["warning_datasets"]
    paid_matrix = next(
        row for row in payload["dataset_matrix"] if row["dataset"] == "paid_meta_ads"
    )
    assert paid_matrix["decision"] == "warning_only_no_aggregate_rows"
    paid = primary_availability["datasets"]["paid_meta_ads"]
    assert paid["coverage_status"] == "missing_history"
    assert paid["row_count"] == 0
    assert "available_accounts" not in paid
    assert paid["scope_diagnostic"]["code"] == "requested_account_no_rows"
    assert paid["scope_diagnostic"]["available_account_count"] == 1
    assert paid["out_of_scope_retained_rows"] == {
        "reason": "retained_meta_rows_exist_outside_requested_scope",
        "excluded_from_selected_scope": True,
        "account_count": 1,
        "row_count": 1,
        "min_date": "2026-05-31",
        "max_date": "2026-05-31",
        "selected_scope_row_count": 0,
    }
    assert paid["scope_diagnostic"]["credential_status"] == {
        "status": "missing",
        "provider": "META",
        "matched_account_id": None,
        "token_status": None,
        "last_validated_at": None,
    }
    assert_report_payload_excludes_sensitive_values(payload)


def test_slb_report_evidence_bundle_command_outputs_fixed_target_bundle(
    tenant, tmp_path, settings
):
    settings.REPORT_EXPORT_ARTIFACT_ROOT = tmp_path
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
    artifact_path = f"/exports/{tenant.id}/{report.id}/slb-report.csv"
    artifact = tmp_path / artifact_path.lstrip("/")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("section,value\npaid,1\n", encoding="utf-8")
    ReportExportJob.objects.create(
        tenant=tenant,
        report=report,
        export_format=ReportExportJob.FORMAT_CSV,
        status=ReportExportJob.STATUS_COMPLETED,
        artifact_path=artifact_path,
        completed_at=timezone.now(),
        metadata={
            "source": "report_v1_snapshot",
            "row_count": 12,
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
    assert payload["rendering"]["widget_count"] == 12
    rendering_widgets = {
        widget["widget_id"]: widget for widget in payload["rendering"]["widgets"]
    }
    assert len(rendering_widgets) == payload["rendering"]["widget_count"]
    assert rendering_widgets["organic_page_summary"] == {
        "page_id": "executive_summary",
        "section_id": "executive_summary_widgets",
        "widget_id": "organic_page_summary",
        "dataset": "organic_facebook_page",
        "type": "kpi",
        "status": "rendered",
        "declared_metrics": ["page_follows"],
        "declared_dimensions": [],
        "data_kind": "kpi",
        "coverage_status": "missing_history",
        "coverage_row_count": 0,
        "source_label": "Facebook Page Insights stored rows",
        "coverage_note_present": True,
        "warning_count": 1,
    }
    assert rendering_widgets["organic_post_engagement_summary"]["declared_metrics"] == [
        "post_reactions",
        "post_comments",
        "post_shares",
    ]
    assert rendering_widgets["organic_reach_impressions_note"]["note"] == {
        "title": "Reach and impressions availability",
        "body_present": True,
        "mentions_reach_impressions_unavailable": True,
    }
    assert payload["coverage_summary"]["datasets"]
    assert (
        payload["data_availability"]["schema_version"] == "report_data_availability.v1"
    )
    assert payload["data_availability"]["stored_aggregate_only"] is True
    assert payload["data_availability"]["no_live_provider_calls"] is True
    assert payload["diagnostics"]["datasets"]
    assert (
        payload["diagnostics"]["source_health"]["schema_version"]
        == "slb_source_health.v1"
    )
    assert payload["diagnostics"]["source_health"]["stored_aggregate_only"] is True
    assert payload["diagnostics"]["source_health"]["no_live_provider_calls"] is True
    assert payload["parity_rows"]
    assert payload["exports"][0]["artifact_present"] is True
    assert payload["exports"][0]["artifact_size_bytes"] == artifact.stat().st_size
    assert payload["exports"][0]["artifact_path"] == artifact_path
    assert payload["exports"][0]["source"] == "report_v1_snapshot"
    assert payload["exports"][0]["row_count"] == 12
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


def test_slb_report_evidence_bundle_warns_for_missing_paid_scope_data_availability(
    tenant,
):
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_791712443035541",
        account_id="791712443035541",
        name="Students' Loan Bureau (SLB)",
        currency="JMD",
    )
    other_account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_697812007883214",
        account_id="697812007883214",
        name="JDIC Meta Account",
        currency="JMD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=other_account,
        external_id="jdic-paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=10,
        impressions=100,
        clicks=5,
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB warning-only bundle evidence",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_791712443035541",
            "template_key": "slb_monthly_social_report",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
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
    assert payload["export_ready"] is True
    assert payload["blocking_reasons"] == []
    availability = payload["data_availability"]
    assert availability["schema_version"] == "report_data_availability.v1"
    assert availability["stored_aggregate_only"] is True
    assert availability["no_live_provider_calls"] is True
    assert availability["eligible_for_report_export"] is True
    assert availability["requested"]["account_id"] == "act_791712443035541"
    assert "paid_meta_ads" not in availability["blocking_datasets"]
    assert "paid_meta_ads" in availability["warning_datasets"]
    paid = availability["datasets"]["paid_meta_ads"]
    assert paid["coverage_status"] == "missing_history"
    assert paid["row_count"] == 0
    assert "available_accounts" not in paid
    assert paid["scope_diagnostic"]["code"] == "requested_account_no_rows"
    assert paid["scope_diagnostic"]["credential_status"] == {
        "status": "missing",
        "provider": "META",
        "matched_account_id": None,
        "token_status": None,
        "last_validated_at": None,
    }
    assert_report_payload_excludes_sensitive_values(payload)


def test_slb_report_export_evidence_command_generates_warning_only_paid_scope_exports(
    tenant, tmp_path, settings, monkeypatch
):
    settings.REPORT_EXPORT_ARTIFACT_ROOT = tmp_path
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_791712443035541",
        account_id="791712443035541",
        name="Students' Loan Bureau (SLB)",
        currency="JMD",
    )
    other_account = AdAccount.objects.create(
        tenant=tenant,
        external_id="act_697812007883214",
        account_id="697812007883214",
        name="JDIC Meta Account",
        currency="JMD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=other_account,
        external_id="jdic-paid-may-31",
        date=datetime(2026, 5, 31).date(),
        level="campaign",
        source="meta",
        spend=10,
        impressions=100,
        clicks=5,
    )
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB blocked export evidence",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_791712443035541",
            "template_key": "slb_monthly_social_report",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
    )

    def fake_render(command, **_kwargs):
        data_path = Path(command[command.index("--data") + 1])
        render_payload = json.loads(data_path.read_text(encoding="utf-8"))
        pdf_path = command[command.index("--out") + 1]
        png_path = command[command.index("--png") + 1]
        assert render_payload["template"] == "report_v1_snapshot"
        assert any(
            row["page"] == "Paid Meta Ads performance"
            and row["status"] == "not_previously_synced"
            for row in render_payload["rows"]
        )
        Path(pdf_path).write_bytes(b"pdf artifact")
        Path(png_path).write_bytes(b"png artifact")

    monkeypatch.setattr("analytics.tasks.subprocess.run", fake_render)
    output = StringIO()

    call_command(
        "slb_report_export_evidence",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_export_evidence_run.v1"
    assert payload["export_ready"] is True
    assert payload["date_range"] == {
        "date_range": "custom",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }
    assert payload["preview_hash"]
    assert payload["blocking_reasons"] == []
    availability = payload["data_availability"]
    assert availability["schema_version"] == "report_data_availability.v1"
    assert availability["stored_aggregate_only"] is True
    assert availability["no_live_provider_calls"] is True
    assert availability["eligible_for_report_export"] is True
    assert "paid_meta_ads" not in availability["blocking_datasets"]
    assert "paid_meta_ads" in availability["warning_datasets"]
    assert availability["requested"]["account_id"] == "act_791712443035541"
    paid = availability["datasets"]["paid_meta_ads"]
    assert paid["coverage_status"] == "missing_history"
    assert paid["row_count"] == 0
    assert "available_accounts" not in paid
    assert paid["scope_diagnostic"]["code"] == "requested_account_no_rows"
    assert paid["scope_diagnostic"]["available_account_count"] == 1
    assert paid["out_of_scope_retained_rows"] == {
        "reason": "retained_meta_rows_exist_outside_requested_scope",
        "excluded_from_selected_scope": True,
        "account_count": 1,
        "row_count": 1,
        "min_date": "2026-05-31",
        "max_date": "2026-05-31",
        "selected_scope_row_count": 0,
    }
    requested_account = paid["scope_diagnostic"]["requested_account"]
    assert requested_account["id"]
    assert requested_account == {
        "id": requested_account["id"],
        "account_id": "791712443035541",
        "external_id": "act_791712443035541",
        "name": "Students' Loan Bureau (SLB)",
        "currency": "JMD",
    }
    assert paid["scope_diagnostic"]["credential_status"] == {
        "status": "missing",
        "provider": "META",
        "matched_account_id": None,
        "token_status": None,
        "last_validated_at": None,
    }
    assert set(payload["exports"]) == {"csv", "pdf", "png"}
    for export_format, row in payload["exports"].items():
        assert row["format"] == export_format
        assert row["status"] == ReportExportJob.STATUS_COMPLETED
        assert row["byte_count"] > 0
        assert row["source"] == "report_v1_snapshot"
        assert row["row_count"] > 0
        assert row["preview_hash"] == payload["preview_hash"]
        assert row["snapshot_preview_hash"] == payload["preview_hash"]
    assert payload["delivery"]["scheduled_dry_run_status"] == "rendered"
    assert (
        payload["delivery"]["scheduled_dry_run_job_id"]
        == payload["scheduled_dry_run"]["job_id"]
    )
    assert payload["delivery"]["scheduled_dry_run_format"] == ReportExportJob.FORMAT_PDF
    assert payload["delivery"]["sanitized"] is True
    assert payload["scheduled_dry_run"]["status"] == ReportExportJob.STATUS_COMPLETED
    assert payload["scheduled_dry_run"]["byte_count"] > 0
    assert payload["scheduled_dry_run"]["preview_hash"] == payload["preview_hash"]
    assert payload["scheduled_dry_run"]["delivery_status"] == {
        "mode": "dry_run",
        "sanitized": True,
        "status": "rendered",
        "rendered_at": payload["scheduled_dry_run"]["delivery_status"]["rendered_at"],
    }
    assert_report_payload_excludes_sensitive_values(payload)

    assert (
        ReportExportJob.objects.filter(
            report=report,
            status=ReportExportJob.STATUS_COMPLETED,
        ).count()
        == 4
    )

    event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_export_evidence_generated",
        resource_type="report_definition",
        resource_id=report.id,
    )
    assert event.metadata == {
        "redacted": True,
        "formats": ["csv", "pdf", "png"],
        "scheduled_dry_run": True,
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "preview_hash": payload["preview_hash"],
    }
    assert_redacted_report_audit_metadata(event.metadata)


def test_slb_report_export_evidence_command_generates_fixed_target_exports(
    tenant, user, tmp_path, settings, monkeypatch
):
    settings.REPORT_EXPORT_ARTIFACT_ROOT = tmp_path
    seed_slb_warning_ready_sources(tenant=tenant, user=user)
    report = ReportDefinition.objects.create(
        tenant=tenant,
        name="SLB fixed export evidence",
        filters={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_123",
            "page_id": "page-123",
            "template_key": "slb_monthly_social_report",
        },
        layout=build_slb_monthly_report_layout(
            date_range="custom",
            start_date="2026-05-01",
            end_date="2026-05-31",
        ),
    )
    SavedReportLayout.objects.create(
        tenant=tenant,
        name="Shared SLB evidence layout",
        config={
            "id": f"report-{report.id}",
            "title": "Shared SLB evidence layout",
            "cols": 12,
            "rowHeight": 64,
            "widgets": [
                {
                    "id": "client-summary-note",
                    "type": "note",
                    "title": "Client summary",
                    "x": 1,
                    "y": 1,
                    "w": 12,
                    "h": 2,
                    "options": {"text": "Client-facing summary."},
                }
            ],
        },
        is_shared=True,
    )

    def fake_render(command, **_kwargs):
        data_path = Path(command[command.index("--data") + 1])
        render_payload = json.loads(data_path.read_text(encoding="utf-8"))
        pdf_path = command[command.index("--out") + 1]
        png_path = command[command.index("--png") + 1]
        assert render_payload["template"] == "report_v1_snapshot"
        assert render_payload["reportLayout"]["source"] == "shared_saved_layout"
        assert (
            render_payload["reportLayout"]["governed_widget_append_count"] > 0
        )
        widget_ids = [
            widget["id"]
            for widget in render_payload["reportLayout"]["config"]["widgets"]
        ]
        assert widget_ids[0] == "client-summary-note"
        assert "paid_summary-spend" in widget_ids
        Path(pdf_path).write_bytes(b"pdf artifact")
        Path(png_path).write_bytes(b"png artifact")

    monkeypatch.setattr("analytics.tasks.subprocess.run", fake_render)
    output = StringIO()

    call_command(
        "slb_report_export_evidence",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "slb_export_evidence_run.v1"
    assert payload["date_range"] == {
        "date_range": "custom",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }
    assert set(payload["exports"]) == {"csv", "pdf", "png"}
    for export_format, row in payload["exports"].items():
        assert row["format"] == export_format
        assert row["status"] == ReportExportJob.STATUS_COMPLETED
        assert row["byte_count"] > 0
        assert row["source"] == "report_v1_snapshot"
        assert row["row_count"] > 0
        assert row["preview_hash"] == payload["preview_hash"]
        assert row["snapshot_preview_hash"] == payload["preview_hash"]
        assert row["report_layout_source"] == "shared_saved_layout"
        assert row["report_layout_governed_widget_append_count"] > 0
    assert payload["delivery"]["scheduled_dry_run_status"] == "rendered"
    assert payload["scheduled_dry_run"]["delivery_status"]["mode"] == "dry_run"
    assert payload["scheduled_dry_run"]["delivery_status"]["status"] == "rendered"
    assert payload["scheduled_dry_run"]["delivery_status"]["sanitized"] is True
    assert payload["scheduled_dry_run"]["delivery_status"]["rendered_at"]
    assert payload["scheduled_dry_run"]["report_layout_source"] == "shared_saved_layout"

    bundle_output = StringIO()
    call_command(
        "slb_report_evidence_bundle",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        stdout=bundle_output,
    )
    bundle = json.loads(bundle_output.getvalue())
    completed_formats = {
        row["format"]
        for row in bundle["exports"]
        if row["status"] == ReportExportJob.STATUS_COMPLETED
        and row["artifact_present"] is True
        and row["artifact_size_bytes"] > 0
        and row["snapshot_preview_hash"] == payload["preview_hash"]
    }
    assert {"csv", "pdf", "png"} <= completed_formats
    current_export_rows = [
        row
        for row in bundle["exports"]
        if row["format"] in {"csv", "pdf", "png"}
        and row["status"] == ReportExportJob.STATUS_COMPLETED
        and row["snapshot_preview_hash"] == payload["preview_hash"]
    ]
    assert len(current_export_rows) >= 3
    for row in current_export_rows:
        assert row["report_layout_source"] == "shared_saved_layout"
        assert row["report_layout_governed_widget_append_count"] > 0
    assert any(
        row["delivery_status"].get("mode") == "dry_run"
        and row["delivery_status"].get("status") == "rendered"
        for row in bundle["exports"]
    )
    event = AuditLog.all_objects.get(
        tenant=tenant,
        action="report_export_evidence_generated",
        resource_type="report_definition",
        resource_id=report.id,
    )
    assert event.metadata == {
        "redacted": True,
        "formats": ["csv", "pdf", "png"],
        "scheduled_dry_run": True,
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "preview_hash": payload["preview_hash"],
    }
    assert_redacted_report_audit_metadata(event.metadata)


def test_slb_report_parity_compare_command_computes_deltas_and_blocks_missing_values(
    tmp_path,
):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
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
        "source_search_provenance": [
            {
                "searched_at": "2026-06-26T07:39:45-0500",
                "source": "Gmail",
                "queries": [
                    '"SLB" "May 2026" has:attachment -in:spam -in:trash',
                    "access_token=secret-token-value",
                ],
                "result": "Found the already-reviewed May 2026 SLB PDF; no paid export.",
            },
            {
                "searched_at": "2026-06-26T07:40:00-0500",
                "source": "operator@example.com",
                "queries": ["SLB paid May"],
                "result": "client_secret was present in the note",
            },
        ],
        "missing_source_values": [
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "reach",
                "label": "Reach",
                "reason": "No approved paid reach export was found.",
            },
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "secret_note",
                "label": "operator@example.com",
                "reason": "access_token=secret-token-value",
            },
        ],
        "unmatched_source_values": [
            {
                "source_document": "SLB Monthly Report - May 2026 Editable v2 PDF",
                "source_page": 11,
                "source_label": "Top post engagement",
                "source_value": {
                    "views": 7900,
                    "comments": 16,
                    "shares": 24,
                },
                "reason_not_in_parity_rows": (
                    "The evidence bundle emits summary rows, not top-post parity rows."
                ),
            }
        ],
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
            {
                "dataset": "organic_facebook_page",
                "widget_id": "organic_page_summary",
                "metric": "page_impressions",
                "label": "Page Impressions",
                "source_value": 145000,
                "source_document": "SLB Monthly Report - May 2026 Editable v2 PDF",
                "source_pages": [7, 10],
                "source_label": "Facebook Views",
                "source_display_value": "145K",
                "explanation": "Source value is real but no longer rendered by the repaired layout.",
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
    assert payload["source_search_provenance"] == [
        {
            "searched_at": "2026-06-26T07:39:45-0500",
            "source": "Gmail",
            "queries": [
                '"SLB" "May 2026" has:attachment -in:spam -in:trash',
                "redacted",
            ],
            "result": "Found the already-reviewed May 2026 SLB PDF; no paid export.",
        },
        {
            "searched_at": "2026-06-26T07:40:00-0500",
            "source": "redacted",
            "queries": ["SLB paid May"],
            "result": "redacted",
        },
    ]
    assert payload["missing_source_values"] == [
        {
            "dataset": "paid_meta_ads",
            "widget_id": "paid_summary",
            "metric": "reach",
            "label": "Reach",
            "reason": "No approved paid reach export was found.",
        },
        {
            "dataset": "paid_meta_ads",
            "widget_id": "paid_summary",
            "metric": "redacted",
            "label": "redacted",
            "reason": "redacted",
        },
    ]
    assert payload["unmatched_source_values"] == [
        {
            "source_document": "SLB Monthly Report - May 2026 Editable v2 PDF",
            "source_page": 11,
            "source_label": "Top post engagement",
            "source_value": {
                "views": 7900,
                "comments": 16,
                "shares": 24,
            },
            "reason_not_in_parity_rows": (
                "The evidence bundle emits summary rows, not top-post parity rows."
            ),
        },
        {
            "dataset": "organic_facebook_page",
            "widget_id": "organic_page_summary",
            "metric": "page_impressions",
            "label": "Page Impressions",
            "source_value": 145000,
            "reason_not_in_parity_rows": (
                "No matching current evidence-bundle parity row exists for "
                "organic_facebook_page.organic_page_summary.page_impressions; "
                "preserved as an unmatched source value."
            ),
            "source_document": "SLB Monthly Report - May 2026 Editable v2 PDF",
            "source_pages": [7, 10],
            "source_label": "Facebook Views",
            "source_display_value": "145K",
            "explanation": "Source value is real but no longer rendered by the repaired layout.",
        },
    ]
    assert payload["row_count"] == 5
    assert payload["result_summary"] == {
        "blocked_metric_semantics": 1,
        "blocked_missing_dashthis_value": 1,
        "fail": 1,
        "pass": 2,
    }
    assert payload["unresolved_row_count"] == 3
    assert payload["unresolved_summary"] == {
        "by_dataset": {
            "content_ops": {"blocked_metric_semantics": 1},
            "organic_facebook_page": {"blocked_missing_dashthis_value": 1},
            "paid_meta_ads": {"fail": 1},
        },
        "by_result": {
            "blocked_metric_semantics": 1,
            "blocked_missing_dashthis_value": 1,
            "fail": 1,
        },
    }
    assert {
        "dataset": "organic_facebook_page",
        "widget_id": "organic_page_summary",
        "metric": "page_reach",
        "label": "Page reach",
        "result": "blocked_missing_dashthis_value",
        "coverage_status": "missing_history",
        "source_label": "Stored Page Insights",
        "has_adinsights_value": True,
        "has_source_value": False,
        "explanation": "",
        "recommended_next_action": (
            "Provide approved aggregate Page/Post source values or keep the row unavailable with search provenance."
        ),
    } in payload["unresolved_rows"]
    assert payload["parity_completion_requirements"] == {
        "ready_for_final_parity": False,
        "requirement_count": 3,
        "requirements": [
            {
                "code": "approved_organic_page_post_source_values_required",
                "dataset": "organic_facebook_page",
                "row_count": 1,
                "metrics": ["page_reach"],
                "blocking_results": {"blocked_missing_dashthis_value": 1},
                "can_run_now": False,
                "required_action": (
                    "Provide approved aggregate Facebook Page/Post source values for the current "
                    "SLB organic metrics, or preserve reviewed top-post examples as unmatched values "
                    "when they cannot represent monthly totals."
                ),
                "scope_evidence": {},
            },
            {
                "code": "metric_semantics_or_tolerance_confirmation_required",
                "dataset": "mixed",
                "row_count": 1,
                "metrics": ["content_items_created"],
                "blocking_results": {"blocked_metric_semantics": 1},
                "can_run_now": False,
                "required_action": (
                    "Confirm metric semantics, date/account filters, and accepted tolerances before approving parity."
                ),
                "scope_evidence": {},
            },
            {
                "code": "parity_delta_investigation_required",
                "dataset": "mixed",
                "row_count": 1,
                "metrics": ["clicks"],
                "blocking_results": {"fail": 1},
                "can_run_now": False,
                "required_action": (
                    "Investigate non-zero parity deltas before approving the fixed-target report."
                ),
                "scope_evidence": {},
            },
        ],
    }
    rows_by_metric = {row["metric"]: row for row in payload["rows"]}
    assert rows_by_metric["spend"]["result"] == "pass"
    assert rows_by_metric["spend"]["absolute_delta"] == -1
    assert rows_by_metric["clicks"]["result"] == "fail"
    assert rows_by_metric["clicks"]["percentage_delta"] == 20
    assert rows_by_metric["page_reach"]["result"] == "blocked_missing_dashthis_value"
    assert rows_by_metric["published_posts"]["result"] == "pass"
    assert (
        rows_by_metric["content_items_created"]["result"] == "blocked_metric_semantics"
    )
    assert_report_payload_excludes_sensitive_values(payload)


def test_slb_report_parity_compare_command_does_not_call_live_providers(
    tmp_path, monkeypatch
):
    block_live_network_calls(monkeypatch)
    evidence_path = tmp_path / "evidence-bundle.json"
    comparison_path = tmp_path / "comparison-values.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "slb_evidence_bundle.v1",
                "report": {"id": "report-1"},
                "date_range": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
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


def test_slb_report_parity_compare_blocks_non_finite_source_values(tmp_path):
    evidence_path = tmp_path / "evidence-bundle.json"
    comparison_path = tmp_path / "comparison-values.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "slb_evidence_bundle.v1",
                "report": {"id": "report-1"},
                "date_range": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
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
                        "source_value": "Infinity",
                        "accepted_tolerance_percent": 1,
                        "explanation": "Rejected non-finite operator entry.",
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

    payload = json.loads(output.getvalue())
    assert payload["result_summary"] == {"blocked_metric_semantics": 1}
    assert payload["rows"][0]["result"] == "blocked_metric_semantics"
    assert payload["rows"][0]["source_value"] == "Infinity"


def test_slb_report_parity_compare_treats_blank_source_values_as_missing(tmp_path):
    evidence_path = tmp_path / "evidence-bundle.json"
    comparison_path = tmp_path / "comparison-values.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "slb_evidence_bundle.v1",
                "report": {"id": "report-1"},
                "date_range": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                "preview_hash": "preview-hash-1",
                "parity_rows": [
                    {
                        "dataset": "paid_meta_ads",
                        "widget_id": "paid_summary",
                        "metric": "spend",
                        "label": "Spend",
                        "adinsights_value": 100,
                    },
                    {
                        "dataset": "paid_meta_ads",
                        "widget_id": "paid_summary",
                        "metric": "clicks",
                        "label": "Clicks",
                        "adinsights_value": 50,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    comparison_path.write_text(
        json.dumps(
            {
                "schema_version": "slb_comparison_values.v1",
                "unmatched_source_values": [
                    {
                        "source_document": "SLB May worksheet",
                        "source_label": "Blank reach cell",
                        "source_value": " ",
                        "reason_not_in_parity_rows": "Blank cells are not source facts.",
                    },
                    {
                        "source_document": "SLB May worksheet",
                        "source_label": "DashThis note",
                        "source_value": "n/a",
                        "reason_not_in_parity_rows": "Placeholder cells are not source facts.",
                    },
                    {
                        "source_document": "SLB May worksheet",
                        "source_label": "Partial receipt impressions",
                        "source_value": 63900,
                        "reason_not_in_parity_rows": "Partial receipt window; audit evidence only.",
                    },
                ],
                "rows": [
                    {
                        "dataset": "paid_meta_ads",
                        "widget_id": "paid_summary",
                        "metric": "spend",
                        "label": "Spend",
                        "dashthis_value": " ",
                        "source_value": 100,
                        "accepted_tolerance_absolute": 0,
                        "explanation": "Use the numeric fallback when DashThis cell is blank.",
                    },
                    {
                        "dataset": "paid_meta_ads",
                        "widget_id": "paid_summary",
                        "metric": "clicks",
                        "label": "Clicks",
                        "source_value": "n/a",
                        "explanation": "No approved selected-account source export was found.",
                    },
                    {
                        "dataset": "paid_meta_ads",
                        "widget_id": "paid_summary",
                        "metric": "reach",
                        "label": "Reach",
                        "source_value": "",
                    },
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

    payload = json.loads(output.getvalue())
    assert payload["result_summary"] == {
        "blocked_missing_source_value": 1,
        "pass": 1,
    }
    rows_by_metric = {row["metric"]: row for row in payload["rows"]}
    assert rows_by_metric["spend"]["result"] == "pass"
    assert rows_by_metric["spend"]["source_value"] == 100
    assert rows_by_metric["clicks"]["result"] == "blocked_missing_source_value"
    assert rows_by_metric["clicks"]["source_value"] is None
    assert rows_by_metric["clicks"]["dashthis_value"] is None
    assert payload["unmatched_source_values"] == [
        {
            "source_document": "SLB May worksheet",
            "source_label": "Partial receipt impressions",
            "source_value": 63900,
            "reason_not_in_parity_rows": "Partial receipt window; audit evidence only.",
        }
    ]
    assert payload["unresolved_rows"] == [
        {
            "dataset": "paid_meta_ads",
            "widget_id": "paid_summary",
            "metric": "clicks",
            "label": "Clicks",
            "result": "blocked_missing_source_value",
            "coverage_status": "",
            "source_label": "",
            "has_adinsights_value": True,
            "has_source_value": False,
            "explanation": "No approved selected-account source export was found.",
            "recommended_next_action": (
                "Provide an approved selected-account May 2026 Meta Ads source export for parity; "
                "if retained ADinsights rows are also missing, reconnect/backfill the selected SLB ad account. "
                "Do not substitute another tenant account."
            ),
        }
    ]


def test_slb_report_parity_compare_classifies_source_present_without_adinsights_value(
    tmp_path,
):
    evidence_path = tmp_path / "evidence-bundle.json"
    comparison_path = tmp_path / "comparison-values.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "slb_evidence_bundle.v1",
                "report": {
                    "id": "report-1",
                    "template_key": "slb_monthly_social_report",
                },
                "date_range": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                "preview_hash": "preview-hash-1",
                "diagnostics": {
                    "source_health": {
                        "report_scope": {
                            "organic_facebook_page": {
                                "page_scope_present": False,
                                "matched_page_count": 0,
                                "available_page_count": 1,
                                "analyzable_page_count": 1,
                                "backfill_status": "blocked_missing_scope",
                                "required_action": (
                                    "Select the tenant-owned SLB Facebook Page before organic import or backfill."
                                ),
                                "scoped_rows": {
                                    "row_count": 0,
                                    "min_date": None,
                                    "max_date": None,
                                },
                            }
                        }
                    }
                },
                "parity_rows": [
                    {
                        "page_id": "executive_summary",
                        "section_id": "executive_summary_widgets",
                        "widget_id": "organic_page_summary",
                        "dataset": "organic_facebook_page",
                        "metric": "page_follows",
                        "label": "Page Follows",
                        "coverage_status": "missing_history",
                        "source_label": "Facebook Page Insights stored rows",
                        "adinsights_value": None,
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
                        "dataset": "organic_facebook_page",
                        "widget_id": "organic_page_summary",
                        "metric": "page_follows",
                        "label": "Page Follows",
                        "source_value": 19,
                        "explanation": (
                            "Facebook Follows is shown as 19 in the approved source PDF."
                        ),
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

    payload = json.loads(output.getvalue())
    assert payload["result_summary"] == {"blocked_missing_adinsights_value": 1}
    assert payload["unresolved_summary"] == {
        "by_dataset": {
            "organic_facebook_page": {"blocked_missing_adinsights_value": 1}
        },
        "by_result": {"blocked_missing_adinsights_value": 1},
    }
    assert payload["rows"][0]["result"] == "blocked_missing_adinsights_value"
    assert payload["rows"][0]["source_value"] == 19
    assert payload["unresolved_rows"] == [
        {
            "dataset": "organic_facebook_page",
            "widget_id": "organic_page_summary",
            "metric": "page_follows",
            "label": "Page Follows",
            "result": "blocked_missing_adinsights_value",
            "coverage_status": "missing_history",
            "source_label": "Facebook Page Insights stored rows",
            "has_adinsights_value": False,
            "has_source_value": True,
            "explanation": "Facebook Follows is shown as 19 in the approved source PDF.",
            "recommended_next_action": (
                "After reviewer confirmation of organic metric semantics, import the approved aggregate source values "
                "through the manual Meta organic CSV path once a tenant-owned SLB Facebook Page exists. "
                "Do not import values into an unrelated Page."
            ),
        }
    ]
    assert payload["parity_completion_requirements"] == {
        "ready_for_final_parity": False,
        "requirement_count": 1,
        "requirements": [
            {
                "code": "tenant_owned_slb_page_required_for_organic_import",
                "dataset": "organic_facebook_page",
                "row_count": 1,
                "metrics": ["page_follows"],
                "blocking_results": {"blocked_missing_adinsights_value": 1},
                "can_run_now": False,
                "required_action": (
                    "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
                    "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
                    "Do not import SLB values into an unrelated Page."
                ),
                "scope_evidence": {
                    "page_scope_present": False,
                    "matched_page_count": 0,
                    "available_page_count": 1,
                    "analyzable_page_count": 1,
                    "backfill_status": "blocked_missing_scope",
                    "required_action": (
                        "Select the tenant-owned SLB Facebook Page before organic import or backfill."
                    ),
                    "scoped_rows": {"row_count": 0, "min_date": "", "max_date": ""},
                },
            }
        ],
    }
    assert payload["blocking_next_actions"] == {
        "action_count": 1,
        "ready_to_run_action_count": 0,
        "blocked_prerequisite_count": 1,
        "primary_next_action": (
            "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
            "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
            "Do not import SLB values into an unrelated Page."
        ),
        "actions": [
            {
                "code": "tenant_owned_slb_page_required_for_organic_import",
                "dataset": "organic_facebook_page",
                "metrics": ["page_follows"],
                "blocking_results": {"blocked_missing_adinsights_value": 1},
                "can_run_now": False,
                "required_action": (
                    "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
                    "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
                    "Do not import SLB values into an unrelated Page."
                ),
                "scope_evidence": {
                    "page_scope_present": False,
                    "matched_page_count": 0,
                    "available_page_count": 1,
                    "analyzable_page_count": 1,
                    "backfill_status": "blocked_missing_scope",
                    "required_action": (
                        "Select the tenant-owned SLB Facebook Page before organic import or backfill."
                    ),
                    "scoped_rows": {"row_count": 0, "min_date": "", "max_date": ""},
                },
            }
        ],
    }


def test_slb_report_evidence_validate_command_passes_complete_artifacts(
    tmp_path, monkeypatch
):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 240,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 96,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "",
                "report_layout_governed_widget_append_count": None,
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


def test_slb_report_evidence_validate_product_finish_makes_parity_optional(
    tmp_path, monkeypatch
):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "format": export_format,
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            }
            for export_format in ("csv", "pdf", "png")
        ]
        + [
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
            }
        ],
        "diagnostics": {
            "source_health": slb_source_health_pass(),
        },
    }
    evidence_path = tmp_path / "evidence-bundle.json"
    evidence_path.write_text(json.dumps(evidence_bundle), encoding="utf-8")
    strict_output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=strict_output,
    )

    strict_payload = json.loads(strict_output.getvalue())
    assert strict_payload["validation_mode"] == "cancellation"
    assert strict_payload["readiness_status"] == "blocked"
    assert {"code": "parity", "message": "Parity comparison artifact is required."} in strict_payload[
        "blockers"
    ]
    product_output = StringIO()

    call_command(
        "slb_report_evidence_validate",
        "--evidence-bundle",
        str(evidence_path),
        "--validation-mode",
        "product_finish",
        "--expected-start-date",
        "2026-05-01",
        "--expected-end-date",
        "2026-05-31",
        stdout=product_output,
    )

    product_payload = json.loads(product_output.getvalue())
    assert product_payload["validation_mode"] == "product_finish"
    assert product_payload["readiness_status"] == "warning"
    assert product_payload["blocker_count"] == 0
    assert {"parity_optional"} == {
        warning["code"] for warning in product_payload["warnings"]
    }
    assert "product_finish_parity" in {
        check["code"] for check in product_payload["checks"]
    }


def test_slb_report_evidence_validate_blocks_legacy_organic_widget_inventory(
    tmp_path, monkeypatch
):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 1,
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
            "widgets": [
                {
                    "page_id": "executive_summary",
                    "section_id": "executive_summary_widgets",
                    "widget_id": "organic_page_summary",
                    "dataset": "organic_facebook_page",
                    "type": "kpi",
                    "status": "rendered",
                    "declared_metrics": ["page_reach", "page_follows"],
                    "declared_dimensions": [],
                    "data_kind": "kpi",
                    "coverage_status": "fresh",
                    "coverage_row_count": 8,
                    "source_label": "Facebook Page Insights stored rows",
                    "coverage_note_present": True,
                    "warning_count": 0,
                }
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
    assert payload["readiness_status"] == "blocked"
    blocker_codes = {blocker["code"] for blocker in payload["blockers"]}
    assert "rendering_legacy_organic_metrics" in blocker_codes
    assert "rendering_organic_availability_note" in blocker_codes


def test_slb_report_evidence_validate_allows_export_ready_warning_only_coverage(
    tmp_path, monkeypatch
):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "export_ready": True,
        "blocking_reasons": [],
        "warnings": [
            "Facebook Page Insights stored rows has no retained rows for the requested range.",
            "Content Ops imported post activity has no retained rows for the requested range.",
        ],
        "coverage_summary": {
            "datasets": [
                {
                    "dataset": "paid_meta_ads",
                    "statuses": {"partial": 3},
                    "row_count": 6,
                },
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"missing_history": 2},
                    "row_count": 0,
                },
                {
                    "dataset": "content_ops",
                    "statuses": {"missing_history": 1},
                    "row_count": 0,
                },
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "artifact_size_bytes": 64,
                "preview_hash": "old-preview-hash",
                "snapshot_preview_hash": "old-preview-hash",
            },
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 320,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "pdf",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 256,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
            },
            {
                "format": "png",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 512,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "shared_saved_layout",
                "report_layout_governed_widget_append_count": 17,
            },
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 96,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "preview-hash-1",
                "source": "report_v1_snapshot",
                "row_count": 17,
                "report_layout_source": "",
                "report_layout_governed_widget_append_count": None,
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
    assert payload["readiness_status"] == "warning"
    assert payload["blocker_count"] == 0
    assert payload["warning_count"] >= 3
    assert not [
        row
        for row in payload["blockers"]
        if row["code"] in {"coverage_status", "coverage_row_count", "export_hash"}
    ]
    selected_exports = {
        row["format"]: row
        for row in payload["export_evidence"]["selected_completed_exports"]
    }
    assert selected_exports["csv"]["report_layout_source"] == "shared_saved_layout"
    assert selected_exports["csv"]["report_layout_governed_widget_append_count"] == 17
    assert selected_exports["pdf"]["report_layout_source"] == "shared_saved_layout"
    assert selected_exports["pdf"]["artifact_size_bytes"] == 320
    assert selected_exports["png"]["report_layout_source"] == "shared_saved_layout"
    assert payload["export_evidence"]["selected_layout_source_count"] == 3
    warning_codes = {row["code"] for row in payload["warnings"]}
    assert {"coverage_status", "coverage_row_count"} <= warning_codes


def test_slb_report_evidence_validate_does_not_count_dry_run_as_completed_export(
    tmp_path,
):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
    assert payload["readiness_status"] == "blocked"
    assert {
        "code": "exports",
        "message": "Missing completed non-empty exports for: pdf.",
    } in payload["blockers"]
    assert "scheduled_dry_run" not in {row["code"] for row in payload["blockers"]}
    assert {
        row["format"] for row in payload["export_evidence"]["selected_completed_exports"]
    } == {"csv", "png"}


def test_slb_report_evidence_validate_blocks_missing_paid_scope_credential(
    tmp_path, monkeypatch
):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "export_ready": False,
        "blocking_reasons": ["paid_meta_ads missing_history"],
        "coverage_summary": {
            "datasets": [
                {
                    "dataset": "paid_meta_ads",
                    "statuses": {"missing_history": 1},
                    "row_count": 0,
                },
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "data_availability": {
            "schema_version": "report_data_availability.v1",
            "stored_aggregate_only": True,
            "no_live_provider_calls": True,
            "requested": {
                "date_range": "custom",
                "start_date": "2026-05-01",
                "end_date": "2026-05-31",
                "account_id": "act_791712443035541",
            },
            "blocking_datasets": ["paid_meta_ads"],
            "warning_datasets": [],
            "eligible_for_report_export": False,
            "datasets": {
                "paid_meta_ads": {
                    "dataset": "paid_meta_ads",
                    "coverage_status": "missing_history",
                    "row_count": 0,
                    "out_of_scope_retained_rows": {
                        "reason": "retained_meta_rows_exist_outside_requested_scope",
                        "excluded_from_selected_scope": True,
                        "account_count": 1,
                        "row_count": 31,
                        "min_date": "2026-05-01",
                        "max_date": "2026-05-31",
                        "selected_scope_row_count": 2,
                        "accounts": [
                            {
                                "account_id": "act_unrelated",
                                "name": "Unrelated retained tenant account",
                            }
                        ],
                    },
                    "scope_diagnostic": {
                        "code": "requested_account_no_rows",
                        "credential_status": {
                            "status": "missing",
                            "provider": "META",
                            "matched_account_id": None,
                            "token_status": None,
                            "last_validated_at": None,
                        },
                    },
                }
            },
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["readiness_status"] == "blocked"
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert "data_availability_paid_credential" in blocker_codes
    assert "data_availability_paid_out_of_scope_rows" in blocker_codes
    assert any(
        "Selected paid Meta account has no retained credential" in row["message"]
        for row in payload["blockers"]
    )
    assert any(
        "selected_scope_row_count must remain zero" in row["message"]
        and "must not expose account identifiers" in row["message"]
        for row in payload["blockers"]
    )


def test_slb_report_evidence_validate_requires_diagnostics_source_health(
    tmp_path, monkeypatch
):
    block_live_network_calls(monkeypatch)
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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


def test_slb_report_evidence_validate_requires_export_preview_and_snapshot_hashes(
    tmp_path,
):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
    assert any(
        row["code"] == "exports" and "csv" in row["message"]
        for row in payload["blockers"]
    )
    assert any(
        row["code"] == "exports" and "pdf" in row["message"]
        for row in payload["blockers"]
    )


def test_slb_report_evidence_validate_requires_parity_preview_hash_match(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
    assert (
        "parity_pass_row",
        "Parity pass row 0 is missing accepted tolerance.",
    ) in blockers
    assert ("parity_pass_row", "Parity pass row 0 is missing explanation.") in blockers


def test_slb_report_evidence_validate_rejects_non_finite_pass_row_values(tmp_path):
    evidence_bundle = slb_evidence_bundle_pass()
    pass_row = slb_parity_pass_row()
    pass_row["source_value"] = "NaN"
    pass_row["accepted_tolerance_percent"] = "Infinity"
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 1,
        "result_summary": {"pass": 1},
        "rows": [pass_row],
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
    assert (
        "parity_pass_row",
        "Parity pass row 0 has non-finite or non-numeric source_value.",
    ) in blockers
    assert (
        "parity_pass_row",
        "Parity pass row 0 has non-finite or non-numeric accepted_tolerance_percent.",
    ) in blockers


def test_slb_report_evidence_validate_blocks_no_data_parity_values(tmp_path):
    no_data_row = {
        "dataset": "content_ops",
        "widget_id": "content_activity_summary",
        "metric": "published_posts",
        "label": "Published Posts",
        "coverage_status": "missing_history",
        "source_label": "Content Ops imported post activity",
        "adinsights_value": 0,
        "source_value": 5,
        "result": "blocked_metric_semantics",
        "explanation": "No retained Content Ops history should remain null, not zero.",
    }
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "diagnostics": {"source_health": slb_source_health_pass()},
        "parity_rows": [slb_parity_pass_row(), no_data_row],
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 2,
        "result_summary": {"pass": 1, "blocked_missing_adinsights_value": 1},
        "rows": [slb_parity_pass_row(), no_data_row],
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
    assert (
        "parity_no_data_value",
        "Evidence bundle row 1 has coverage_status missing_history but a non-null adinsights_value.",
    ) in blockers
    assert (
        "parity_no_data_value",
        "Parity comparison row 1 has coverage_status missing_history but a non-null adinsights_value.",
    ) in blockers


def test_slb_report_evidence_validate_requires_missing_source_provenance(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "row_count": 2,
        "result_summary": {"pass": 1, "blocked_missing_source_value": 1},
        "missing_source_values": [
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "clicks",
                "label": "Clicks",
                "reason": "No approved paid clicks export was found.",
            }
        ],
        "unmatched_source_values": [
            {
                "source_document": "SLB Monthly Report - May 2026 Editable v2 PDF",
                "source_page": 10,
                "source_label": "Facebook Link Clicks",
                "source_value": 889,
                "reason_not_in_parity_rows": (
                    "The current clicks row is paid Meta Ads clicks, not organic link clicks."
                ),
            }
        ],
        "rows": [
            slb_parity_pass_row(),
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "clicks",
                "label": "Clicks",
                "coverage_status": "missing_history",
                "source_label": "Meta Ads UI/export search",
                "adinsights_value": None,
                "source_value": None,
                "result": "blocked_missing_source_value",
                "explanation": "No approved source export was found.",
                "recommended_next_action": (
                    "Provide an approved selected-account May 2026 Meta Ads source export for parity; "
                    "if retained ADinsights rows are also missing, reconnect/backfill the selected SLB ad account. "
                    "Do not substitute another tenant account."
                ),
            },
        ],
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
        "code": "parity_source_provenance",
        "message": "Parity rows with blocked_missing_source_value require source_search_provenance search proof.",
    } in payload["blockers"]

    parity_comparison["source_search_provenance"] = [
        {
            "searched_at": "2026-06-26T07:39:45-0500",
            "source": "Gmail",
            "queries": ['"SLB" "May 2026" has:attachment -in:spam -in:trash'],
            "result": "Found only the already-reviewed May PDF; no paid export.",
        }
    ]
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
    assert "parity_source_provenance" not in {
        row["code"] for row in payload["blockers"]
    }
    assert {
        "code": "parity_results",
        "message": "Parity has unresolved rows: {'blocked_missing_source_value': 1}.",
    } in payload["blockers"]
    assert payload["unresolved_parity"] == {
        "row_count": 1,
        "by_result": {"blocked_missing_source_value": 1},
        "by_dataset": {"paid_meta_ads": {"blocked_missing_source_value": 1}},
        "rows": [
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "clicks",
                "label": "Clicks",
                "result": "blocked_missing_source_value",
                "coverage_status": "missing_history",
                "source_label": "Meta Ads UI/export search",
                "has_adinsights_value": False,
                "has_source_value": False,
                "explanation": "No approved source export was found.",
                "recommended_next_action": (
                    "Provide an approved selected-account May 2026 Meta Ads source export for parity; "
                    "if retained ADinsights rows are also missing, reconnect/backfill the selected SLB ad account. "
                    "Do not substitute another tenant account."
                ),
            }
        ],
    }
    assert payload["source_value_inventory"] == {
        "missing_source_value_count": 1,
        "missing_source_values": [
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "clicks",
                "label": "Clicks",
                "reason": "No approved paid clicks export was found.",
            }
        ],
        "unmatched_source_value_count": 1,
        "unmatched_source_values": [
            {
                "source_document": "SLB Monthly Report - May 2026 Editable v2 PDF",
                "source_page": 10,
                "source_label": "Facebook Link Clicks",
                "source_value": 889,
                "reason_not_in_parity_rows": (
                    "The current clicks row is paid Meta Ads clicks, not organic link clicks."
                ),
            }
        ],
    }
    assert payload["parity_completion_requirements"] == {
        "ready_for_final_parity": False,
        "requirement_count": 1,
        "requirements": [
            {
                "code": "approved_selected_account_paid_source_export_required",
                "dataset": "paid_meta_ads",
                "row_count": 1,
                "metrics": ["clicks"],
                "blocking_results": {"blocked_missing_source_value": 1},
                "can_run_now": False,
                "required_action": (
                    "Provide an approved selected-account May 2026 Meta Ads source export, "
                    "then dry-run `import_meta_paid_csv` if retained ADinsights rows are missing. "
                    "Do not substitute another tenant ad account."
                ),
                "scope_evidence": {},
            }
        ],
    }


def test_slb_report_evidence_validate_requires_row_level_missing_source_inventory(
    tmp_path,
):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 2},
                    "row_count": 8,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "row_count": 2,
        "result_summary": {"pass": 1, "blocked_missing_source_value": 1},
        "source_search_provenance": [
            {
                "searched_at": "2026-06-28T18:00:15-0500",
                "source": "Gmail and Drive recheck",
                "queries": ["SLB paid May 2026 export"],
                "result": "No approved May 1-31 paid export was found.",
            }
        ],
        "missing_source_values": [
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "reach",
                "label": "Reach",
                "reason": "No approved paid reach export was found.",
            }
        ],
        "rows": [
            slb_parity_pass_row(),
            {
                "dataset": "paid_meta_ads",
                "widget_id": "paid_summary",
                "metric": "clicks",
                "label": "Clicks",
                "coverage_status": "missing_history",
                "source_label": "Meta Ads UI/export search",
                "adinsights_value": None,
                "source_value": None,
                "result": "blocked_missing_source_value",
                "explanation": "No approved source export was found.",
            },
        ],
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
    assert {
        "code": "parity_source_inventory",
        "message": (
            "missing_source_values does not cover unresolved source-missing rows: "
            "paid_meta_ads.paid_summary.clicks."
        ),
    } in payload["blockers"]

    parity_comparison["missing_source_values"] = [
        {
            "dataset": "paid_meta_ads",
            "widget_id": "paid_summary",
            "metric": "clicks",
            "label": "Clicks",
        }
    ]
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
    assert {
        "code": "parity_source_inventory",
        "message": (
            "missing_source_values entries must include reason text for unresolved "
            "source-missing rows: paid_meta_ads.paid_summary.clicks."
        ),
    } in payload["blockers"]


def test_slb_report_evidence_validate_surfaces_organic_page_scope_requirement(
    tmp_path,
):
    source_health = slb_source_health_pass()
    source_health["report_scope"] = {
        "organic_facebook_page": {
            "page_scope_present": False,
            "matched_page_count": 0,
            "available_page_count": 1,
            "analyzable_page_count": 1,
            "backfill_status": "blocked_missing_scope",
            "scoped_rows": {"row_count": 0, "min_date": None, "max_date": None},
            "required_action": (
                "Select the tenant-owned SLB Facebook Page before organic import or backfill."
            ),
        }
    }
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {"dataset": "paid_meta_ads", "statuses": {"fresh": 2}, "row_count": 10},
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"missing_history": 1},
                    "row_count": 0,
                },
                {"dataset": "content_ops", "statuses": {"fresh": 1}, "row_count": 4},
            ]
        },
        "rendering": {
            "widget_count": 12,
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
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "rendered",
                    "sanitized": True,
                },
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
        "diagnostics": {"source_health": source_health},
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "report": evidence_bundle["report"],
        "date_range": evidence_bundle["date_range"],
        "preview_hash": "preview-hash-1",
        "row_count": 2,
        "result_summary": {"pass": 1, "blocked_missing_adinsights_value": 1},
        "rows": [
            slb_parity_pass_row(),
            {
                "dataset": "organic_facebook_page",
                "widget_id": "organic_page_summary",
                "metric": "page_follows",
                "label": "Page Follows",
                "coverage_status": "missing_history",
                "source_label": "Facebook Page Insights stored rows",
                "adinsights_value": None,
                "source_value": 19,
                "result": "blocked_missing_adinsights_value",
                "explanation": "Facebook Follows is shown as 19 in the approved source PDF.",
                "recommended_next_action": (
                    "After reviewer confirmation of organic metric semantics, import the approved aggregate source values "
                    "through the manual Meta organic CSV path once a tenant-owned SLB Facebook Page exists. "
                    "Do not import values into an unrelated Page."
                ),
            },
        ],
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
    assert payload["parity_completion_requirements"] == {
        "ready_for_final_parity": False,
        "requirement_count": 1,
        "requirements": [
            {
                "code": "tenant_owned_slb_page_required_for_organic_import",
                "dataset": "organic_facebook_page",
                "row_count": 1,
                "metrics": ["page_follows"],
                "blocking_results": {"blocked_missing_adinsights_value": 1},
                "can_run_now": False,
                "required_action": (
                    "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
                    "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
                    "Do not import SLB values into an unrelated Page."
                ),
                "scope_evidence": {
                    "page_scope_present": False,
                    "matched_page_count": 0,
                    "available_page_count": 1,
                    "analyzable_page_count": 1,
                    "backfill_status": "blocked_missing_scope",
                    "scoped_rows": {"row_count": 0, "min_date": "", "max_date": ""},
                    "required_action": (
                        "Select the tenant-owned SLB Facebook Page before organic import or backfill."
                    ),
                },
            }
        ],
    }
    assert payload["blocking_next_actions"] == {
        "action_count": 1,
        "ready_to_run_action_count": 0,
        "blocked_prerequisite_count": 1,
        "primary_next_action": (
            "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
            "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
            "Do not import SLB values into an unrelated Page."
        ),
        "actions": [
            {
                "code": "tenant_owned_slb_page_required_for_organic_import",
                "dataset": "organic_facebook_page",
                "metrics": ["page_follows"],
                "blocking_results": {"blocked_missing_adinsights_value": 1},
                "can_run_now": False,
                "required_action": (
                    "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
                    "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
                    "Do not import SLB values into an unrelated Page."
                ),
                "scope_evidence": {
                    "page_scope_present": False,
                    "matched_page_count": 0,
                    "available_page_count": 1,
                    "analyzable_page_count": 1,
                    "backfill_status": "blocked_missing_scope",
                    "scoped_rows": {"row_count": 0, "min_date": "", "max_date": ""},
                    "required_action": (
                        "Select the tenant-owned SLB Facebook Page before organic import or backfill."
                    ),
                },
            }
        ],
    }
    assert_report_payload_excludes_sensitive_values(payload)


def test_slb_report_evidence_validate_command_surfaces_cancellation_blockers(tmp_path):
    evidence_bundle = {
        "schema_version": "slb_evidence_bundle.v1",
        "report": {"id": "report-1", "template_key": "slb_monthly_social_report"},
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
        },
        "preview_hash": "preview-hash-1",
        "coverage_summary": {
            "datasets": [
                {
                    "dataset": "paid_meta_ads",
                    "statuses": {"missing_history": 1},
                    "row_count": 0,
                },
                {
                    "dataset": "organic_facebook_page",
                    "statuses": {"fresh": 1},
                    "row_count": 3,
                },
            ]
        },
        "rendering": {"widget_count": 0, "pages": [{"id": "cover"}]},
        "exports": [
            {
                "format": "csv",
                "status": "completed",
                "artifact_present": True,
                "artifact_size_bytes": 128,
                "preview_hash": "preview-hash-1",
                "snapshot_preview_hash": "different-hash",
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "failed",
                    "sanitized": True,
                },
            }
        ],
        "raw_payload": "user_id=123 access_token=secret-token-value",
    }
    parity_comparison = {
        "schema_version": "slb_parity_comparison.v1",
        "date_range": {
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
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


def test_report_v1_export_blocks_when_required_coverage_missing(
    api_client, user, tenant
):
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


def test_generic_report_csv_export_creates_downloadable_artifact(
    tenant, tmp_path, monkeypatch
):
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


@pytest.mark.parametrize(
    "export_format", [ReportExportJob.FORMAT_PDF, ReportExportJob.FORMAT_PNG]
)
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


def test_generic_report_export_fails_without_renderer_artifact(
    tenant, tmp_path, monkeypatch
):
    report = ReportDefinition.objects.create(
        tenant=tenant, name="Missing artifact report"
    )
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


def test_generic_report_export_enqueue_failure_is_sanitized(
    api_client, user, tenant, monkeypatch
):
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
    assert (
        response.json()["error_message"] == "Export scheduling failed (RuntimeError)."
    )
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

    empty_response = api_client.get(
        reverse("report-export-download", args=[empty_job.id])
    )
    assert empty_response.status_code == 404

    other_tenant = Tenant.objects.create(name="Other Export Tenant")
    other_report = ReportDefinition.objects.create(
        tenant=other_tenant, name="Other report"
    )
    other_job = ReportExportJob.objects.create(
        tenant=other_tenant,
        report=other_report,
        export_format=ReportExportJob.FORMAT_CSV,
        status=ReportExportJob.STATUS_COMPLETED,
        artifact_path=f"/exports/{other_tenant.id}/{other_report.id}/other.csv",
    )
    tenant_response = api_client.get(
        reverse("report-export-download", args=[other_job.id])
    )
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
    assert any(
        item["route"].startswith("/dashboards/create?template=")
        for item in payload["systemTemplates"]
    )
    assert any(
        item["route"].startswith("/dashboards/saved/")
        for item in payload["savedDashboards"]
    )
    assert any(
        item["name"] == "Saved Meta dashboard" for item in payload["savedDashboards"]
    )
    assert all(item["name"] != "Saved report" for item in payload["savedDashboards"])


def test_dashboard_library_bootstraps_default_presets_idempotently(
    api_client, user, tenant
):
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
    assert (
        DashboardDefinition.objects.filter(tenant=tenant, is_active=True).count() == 3
    )
    assert all(
        dashboard.created_by is None and dashboard.updated_by is None
        for dashboard in DashboardDefinition.objects.filter(tenant=tenant)
    )

    second_response = api_client.get(reverse("dashboard-library"))
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert {item["name"] for item in second_payload["savedDashboards"]} == preset_names
    assert (
        DashboardDefinition.objects.filter(tenant=tenant, is_active=True).count() == 3
    )


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
        "layout": {
            "routeKind": "campaigns",
            "widgets": ["kpis", "trend", "campaign_table"],
        },
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
        {
            "name": "SLB renamed dashboard",
            "default_metric": DashboardDefinition.METRIC_CTR,
        },
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

    delete_response = api_client.delete(
        reverse("dashboard-definition-detail", args=[duplicate_id])
    )
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
    assert {"datasets", "metrics", "dimensions", "widgets", "compatibility"} <= set(
        payload
    )
    metrics_by_key = {
        (metric["dataset"], metric["key"]): metric for metric in payload["metrics"]
    }
    assert metrics_by_key[("organic_facebook_page", "page_reach")][
        "availability_state"
    ] == ("permission_gated")
    assert metrics_by_key[("organic_facebook_page", "post_reactions")][
        "availability_state"
    ] == ("available")
    assert "permission_gated" in payload["compatibility"]["metric_availability_states"]
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
    assert payload["source_metric_semantics"]["organic_facebook_page"]["page"][
        "page_reach"
    ] == [
        "page_total_media_view_unique",
        "page_impressions_unique",
    ]
    assert payload["source_metric_semantics"]["organic_facebook_page"]["post"][
        "post_reactions"
    ] == ["post_reactions_total"]
    assert payload["source_metric_semantics"]["organic_facebook_page"]["post"][
        "post_comments"
    ] == [
        "post_comments_total",
        "post_comments",
    ]
    assert payload["source_metric_semantics"]["organic_facebook_page"]["post"][
        "post_shares"
    ] == [
        "post_shares_total",
        "post_shares",
    ]
    assert (
        "post_reactions_by_type_total"
        in payload["source_metric_semantics"]["organic_facebook_page"]["post"][
            "post_reactions_like"
        ]
    )


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


def test_dashboard_widget_preview_returns_stored_aggregate_data(
    api_client, user, tenant
):
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
                "rows": [
                    {
                        "date": today,
                        "campaign": "SLB Awareness",
                        "spend": 1200,
                        "clicks": 80,
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
    assert payload["data"]["columns"] == [
        "post",
        "date",
        "content",
        "post_impressions",
        "post_clicks",
    ]
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


def test_dashboard_widget_preview_bar_chart_keeps_missing_organic_values_null(
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
                id="organic_post_impressions_bar",
                type="bar_chart",
                dataset="organic_facebook_page",
                dimensions=["post"],
                metrics=["post_impressions"],
                filters={
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                visual={"row_limit": 10, "title": "Post impressions"},
            ),
            "page_id": "slb-page",
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["kind"] == "bar"
    assert payload["data"]["rows"] == [
        {
            "post": "slb-page_123",
            "post_impressions": None,
        }
    ]
    assert payload["coverage"]["coverage_status"] == "partial"


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
    assert payload["data"]["columns"] == [
        "post",
        "date",
        "content",
        "post_reactions_like",
        "post_reactions_love",
    ]
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


def test_dashboard_widget_preview_maps_edge_sourced_post_engagement_totals(
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
        message="Edge engagement post",
        created_time=datetime(2026, 5, 10, 15, 30, tzinfo=dt_timezone.utc),
    )
    metric_time = datetime(2026, 5, 10, 23, 59, tzinfo=dt_timezone.utc)
    for metric_key, value in {
        "post_reactions_total": 9,
        "post_comments_total": 2,
        "post_shares_total": 4,
    }.items():
        MetaPostInsightPoint.all_objects.create(
            tenant=tenant,
            post=post,
            metric_key=metric_key,
            period="lifetime",
            end_time=metric_time,
            value_num=value,
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
                metrics=["post_reactions", "post_comments", "post_shares"],
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
    assert payload["data"]["columns"] == [
        "post",
        "date",
        "content",
        "post_reactions",
        "post_comments",
        "post_shares",
    ]
    assert payload["data"]["rows"] == [
        {
            "post": "slb-page_123",
            "date": "2026-05-10",
            "content": "Edge engagement post",
            "post_reactions": 9.0,
            "post_comments": 2.0,
            "post_shares": 4.0,
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
                "rows": [
                    {"date": today.isoformat(), "campaign": "Old Snapshot", "spend": 10}
                ],
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


def test_dashboard_widget_preview_applies_client_scope_to_paid_rows(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate()
    client = Client.objects.create(tenant=tenant, name="SLB", slug="slb")
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
    ClientPlatformAccount.objects.create(
        tenant=tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS,
        external_id=selected.external_id,
        display_name=selected.name,
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
            "client_id": str(client.id),
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["metrics"][0]["value"] == 75
    assert payload["data"]["metrics"][1]["value"] == 50
    assert payload["coverage"]["row_count"] == 1


def test_dashboard_widget_preview_does_not_fallback_to_unscoped_snapshot_for_empty_account_scope(
    api_client,
    user,
    tenant,
):
    today = timezone.localdate().isoformat()
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_111",
        account_id="111",
        name="Selected Meta Account",
        currency="USD",
        status="ACTIVE",
    )
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        generated_at=timezone.now(),
        payload={
            "campaign": {
                "summary": {"totalSpend": 999, "totalClicks": 99},
                "trend": [{"date": today, "spend": 999, "clicks": 99}],
                "rows": [
                    {
                        "date": today,
                        "campaign": "Other Client",
                        "spend": 999,
                        "clicks": 99,
                    }
                ],
            }
        },
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
    assert payload["data"]["metrics"][0]["value"] is None
    assert payload["data"]["metrics"][1]["value"] is None
    assert payload["coverage"]["row_count"] == 0
    assert payload["coverage"]["coverage_status"] == "not_previously_synced"


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
    assert "account_id does not belong to the authenticated tenant" in str(
        response.json()
    )


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
    assert payload["warnings"][0] == (
        f"Warehouse aggregate metrics is missing 1 requested day from "
        f"{(today - timedelta(days=1)).isoformat()} through "
        f"{(today - timedelta(days=1)).isoformat()}."
    )


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

    response = api_client.post(
        reverse("dashboard-definition-list"), payload, format="json"
    )

    assert response.status_code == 201
    assert response.json()["layout"]["schema_version"] == "dashboard.v1"


def test_dashboard_definitions_dashboard_v1_remains_tenant_scoped(
    api_client, user, tenant
):
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
    assert not DashboardDefinition.objects.filter(
        tenant=other_tenant, id__in=dashboard_ids
    ).exists()


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

    assert (
        len(rows) == 1
    ), f"Expected exactly 1 row for authed tenant, got {len(rows)}: {rows}"
    assert str(rows[0]["tenant_id"]) == str(tenant.id)
    assert rows[0]["property_id"] == "11111"
    assert rows[0]["campaign_name"] == "brand"
    # Leak canary: the other tenant's distinctive campaign must never appear.
    assert not any(row.get("campaign_name") == "leak_canary" for row in rows)
    assert not any(str(row.get("tenant_id")) == str(other_tenant.id) for row in rows)
