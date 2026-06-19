"""Support-safe source health summaries for reporting diagnostics."""

from __future__ import annotations

from typing import Any, Mapping

from django.db.models import Count, Max, Min

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


def build_reporting_source_health(*, tenant) -> dict[str, Any]:
    """Return redacted source health used by report diagnostics and evidence commands."""

    return {
        "schema_version": "slb_source_health.v1",
        "stored_aggregate_only": True,
        "no_live_provider_calls": True,
        "meta_credentials": _meta_credential_health(tenant=tenant),
        "meta_page_connection": _meta_page_connection_health(tenant=tenant),
        "meta_airbyte": _meta_airbyte_health(tenant=tenant),
        "stored_assets": _stored_asset_health(tenant=tenant),
        "stored_rows": _stored_row_health(tenant=tenant),
        "recommended_next_actions": _recommended_source_actions(tenant=tenant),
    }


def _meta_credential_health(*, tenant) -> dict[str, Any]:
    credentials = PlatformCredential.all_objects.filter(
        tenant=tenant,
        provider=PlatformCredential.META,
    )
    scopes = set()
    for granted in credentials.values_list("granted_scopes", flat=True):
        if isinstance(granted, list):
            scopes.update(str(scope) for scope in granted)
    required_scopes = {
        "ads_read",
        "business_management",
        "pages_read_engagement",
        "pages_show_list",
    }
    token_status_counts = _count_by(credentials, "token_status")
    return {
        "credential_count": credentials.count(),
        "token_status_counts": token_status_counts,
        "has_valid_credential": bool(token_status_counts.get(PlatformCredential.TOKEN_STATUS_VALID)),
        "has_reauth_required": bool(token_status_counts.get(PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED)),
        "required_scope_coverage": {
            "present": sorted(required_scopes & scopes),
            "missing": sorted(required_scopes - scopes),
        },
        "latest_validated_at": _latest_iso(credentials.aggregate(value=Max("last_validated_at"))["value"]),
        "latest_expires_at": _latest_iso(credentials.aggregate(value=Max("expires_at"))["value"]),
    }


def _meta_page_connection_health(*, tenant) -> dict[str, Any]:
    connections = MetaConnection.all_objects.filter(tenant=tenant)
    pages = MetaPage.all_objects.filter(tenant=tenant)
    scopes = set()
    for granted in connections.values_list("scopes", flat=True):
        if isinstance(granted, list):
            scopes.update(str(scope) for scope in granted)
    required_scopes = {"pages_show_list", "pages_read_engagement"}
    active_count = connections.filter(is_active=True).count()
    page_auth_counts = _page_auth_status_counts(pages)
    usable_page_auth_count = int(page_auth_counts.get("usable", 0))
    return {
        "connection_count": connections.count(),
        "active_count": active_count,
        "inactive_count": connections.filter(is_active=False).count(),
        "has_active_connection": active_count > 0,
        "has_usable_page_auth": usable_page_auth_count > 0,
        "usable_page_auth_count": usable_page_auth_count,
        "unusable_page_auth_count": int(
            page_auth_counts.get("missing", 0) + page_auth_counts.get("unreadable", 0)
        ),
        "page_auth_status_counts": page_auth_counts,
        "required_scope_coverage": {
            "present": sorted(required_scopes & scopes),
            "missing": sorted(required_scopes - scopes),
        },
        "latest_token_expires_at": _latest_iso(connections.aggregate(value=Max("token_expires_at"))["value"]),
    }


def _meta_airbyte_health(*, tenant) -> dict[str, Any]:
    connections = AirbyteConnection.all_objects.filter(
        tenant=tenant,
        provider=PlatformCredential.META,
    )
    error_categories: dict[str, int] = {}
    for error in connections.values_list("last_job_error", flat=True):
        category = _airbyte_error_category(str(error or ""))
        if category:
            error_categories[category] = error_categories.get(category, 0) + 1
    return {
        "connection_count": connections.count(),
        "active_count": connections.filter(is_active=True).count(),
        "inactive_count": connections.filter(is_active=False).count(),
        "last_job_status_counts": _count_by(connections, "last_job_status"),
        "latest_synced_at": _latest_iso(connections.aggregate(value=Max("last_synced_at"))["value"]),
        "latest_completed_at": _latest_iso(connections.aggregate(value=Max("last_job_completed_at"))["value"]),
        "sanitized_error_categories": error_categories,
    }


def _stored_asset_health(*, tenant) -> dict[str, Any]:
    pages = MetaPage.all_objects.filter(tenant=tenant)
    return {
        "ad_account_count": AdAccount.all_objects.filter(tenant=tenant).count(),
        "meta_page_count": pages.count(),
        "analyzable_page_count": pages.filter(can_analyze=True).count(),
        "selected_default_page_count": pages.filter(is_default=True).count(),
    }


def _stored_row_health(*, tenant) -> dict[str, Any]:
    return {
        "paid_meta_ads": _row_summary(
            RawPerformanceRecord.all_objects.filter(tenant=tenant, source__icontains="meta"),
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
            extra_count=MetaPost.all_objects.filter(tenant=tenant).count(),
            extra_count_label="post_count",
        ),
        "content_ops": _content_ops_row_summary(tenant=tenant),
    }


