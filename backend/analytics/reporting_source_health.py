"""Support-safe source health summaries for reporting diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable, Mapping

from django.db.models import Count, Max, Min, Q
from django.utils.dateparse import parse_date

from analytics.models import AdAccount, RawPerformanceRecord, TenantMetricsSnapshot
from integrations.models import (
    AirbyteConnection,
    MetaConnection,
    MetaInsightPoint,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
    PlatformCredential,
)
from analytics.reporting_templates import SLB_MONTHLY_TEMPLATE_KEY


@dataclass
class SourceHealthContext:
    credential_rows: list[PlatformCredential]
    credential_count: int
    credential_token_status_counts: dict[str, int]
    credential_scopes: set[str]
    credential_latest_validated_at: Any
    credential_latest_expires_at: Any
    page_connection_count: int
    page_connection_active_count: int
    page_connection_inactive_count: int
    page_connection_scopes: set[str]
    page_connection_latest_token_expires_at: Any
    page_auth_counts: dict[str, int]
    page_count: int
    analyzable_page_count: int
    selected_default_page_count: int
    page_ids: set[str]
    has_synced_pages_without_rows: bool
    has_post_sync_without_rows: bool
    airbyte_connection_count: int
    airbyte_active_count: int
    airbyte_inactive_count: int
    airbyte_last_job_status_counts: dict[str, int]
    airbyte_latest_synced_at: Any
    airbyte_latest_completed_at: Any
    airbyte_error_categories: dict[str, int]
    ad_account_count: int
    stored_rows: dict[str, Any]
    has_page_rows: bool
    has_post_rows: bool
    has_meta_posts: bool
    has_content_rows: bool
    has_published_posts: bool


def build_reporting_source_health(
    *, tenant, report_context: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return redacted source health used by report diagnostics and evidence commands."""

    context = _build_source_health_context(tenant=tenant)
    report_scope = _report_scope_health(
        tenant=tenant,
        report_context=report_context,
        context=context,
    )
    payload = {
        "schema_version": "slb_source_health.v1",
        "stored_aggregate_only": True,
        "no_live_provider_calls": True,
        "meta_credentials": _meta_credential_health(context=context),
        "meta_page_connection": _meta_page_connection_health(context=context),
        "meta_airbyte": _meta_airbyte_health(context=context),
        "stored_assets": _stored_asset_health(context=context),
        "stored_rows": context.stored_rows,
        "recommended_next_actions": _recommended_source_actions(
            context=context,
            report_scope=report_scope,
        ),
        "remediation_actions": _remediation_actions(
            context=context,
            report_scope=report_scope,
        ),
    }
    if report_scope is not None:
        payload["report_scope"] = report_scope
    return payload


