from __future__ import annotations

import io
import json
from datetime import datetime, timezone as dt_timezone

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from analytics.models import ReportDefinition
from content_ops.models import PublishedPost
from integrations.models import MetaConnection, MetaPage, MetaPost, PlatformCredential


def _create_meta_credential(user, account_id: str = "act_123") -> PlatformCredential:
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id=account_id,
        granted_scopes=[
            "ads_read",
            "business_management",
            "pages_read_engagement",
            "pages_show_list",
        ],
        token_status=PlatformCredential.TOKEN_STATUS_VALID,
    )
    credential.set_raw_tokens("meta-access-token", None)
    credential.save()
    return credential


def _create_meta_page(user, page_id: str = "page-1", *, is_default: bool = True) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id=f"app-scoped-user-{page_id}",
        scopes=["pages_show_list", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("meta-user-token")
    connection.save()

    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id=page_id,
        name="SLB Page",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=is_default,
    )
    page.set_raw_page_token("meta-page-token")
    page.save()
    return page


def _create_report(user, *, account_id: str = "act_123", page_id: str = "page-1") -> ReportDefinition:
    return ReportDefinition.objects.create(
        tenant=user.tenant,
        name="SLB Monthly Social Report",
        filters={"account_id": account_id, "page_id": page_id},
        layout={
            "schema_version": "report.v1",
            "template_key": "slb_monthly_social_report",
        },
    )


def _create_report_without_page_scope(user, *, account_id: str = "act_123") -> ReportDefinition:
    return ReportDefinition.objects.create(
        tenant=user.tenant,
        name="SLB Monthly Social Report",
        filters={"account_id": account_id},
        layout={
            "schema_version": "report.v1",
            "template_key": "slb_monthly_social_report",
        },
    )