def _snapshot_summary(*, tenant) -> list[dict[str, Any]]:
    rows = []
    for snapshot in TenantMetricsSnapshot.all_objects.filter(tenant=tenant).order_by("source"):
        payload = snapshot.payload if isinstance(snapshot.payload, Mapping) else {}
        data = _snapshot_payload(payload)
        campaign = data.get("campaign") if isinstance(data.get("campaign"), Mapping) else {}
        rows.append(
            {
                "source": snapshot.source,
                "generated_at": snapshot.generated_at.isoformat(),
                "campaign_row_count": _safe_len(campaign.get("rows")),
                "campaign_trend_count": _safe_len(campaign.get("trend")),
                "has_summary": isinstance(campaign.get("summary"), Mapping) and bool(campaign.get("summary")),
            }
        )
    return rows


def _content_ops_row_summary(*, tenant) -> dict[str, Any]:
    from content_ops.models import OrganicPostMetricSnapshot, PublishedPost

    snapshots = OrganicPostMetricSnapshot.all_objects.filter(tenant=tenant)
    published = PublishedPost.all_objects.filter(tenant=tenant)
    summary = _row_summary(snapshots, min_field="metric_date", max_field="metric_date")
    summary["published_post_count"] = published.count()
    published_dates = published.aggregate(min_value=Min("published_at"), max_value=Max("published_at"))
    summary["published_min_date"] = _latest_iso(published_dates["min_value"])
    summary["published_max_date"] = _latest_iso(published_dates["max_value"])
    return summary


def _recommended_source_actions(*, tenant) -> list[str]:
    actions: list[str] = []
    meta_statuses = _count_by(
        PlatformCredential.all_objects.filter(tenant=tenant, provider=PlatformCredential.META),
        "token_status",
    )
    has_valid_meta_credential = bool(meta_statuses.get(PlatformCredential.TOKEN_STATUS_VALID))
    if (
        meta_statuses.get(PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED)
        and not has_valid_meta_credential
    ):
        actions.append("Reconnect Meta OAuth credentials before running fresh Facebook/Meta reporting.")
    airbyte_errors = [
        _airbyte_error_category(str(error or ""))
        for error in AirbyteConnection.all_objects.filter(
            tenant=tenant,
            provider=PlatformCredential.META,
        ).values_list("last_job_error", flat=True)
    ]
    if "destination_connection_refused" in airbyte_errors:
        actions.append("Fix the Airbyte destination/Postgres connectivity before rerunning Meta sync.")
    page_auth_counts = _page_auth_status_counts(MetaPage.all_objects.filter(tenant=tenant))
    if (
        page_auth_counts.get("missing") or page_auth_counts.get("unreadable")
    ) and not page_auth_counts.get("usable"):
        actions.append("Reconnect/select the Facebook Page because the stored Page authorization cannot be used for Page Insights backfill.")
    if not MetaInsightPoint.all_objects.filter(tenant=tenant).exists():
        synced_pages_without_rows = MetaPage.all_objects.filter(
            tenant=tenant,
            last_synced_at__isnull=False,
        ).exists()
        if synced_pages_without_rows:
            actions.append(
                "Meta Page Insights sync has run, but Graph returned no Page insight metric rows; "
                "verify the selected Page/date range in Meta or upload fallback organic values."
            )
        else:
            actions.append("Backfill Facebook Page Insights stored rows for the fixed SLB Page/date range.")
    has_meta_posts = MetaPost.all_objects.filter(tenant=tenant).exists()
    if not MetaPostInsightPoint.all_objects.filter(tenant=tenant).exists():
        if has_meta_posts:
            actions.append(
                "Facebook posts are stored, but Meta returned no post insight metric rows; "
                "top-post activity can render from stored posts while post metrics remain unavailable."
            )
        else:
            actions.append("Backfill Facebook post insight rows for top-post reporting.")
    try:
        from content_ops.models import OrganicPostMetricSnapshot, PublishedPost

        has_content_rows = OrganicPostMetricSnapshot.all_objects.filter(tenant=tenant).exists()
        has_published_posts = PublishedPost.all_objects.filter(tenant=tenant).exists()
    except Exception:  # pragma: no cover - defensive for optional app import drift
        has_content_rows = False
        has_published_posts = False
    if not has_content_rows:
        if has_published_posts:
            actions.append(
                "Content Ops has Meta-linked published posts, but no aggregate metric snapshots; "
                "keep this section activity-only until post insight rows are available."
            )
        else:
            actions.append("Generate or backfill Content Ops aggregate snapshots for the fixed SLB date range.")
    if not actions:
        actions.append("Run fixed-range evidence bundle, export, parity, and adversarial checks.")
    return actions


def _row_summary(
    queryset,
    *,
    min_field: str,
    max_field: str,
    extra_count: int | None = None,
    extra_count_label: str = "",
) -> dict[str, Any]:
    aggregate = queryset.aggregate(count=Count("id"), min_value=Min(min_field), max_value=Max(max_field))
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


def _page_auth_status_counts(queryset) -> dict[str, int]:
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