def _build_source_health_context(*, tenant) -> SourceHealthContext:
    credential_rows = list(
        PlatformCredential.all_objects.filter(
            tenant=tenant,
            provider=PlatformCredential.META,
        )
    )
    credential_scopes = _scope_set(row.granted_scopes for row in credential_rows)
    credential_token_status_counts = _count_rows_by(
        credential_rows, lambda row: row.token_status
    )

    page_connection_rows = list(MetaConnection.all_objects.filter(tenant=tenant))
    page_connection_scopes = _scope_set(row.scopes for row in page_connection_rows)

    pages = list(MetaPage.all_objects.filter(tenant=tenant))
    page_auth_counts = _page_auth_status_counts(pages)
    page_ids = {str(page.page_id) for page in pages if str(page.page_id).strip()}

    airbyte_rows = list(
        AirbyteConnection.all_objects.filter(
            tenant=tenant,
            provider=PlatformCredential.META,
        )
    )
    airbyte_error_categories: dict[str, int] = {}
    for row in airbyte_rows:
        category = _airbyte_error_category(str(row.last_job_error or ""))
        if category:
            airbyte_error_categories[category] = (
                airbyte_error_categories.get(category, 0) + 1
            )

    meta_post_count = MetaPost.all_objects.filter(tenant=tenant).count()
    stored_rows = _stored_row_health(tenant=tenant, meta_post_count=meta_post_count)
    has_page_rows = int(stored_rows["organic_facebook_page"]["row_count"] or 0) > 0
    has_post_rows = int(stored_rows["organic_facebook_posts"]["row_count"] or 0) > 0
    has_meta_posts = meta_post_count > 0
    content_ops_rows = stored_rows["content_ops"]
    has_content_rows = int(content_ops_rows.get("row_count") or 0) > 0
    has_published_posts = int(content_ops_rows.get("published_post_count") or 0) > 0

    return SourceHealthContext(
        credential_rows=credential_rows,
        credential_count=len(credential_rows),
        credential_token_status_counts=credential_token_status_counts,
        credential_scopes=credential_scopes,
        credential_latest_validated_at=_max_attr(credential_rows, "last_validated_at"),
        credential_latest_expires_at=_max_attr(credential_rows, "expires_at"),
        page_connection_count=len(page_connection_rows),
        page_connection_active_count=sum(
            1 for row in page_connection_rows if bool(row.is_active)
        ),
        page_connection_inactive_count=sum(
            1 for row in page_connection_rows if not bool(row.is_active)
        ),
        page_connection_scopes=page_connection_scopes,
        page_connection_latest_token_expires_at=_max_attr(
            page_connection_rows, "token_expires_at"
        ),
        page_auth_counts=page_auth_counts,
        page_count=len(pages),
        analyzable_page_count=sum(1 for page in pages if bool(page.can_analyze)),
        selected_default_page_count=sum(1 for page in pages if bool(page.is_default)),
        page_ids=page_ids,
        has_synced_pages_without_rows=any(page.last_synced_at for page in pages),
        has_post_sync_without_rows=any(page.last_posts_synced_at for page in pages),
        airbyte_connection_count=len(airbyte_rows),
        airbyte_active_count=sum(1 for row in airbyte_rows if bool(row.is_active)),
        airbyte_inactive_count=sum(
            1 for row in airbyte_rows if not bool(row.is_active)
        ),
        airbyte_last_job_status_counts=_count_rows_by(
            airbyte_rows, lambda row: row.last_job_status
        ),
        airbyte_latest_synced_at=_max_attr(airbyte_rows, "last_synced_at"),
        airbyte_latest_completed_at=_max_attr(airbyte_rows, "last_job_completed_at"),
        airbyte_error_categories=airbyte_error_categories,
        ad_account_count=AdAccount.all_objects.filter(tenant=tenant).count(),
        stored_rows=stored_rows,
        has_page_rows=has_page_rows,
        has_post_rows=has_post_rows,
        has_meta_posts=has_meta_posts,
        has_content_rows=has_content_rows,
        has_published_posts=has_published_posts,
    )


def _meta_credential_health(*, context: SourceHealthContext) -> dict[str, Any]:
    required_scopes = {
        "ads_read",
        "business_management",
        "pages_read_engagement",
        "pages_show_list",
    }
    return {
        "credential_count": context.credential_count,
        "token_status_counts": context.credential_token_status_counts,
        "has_valid_credential": bool(
            context.credential_token_status_counts.get(
                PlatformCredential.TOKEN_STATUS_VALID
            )
        ),
        "has_reauth_required": bool(
            context.credential_token_status_counts.get(
                PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED
            )
        ),
        "required_scope_coverage": {
            "present": sorted(required_scopes & context.credential_scopes),
            "missing": sorted(required_scopes - context.credential_scopes),
        },
        "latest_validated_at": _latest_iso(context.credential_latest_validated_at),
        "latest_expires_at": _latest_iso(context.credential_latest_expires_at),
    }


def _meta_page_connection_health(*, context: SourceHealthContext) -> dict[str, Any]:
    required_scopes = {"pages_show_list", "pages_read_engagement"}
    usable_page_auth_count = int(context.page_auth_counts.get("usable", 0))
    return {
        "connection_count": context.page_connection_count,
        "active_count": context.page_connection_active_count,
        "inactive_count": context.page_connection_inactive_count,
        "has_active_connection": context.page_connection_active_count > 0,
        "has_usable_page_auth": usable_page_auth_count > 0,
        "usable_page_auth_count": usable_page_auth_count,
        "unusable_page_auth_count": int(
            context.page_auth_counts.get("missing", 0)
            + context.page_auth_counts.get("unreadable", 0)
        ),
        "page_auth_status_counts": context.page_auth_counts,
        "required_scope_coverage": {
            "present": sorted(required_scopes & context.page_connection_scopes),
            "missing": sorted(required_scopes - context.page_connection_scopes),
        },
        "latest_token_expires_at": _latest_iso(
            context.page_connection_latest_token_expires_at
        ),
    }