@pytest.mark.django_db
def test_slb_backfill_meta_reporting_dry_run_plans_fixed_range(user):
    _create_meta_credential(user)
    _create_meta_page(user)
    report = _create_report(user)

    stdout = io.StringIO()
    call_command(
        "slb_backfill_meta_reporting",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        "--dispatch-mode",
        "dry-run",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    assert payload["schema_version"] == "slb_backfill_meta_reporting.v1"
    assert payload["dispatch_mode"] == "dry-run"
    assert payload["date_range"] == {
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "timezone": "America/Jamaica",
    }
    assert payload["guardrails"]["no_demo_seed_data"] is True
    assert payload["guardrails"]["no_render_export_provider_calls"] is True

    paid = payload["datasets"]["paid_meta_ads"]
    assert paid["status"] == "planned"
    assert paid["account_id"] == "act_123"
    assert paid["task"]["kwargs"]["since"] == "2026-05-01"
    assert paid["task"]["kwargs"]["until"] == "2026-05-31"

    page = payload["datasets"]["organic_facebook_page"]
    assert page["status"] == "planned"
    assert page["tasks"][0]["kwargs"]["page_id"] == "page-1"
    assert page["tasks"][0]["kwargs"]["since"] == "2026-05-01"
    assert page["tasks"][0]["kwargs"]["until"] == "2026-05-31"

    posts = payload["datasets"]["organic_facebook_posts"]
    assert posts["status"] == "planned"
    assert {task["task_name"] for task in posts["tasks"]} == {
        "integrations.tasks.sync_page_posts",
        "integrations.tasks.sync_post_insights",
    }
    assert payload["datasets"]["content_ops"]["status"] == "blocked"
    assert payload["datasets"]["content_ops"]["reason"] == "content_ops_published_posts_missing"


@pytest.mark.django_db
def test_slb_backfill_meta_reporting_defaults_to_single_default_page(user):
    _create_meta_credential(user)
    _create_meta_page(user, page_id="default-page", is_default=True)
    _create_meta_page(user, page_id="secondary-page", is_default=False)
    report = _create_report_without_page_scope(user)

    stdout = io.StringIO()
    call_command(
        "slb_backfill_meta_reporting",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        "--datasets",
        "organic_facebook_page,organic_facebook_posts",
        "--dispatch-mode",
        "dry-run",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    page = payload["datasets"]["organic_facebook_page"]
    assert page["page_count"] == 1
    assert [task["kwargs"]["page_id"] for task in page["tasks"]] == ["default-page"]

    posts = payload["datasets"]["organic_facebook_posts"]
    assert posts["page_count"] == 1
    assert {task["kwargs"]["page_id"] for task in posts["tasks"]} == {"default-page"}


@pytest.mark.django_db
def test_slb_backfill_meta_reporting_persist_targets_is_planned_in_dry_run(user):
    _create_meta_credential(user, account_id="act_selected")
    _create_meta_page(user, page_id="selected-page", is_default=False)
    report = _create_report_without_page_scope(user, account_id="")

    stdout = io.StringIO()
    call_command(
        "slb_backfill_meta_reporting",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        "--datasets",
        "paid_meta_ads,organic_facebook_page",
        "--account-id",
        "act_selected",
        "--page-id",
        "selected-page",
        "--persist-report-targets",
        "--dispatch-mode",
        "dry-run",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    assert payload["report_target_persistence"] == {
        "status": "planned",
        "fields": ["account_id", "page_id"],
        "account_id": "act_selected",
        "page_id": "selected-page",
    }
    report.refresh_from_db()
    assert report.filters == {"account_id": ""}


@pytest.mark.django_db
def test_slb_backfill_meta_reporting_imports_synced_meta_posts_to_content_ops(user):
    _create_meta_credential(user)
    page = _create_meta_page(user, page_id="page-1")
    report = _create_report(user)
    created_time = datetime(2026, 5, 10, 15, 30, tzinfo=dt_timezone.utc)
    MetaPost.all_objects.create(
        tenant=user.tenant,
        page=page,
        post_id="page-1_123",
        message="Real synced post for SLB reporting",
        permalink_url="https://facebook.com/page-1/posts/123",
        created_time=created_time,
    )

    stdout = io.StringIO()
    call_command(
        "slb_backfill_meta_reporting",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        "--datasets",
        "content_ops",
        "--page-id",
        "page-1",
        "--import-synced-posts-to-content-ops",
        "--dispatch-mode",
        "inline",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    content_ops = payload["datasets"]["content_ops"]
    assert content_ops["status"] == "partial"
    assert content_ops["reason"] == "content_ops_activity_imported_metrics_unavailable"
    assert content_ops["published_post_count"] == 1
    assert content_ops["metric_refresh_counts"] == {"unavailable": 1}
    assert content_ops["import"]["imported_count"] == 1

    published = PublishedPost.all_objects.get(
        tenant=user.tenant,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id="page-1_123",
    )
    assert published.permalink == "https://facebook.com/page-1/posts/123"
    assert published.draft.state == "published"
    assert published.version.caption == "Real synced post for SLB reporting"


@pytest.mark.django_db
def test_slb_backfill_meta_reporting_blocks_unreadable_page_token(user):
    _create_meta_credential(user)
    page = _create_meta_page(user)
    page.page_token_tag = b"0" * 16
    page.save(update_fields=["page_token_tag"])
    report = _create_report(user)

    stdout = io.StringIO()
    call_command(
        "slb_backfill_meta_reporting",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        "--datasets",
        "organic_facebook_page",
        "--dispatch-mode",
        "dry-run",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    assert payload["datasets"]["organic_facebook_page"] == {
        "status": "blocked",
        "reason": "facebook_page_auth_reconnect_required",
        "required_action": "Reconnect/select the SLB Facebook Page before Page Insights or post backfill.",
        "page_count": 1,
        "missing_page_auth_count": 0,
        "unreadable_page_auth_count": 1,
        "tasks": [],
    }


@pytest.mark.django_db
def test_slb_backfill_meta_reporting_rejects_unknown_dataset(user):
    report = _create_report(user)

    with pytest.raises(CommandError, match="Unsupported dataset"):
        call_command(
            "slb_backfill_meta_reporting",
            "--report-id",
            str(report.id),
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-31",
            "--datasets",
            "paid_meta_ads,organic_instagram",
            "--dispatch-mode",
            "dry-run",
        )


@pytest.mark.django_db
def test_slb_backfill_meta_reporting_blocks_missing_meta_credential(user):
    _create_meta_page(user)
    report = _create_report(user)

    stdout = io.StringIO()
    call_command(
        "slb_backfill_meta_reporting",
        "--report-id",
        str(report.id),
        "--start-date",
        "2026-05-01",
        "--end-date",
        "2026-05-31",
        "--datasets",
        "paid_meta_ads",
        "--dispatch-mode",
        "dry-run",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    assert payload["datasets"]["paid_meta_ads"] == {
        "status": "blocked",
        "reason": "meta_ad_account_credential_missing",
        "required_action": "Reconnect Meta/Facebook and select the SLB ad account before backfill.",
    }