def _meta_airbyte_health(*, context: SourceHealthContext) -> dict[str, Any]:
    return {
        "connection_count": context.airbyte_connection_count,
        "active_count": context.airbyte_active_count,
        "inactive_count": context.airbyte_inactive_count,
        "last_job_status_counts": context.airbyte_last_job_status_counts,
        "latest_synced_at": _latest_iso(context.airbyte_latest_synced_at),
        "latest_completed_at": _latest_iso(context.airbyte_latest_completed_at),
        "sanitized_error_categories": context.airbyte_error_categories,
    }


def _stored_asset_health(*, context: SourceHealthContext) -> dict[str, Any]:
    return {
        "ad_account_count": context.ad_account_count,
        "meta_page_count": context.page_count,
        "analyzable_page_count": context.analyzable_page_count,
        "selected_default_page_count": context.selected_default_page_count,
    }


def _stored_row_health(*, tenant, meta_post_count: int | None = None) -> dict[str, Any]:
    resolved_meta_post_count = (
        meta_post_count
        if meta_post_count is not None
        else MetaPost.all_objects.filter(tenant=tenant).count()
    )
    return {
        "paid_meta_ads": _row_summary(
            RawPerformanceRecord.all_objects.filter(
                tenant=tenant, source__icontains="meta"
            ),
            min_field="date",
            max_field="date",
        ),
        "warehouse_snapshots": _snapshot_summary(tenant=tenant),
        "organic_facebook_page": _row_summary(
            MetaInsightPoint.all_objects.filter(tenant=tenant),
            min_field="end_time",
            max_field="end_time",
        ),
        "organic_facebook_posts": _row_summary(
            MetaPostInsightPoint.all_objects.filter(tenant=tenant),
            min_field="end_time",
            max_field="end_time",
            extra_count=resolved_meta_post_count,
            extra_count_label="post_count",
        ),
        "content_ops": _content_ops_row_summary(tenant=tenant),
    }


def _snapshot_summary(*, tenant) -> list[dict[str, Any]]:
    rows = []
    for snapshot in TenantMetricsSnapshot.all_objects.filter(tenant=tenant).order_by(
        "source"
    ):
        payload = snapshot.payload if isinstance(snapshot.payload, Mapping) else {}
        data = _snapshot_payload(payload)
        campaign = (
            data.get("campaign") if isinstance(data.get("campaign"), Mapping) else {}
        )
        rows.append(
            {
                "source": snapshot.source,
                "generated_at": snapshot.generated_at.isoformat(),
                "campaign_row_count": _safe_len(campaign.get("rows")),
                "campaign_trend_count": _safe_len(campaign.get("trend")),
                "has_summary": isinstance(campaign.get("summary"), Mapping)
                and bool(campaign.get("summary")),
            }
        )
    return rows


def _content_ops_row_summary(*, tenant) -> dict[str, Any]:
    from content_ops.models import OrganicPostMetricSnapshot, PublishedPost

    snapshots = OrganicPostMetricSnapshot.all_objects.filter(tenant=tenant)
    published = PublishedPost.all_objects.filter(tenant=tenant)
    summary = _row_summary(snapshots, min_field="metric_date", max_field="metric_date")
    summary["published_post_count"] = published.count()
    published_dates = published.aggregate(
        min_value=Min("published_at"), max_value=Max("published_at")
    )
    summary["published_min_date"] = _latest_iso(published_dates["min_value"])
    summary["published_max_date"] = _latest_iso(published_dates["max_value"])
    return summary


def _recommended_source_actions(
    *, context: SourceHealthContext, report_scope: Mapping[str, Any] | None = None
) -> list[str]:
    actions: list[str] = []
    paid_scope = (
        report_scope.get("paid_meta_ads")
        if isinstance(report_scope, Mapping)
        and isinstance(report_scope.get("paid_meta_ads"), Mapping)
        else None
    )
    if paid_scope:
        backfill_status = str(paid_scope.get("backfill_status") or "")
        if backfill_status == "blocked_missing_scope":
            actions.append(
                "Select the intended SLB Meta ad account or client before paid reporting backfill."
            )
        elif backfill_status == "blocked_missing_credential":
            actions.append(
                "Reconnect/select the selected SLB Meta ad account before paid May backfill."
            )
        elif backfill_status == "blocked_no_scoped_rows":
            actions.append(
                "Run fixed-range paid Meta backfill for the selected SLB ad account before export evidence."
            )
    meta_statuses = context.credential_token_status_counts
    has_valid_meta_credential = bool(
        meta_statuses.get(PlatformCredential.TOKEN_STATUS_VALID)
    )
    if (
        meta_statuses.get(PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED)
        and not has_valid_meta_credential
    ):
        actions.append(
            "Reconnect Meta OAuth credentials before running fresh Facebook/Meta reporting."
        )
    if "destination_connection_refused" in context.airbyte_error_categories:
        actions.append(
            "Fix the Airbyte destination/Postgres connectivity before rerunning Meta sync."
        )
    page_auth_counts = context.page_auth_counts
    if (
        page_auth_counts.get("missing") or page_auth_counts.get("unreadable")
    ) and not page_auth_counts.get("usable"):
        actions.append(
            "Reconnect/select the Facebook Page because the stored Page authorization cannot be used for Page Insights backfill."
        )
    if not context.has_page_rows:
        if context.has_synced_pages_without_rows:
            actions.append(
                "Meta Page Insights sync has run, but Graph returned no Page insight metric rows; "
                "verify the selected Page/date range in Meta or upload fallback organic values."
            )
        else:
            actions.append(
                "Backfill Facebook Page Insights stored rows for the fixed SLB Page/date range."
            )
    post_sync_ran_without_rows = (
        not context.has_meta_posts and context.has_post_sync_without_rows
    )
    if not context.has_post_rows:
        if context.has_meta_posts:
            actions.append(
                "Facebook posts are stored, but Meta returned no post insight metric rows; "
                "top-post activity can render from stored posts while post metrics remain unavailable."
            )
        elif post_sync_ran_without_rows:
            actions.append(
                "Meta Page posts sync has run, but Graph returned no Page posts for the selected "
                "Page/date range; choose a Page/date range with organic posts or upload fallback "
                "top-post values."
            )
        else:
            actions.append(
                "Backfill Facebook post insight rows for top-post reporting."
            )
    if not context.has_content_rows:
        if context.has_published_posts:
            actions.append(
                "Content Ops has Meta-linked published posts, but no aggregate metric snapshots; "
                "keep this section activity-only until post insight rows are available."
            )
        elif post_sync_ran_without_rows:
            actions.append(
                "Content Ops cannot import published activity because Meta returned no Page posts "
                "for the selected Page/date range."
            )
        else:
            actions.append(
                "Generate or backfill Content Ops aggregate snapshots for the fixed SLB date range."
            )
    if not actions:
        actions.append(
            "Run fixed-range evidence bundle, export, parity, and adversarial checks."
        )
    return actions


def _remediation_actions(
    *, context: SourceHealthContext, report_scope: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    has_page = context.page_count > 0
    has_page_rows = context.has_page_rows
    has_posts = context.has_meta_posts
    has_post_rows = context.has_post_rows
    paid_scope = (
        report_scope.get("paid_meta_ads")
        if isinstance(report_scope, Mapping)
        and isinstance(report_scope.get("paid_meta_ads"), Mapping)
        else None
    )
    organic_page_scope = (
        report_scope.get("organic_facebook_page")
        if isinstance(report_scope, Mapping)
        and isinstance(report_scope.get("organic_facebook_page"), Mapping)
        else None
    )

    if paid_scope and paid_scope.get("backfill_status") != "ready_with_scoped_rows":
        prerequisites = []
        backfill_status = str(paid_scope.get("backfill_status") or "")
        if backfill_status == "blocked_missing_scope":
            prerequisites.append(
                "Select an SLB Meta ad account or client on the report first."
            )
        elif backfill_status == "blocked_missing_credential":
            prerequisites.append(
                "Reconnect/select the selected SLB Meta ad account so a retained credential exists."
            )
        actions.append(
            {
                "dataset": "paid_meta_ads",
                "code": "slb_paid_meta_backfill",
                "label": "Run fixed-range paid Meta backfill for the selected SLB account.",
                "command_template": _slb_backfill_command_template(
                    datasets="paid_meta_ads",
                    scope_arg="--account-id <meta_ad_account_id>",
                    dispatch_mode="inline",
                ),
                "dry_run_command_template": _slb_backfill_command_template(
                    datasets="paid_meta_ads",
                    scope_arg="--account-id <meta_ad_account_id>",
                    dispatch_mode="dry-run",
                ),
                "no_render_export_provider_calls": True,
                "live_provider_calls_during_backfill": True,
                "aggregate_only": True,
                "prerequisites": prerequisites,
            }
        )
        actions.append(
            {
                "dataset": "paid_meta_ads",
                "code": "manual_meta_paid_csv_import",
                "label": "Import approved daily Meta paid values for the selected SLB account.",
                "command_template": _manual_paid_csv_import_command_template(),
                "dry_run_command_template": _manual_paid_csv_import_command_template(
                    dry_run=True
                ),
                "no_live_provider_calls": True,
                "aggregate_only": True,
                "prerequisites": [
                    "Use only approved Meta Ads UI/export daily aggregate values for the selected account.",
                    "CSV rows must be daily; monthly date_start/date_stop aggregates are rejected.",
                ],
            }
        )

    if not has_page_rows:
        organic_prerequisites = _organic_page_prerequisites(organic_page_scope)
        if has_page:
            actions.append(
                {
                    "dataset": "organic_facebook_page",
                    "code": "manual_meta_organic_csv_import",
                    "label": "Import approved aggregate Meta Page organic values.",
                    "command_template": _manual_organic_csv_import_command_template(),
                    "dry_run_command_template": (
                        _manual_organic_csv_import_command_template(dry_run=True)
                    ),
                    "no_live_provider_calls": True,
                    "aggregate_only": True,
                    "notes": [
                        "Use only approved Meta UI/export aggregate values.",
                        "Blank metric cells are skipped and must not be converted to zero.",
                    ],
                    "prerequisites": organic_prerequisites,
                }
            )
            actions.append(
                {
                    "dataset": "organic_facebook_page",
                    "code": "slb_page_insights_backfill",
                    "label": "Retry stored Page reporting backfill for the fixed SLB target.",
                    "command_template": _slb_backfill_command_template(
                        datasets="organic_facebook_page",
                        scope_arg="--page-id <facebook_page_id>",
                        dispatch_mode="inline",
                    ),
                    "dry_run_command_template": _slb_backfill_command_template(
                        datasets="organic_facebook_page",
                        scope_arg="--page-id <facebook_page_id>",
                        dispatch_mode="dry-run",
                    ),
                    "no_render_export_provider_calls": True,
                    "live_provider_calls_during_backfill": True,
                    "aggregate_only": True,
                    "prerequisites": organic_prerequisites,
                }
            )
        else:
            actions.append(
                {
                    "dataset": "organic_facebook_page",
                    "code": "select_facebook_page",
                    "label": "Reconnect/select the Facebook Page before organic reporting backfill.",
                    "command_template": "",
                    "no_live_provider_calls": False,
                    "aggregate_only": True,
                }
            )

    if not has_post_rows:
        actions.append(
            {
                "dataset": "organic_facebook_posts",
                "code": "manual_meta_organic_csv_import_posts",
                "label": "Import approved aggregate Meta post engagement values.",
                "command_template": _manual_organic_csv_import_command_template(),
                "dry_run_command_template": _manual_organic_csv_import_command_template(
                    dry_run=True
                ),
                "no_live_provider_calls": True,
                "aggregate_only": True,
                "notes": [
                    "Include post_id rows for top-post reporting.",
                    "Do not include user-level engagement, viewer, commenter, or reaction identity.",
                ],
            }
        )
        actions.append(
            {
                "dataset": "organic_facebook_posts",
                "code": "slb_post_engagement_backfill",
                "label": "Retry stored post discovery and engagement-edge backfill.",
                "command_template": _slb_backfill_command_template(
                    datasets="organic_facebook_posts",
                    scope_arg="--page-id <facebook_page_id>",
                    dispatch_mode="inline",
                ),
                "dry_run_command_template": _slb_backfill_command_template(
                    datasets="organic_facebook_posts",
                    scope_arg="--page-id <facebook_page_id>",
                    dispatch_mode="dry-run",
                ),
                "no_render_export_provider_calls": True,
                "live_provider_calls_during_backfill": True,
                "aggregate_only": True,
                "prerequisites": (
                    ["A selected Facebook Page must exist."] if not has_page else []
                ),
            }
        )

    has_content_rows = context.has_content_rows
    if not has_content_rows:
        actions.append(
            {
                "dataset": "content_ops",
                "code": "content_ops_from_synced_posts",
                "label": "Refresh Content Ops aggregate snapshots from synced Meta posts.",
                "command_template": _slb_backfill_command_template(
                    datasets="content_ops",
                    scope_arg="--page-id <facebook_page_id>",
                    extra_args="--import-synced-posts-to-content-ops",
                    dispatch_mode="inline",
                ),
                "dry_run_command_template": _slb_backfill_command_template(
                    datasets="content_ops",
                    scope_arg="--page-id <facebook_page_id>",
                    extra_args="--import-synced-posts-to-content-ops",
                    dispatch_mode="dry-run",
                ),
                "no_render_export_provider_calls": True,
                "live_provider_calls_during_backfill": False,
                "aggregate_only": True,
                "prerequisites": (
                    [
                        "Run organic_facebook_posts backfill or manual post CSV import first."
                    ]
                    if not has_posts
                    else []
                ),
            }
        )
    return actions


def _slb_backfill_command_template(
    *,
    datasets: str,
    scope_arg: str,
    dispatch_mode: str,
    extra_args: str = "",
) -> str:
    command = (
        "backend/.venv/bin/python backend/manage.py slb_backfill_meta_reporting "
        "--report-id <report_uuid> --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> "
        f"--datasets {datasets} {scope_arg}"
    )
    if extra_args:
        command = f"{command} {extra_args}"
    return f"{command} --dispatch-mode {dispatch_mode}"


def _manual_paid_csv_import_command_template(*, dry_run: bool = False) -> str:
    command = (
        "backend/.venv/bin/python backend/manage.py import_meta_paid_csv "
        "--tenant-id <tenant_uuid> --account-id <meta_ad_account_id> "
        "--file <path-to-meta-paid-csv>"
    )
    if dry_run:
        command = f"{command} --dry-run"
    return command


def _manual_organic_csv_import_command_template(*, dry_run: bool = False) -> str:
    command = (
        "backend/.venv/bin/python backend/manage.py import_meta_organic_csv "
        "--tenant-id <tenant_uuid> --page-id <facebook_page_id> "
        "--file <path-to-meta-organic-csv>"
    )
    if dry_run:
        command = f"{command} --dry-run"
    return command


def _report_scope_health(
    *, tenant, report_context: Mapping[str, Any] | None, context: SourceHealthContext
) -> dict[str, Any] | None:
    if not isinstance(report_context, Mapping):
        return None
    if str(report_context.get("template_key") or "") != SLB_MONTHLY_TEMPLATE_KEY:
        return None
    date_range = (
        report_context.get("date_range")
        if isinstance(report_context.get("date_range"), Mapping)
        else {}
    )
    start_date = _parse_context_date(date_range.get("start_date"))
    end_date = _parse_context_date(date_range.get("end_date"))
    account_id = str(report_context.get("account_id") or "").strip()
    page_id = str(report_context.get("page_id") or "").strip()
    client_id = str(report_context.get("client_id") or "").strip()
    paid_scope = _paid_report_scope_health(
        tenant=tenant,
        context=context,
        account_id=account_id,
        client_id=client_id,
        start_date=start_date,
        end_date=end_date,
    )
    organic_page_scope = _organic_page_report_scope_health(
        tenant=tenant,
        context=context,
        page_id=page_id,
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "schema_version": "slb_report_scope_health.v1",
        "date_range": {
            "date_range": str(date_range.get("date_range") or ""),
            "start_date": start_date.isoformat() if start_date else "",
            "end_date": end_date.isoformat() if end_date else "",
        },
        "paid_meta_ads": paid_scope,
        "organic_facebook_page": organic_page_scope,
    }


def _paid_report_scope_health(
    *,
    tenant,
    context: SourceHealthContext,
    account_id: str,
    client_id: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    credential_status = _redacted_meta_credential_status(
        context=context,
        account_id=account_id,
    )
    scoped_rows = _paid_scoped_row_summary(
        tenant=tenant,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
    )
    has_account_scope = bool(account_id)
    has_client_scope = bool(client_id)
    has_rows = int(scoped_rows.get("row_count") or 0) > 0
    if not has_account_scope and not has_client_scope:
        backfill_status = "blocked_missing_scope"
        required_action = (
            "Select the intended SLB Meta ad account or client before paid backfill."
        )
    elif has_account_scope and credential_status["status"] == "missing":
        backfill_status = "blocked_missing_credential"
        required_action = (
            "Reconnect/select the selected SLB Meta ad account before paid backfill."
        )
    elif not has_rows:
        backfill_status = "blocked_no_scoped_rows"
        required_action = (
            "Run fixed-range paid Meta backfill for the selected SLB ad account."
        )
    else:
        backfill_status = "ready_with_scoped_rows"
        required_action = "No paid backfill action required for the selected scope."
    return {
        "account_scope_present": has_account_scope,
        "client_scope_present": has_client_scope,
        "date_filter_applied": bool(start_date and end_date),
        "scoped_rows": scoped_rows,
        "credential_status": credential_status,
        "backfill_status": backfill_status,
        "required_action": required_action,
    }


def _paid_scoped_row_summary(
    *,
    tenant,
    account_id: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    queryset = RawPerformanceRecord.all_objects.filter(
        tenant=tenant,
        source__icontains="meta",
    )
    if account_id:
        aliases = _account_aliases(account_id)
        accounts = AdAccount.all_objects.filter(tenant=tenant).filter(
            Q(account_id__in=aliases) | Q(external_id__in=aliases)
        )
        queryset = queryset.filter(ad_account__in=accounts)
    if start_date and end_date:
        queryset = queryset.filter(date__gte=start_date, date__lte=end_date)
    return _row_summary(queryset, min_field="date", max_field="date")


def _organic_page_report_scope_health(
    *,
    tenant,
    context: SourceHealthContext,
    page_id: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    scoped_rows = _organic_page_scoped_row_summary(
        tenant=tenant,
        page_id=page_id,
        start_date=start_date,
        end_date=end_date,
    )
    has_page_scope = bool(page_id)
    matched_page = page_id in context.page_ids if page_id else False
    has_rows = int(scoped_rows.get("row_count") or 0) > 0
    if not has_page_scope:
        backfill_status = "blocked_missing_scope"
        required_action = "Select the tenant-owned SLB Facebook Page before organic import or backfill."
    elif not matched_page:
        backfill_status = "blocked_page_not_found"
        required_action = "Reconnect/select the tenant-owned SLB Facebook Page; the requested Page is not retained for this tenant."
    elif not has_rows:
        backfill_status = "blocked_no_scoped_rows"
        required_action = "Run fixed-range organic Page backfill or approved manual organic CSV import for the selected SLB Page."
    else:
        backfill_status = "ready_with_scoped_rows"
        required_action = (
            "No organic Page backfill action required for the selected scope."
        )
    return {
        "page_scope_present": has_page_scope,
        "matched_page_count": 1 if matched_page else 0,
        "available_page_count": context.page_count,
        "analyzable_page_count": context.analyzable_page_count,
        "date_filter_applied": bool(start_date and end_date),
        "scoped_rows": scoped_rows,
        "backfill_status": backfill_status,
        "required_action": required_action,
    }


def _organic_page_scoped_row_summary(
    *,
    tenant,
    page_id: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    queryset = MetaInsightPoint.all_objects.filter(tenant=tenant)
    if page_id:
        queryset = queryset.filter(page__page_id=page_id)
    if start_date and end_date:
        queryset = queryset.filter(
            end_time__date__gte=start_date, end_time__date__lte=end_date
        )
    return _row_summary(queryset, min_field="end_time", max_field="end_time")


def _organic_page_prerequisites(
    organic_page_scope: Mapping[str, Any] | None,
) -> list[str]:
    if not organic_page_scope:
        return [
            "Use only the tenant-owned SLB Facebook Page selected for the report; do not import into an unrelated Page."
        ]
    status = str(organic_page_scope.get("backfill_status") or "")
    if status == "blocked_missing_scope":
        return [
            "Select the tenant-owned SLB Facebook Page on the report before running this action.",
            "Do not import SLB source values into another tenant Page.",
        ]
    if status == "blocked_page_not_found":
        return [
            "Reconnect/select the tenant-owned SLB Facebook Page because the requested Page is not retained for this tenant.",
            "Do not import SLB source values into another tenant Page.",
        ]
    return [
        "Use only the tenant-owned SLB Facebook Page selected for the report; do not import into an unrelated Page."
    ]


def _redacted_meta_credential_status(
    *, context: SourceHealthContext, account_id: str
) -> dict[str, Any]:
    if not account_id:
        return {
            "status": "not_scoped",
            "provider": PlatformCredential.META,
            "matched": False,
            "token_status": None,
            "last_validated_at": None,
        }
    aliases = _account_aliases(account_id)
    credential = next(
        (
            row
            for row in sorted(
                context.credential_rows,
                key=lambda item: str(item.account_id or ""),
            )
            if str(row.account_id or "") in aliases
        ),
        None,
    )
    if credential is None:
        return {
            "status": "missing",
            "provider": PlatformCredential.META,
            "matched": False,
            "token_status": None,
            "last_validated_at": None,
        }
    token_status = str(credential.token_status or "")
    if token_status == PlatformCredential.TOKEN_STATUS_VALID:
        status = "valid"
    elif token_status in {
        PlatformCredential.TOKEN_STATUS_INVALID,
        PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
    }:
        status = "reauth_required"
    else:
        status = "present"
    return {
        "status": status,
        "provider": PlatformCredential.META,
        "matched": True,
        "token_status": token_status,
        "last_validated_at": _latest_iso(credential.last_validated_at),
    }


def _parse_context_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    parsed = parse_date(str(value))
    return parsed


def _account_aliases(account_id: str) -> set[str]:
    value = str(account_id or "").strip()
    if not value:
        return set()
    aliases = {value}
    if value.startswith("act_") and value[4:]:
        aliases.add(value[4:])
    elif value.isdigit():
        aliases.add(f"act_{value}")
    return aliases


def _row_summary(
    queryset,
    *,
    min_field: str,
    max_field: str,
    extra_count: int | None = None,
    extra_count_label: str = "",
) -> dict[str, Any]:
    aggregate = queryset.aggregate(
        count=Count("id"), min_value=Min(min_field), max_value=Max(max_field)
    )
    summary = {
        "row_count": int(aggregate["count"] or 0),
        "min_date": _latest_iso(aggregate["min_value"]),
        "max_date": _latest_iso(aggregate["max_value"]),
    }
    if extra_count_label:
        summary[extra_count_label] = int(extra_count or 0)
    return summary


def _snapshot_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("metrics", "snapshot", "data", "results", "payload"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return payload


def _count_by(queryset, field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in queryset.values(field).annotate(count=Count("id")):
        key = str(row.get(field) or "blank")
        counts[key] = int(row.get("count") or 0)
    return counts


def _count_rows_by(
    rows: Iterable[Any], value_getter: Callable[[Any], object]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(value_getter(row) or "blank")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _page_auth_status_counts(queryset: Iterable[Any]) -> dict[str, int]:
    counts = {"usable": 0, "missing": 0, "unreadable": 0}
    for page in queryset:
        try:
            token = page.decrypt_page_token()
        except Exception:
            counts["unreadable"] += 1
            continue
        if isinstance(token, str) and token.strip():
            counts["usable"] += 1
        else:
            counts["missing"] += 1
    return counts


def _safe_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _scope_set(values: Iterable[Any]) -> set[str]:
    scopes: set[str] = set()
    for granted in values:
        if isinstance(granted, list):
            scopes.update(str(scope) for scope in granted)
    return scopes


def _max_attr(rows: Iterable[Any], attr: str) -> Any:
    values = [
        getattr(row, attr, None) for row in rows if getattr(row, attr, None) is not None
    ]
    return max(values) if values else None


def _latest_iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _airbyte_error_category(error: str) -> str:
    lowered = error.lower()
    if not lowered:
        return ""
    if "error validating access token" in lowered or "session has expired" in lowered:
        return "meta_token_expired"
    if "connection to host.docker.internal" in lowered and "refused" in lowered:
        return "destination_connection_refused"
    if "cancelled" in lowered:
        return "sync_cancelled"
    return "other"
