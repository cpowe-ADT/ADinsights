"""Stored-data availability summaries for report target selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping

from django.db.models import Count, Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_date

from analytics.models import AdAccount, RawPerformanceRecord
from content_ops.models import OrganicPostMetricSnapshot, PublishedPost
from integrations.models import Client, MetaInsightPoint, MetaPage, MetaPost, MetaPostInsightPoint

from .reporting_source_health import build_reporting_source_health
from .reporting_templates import SLB_MONTHLY_TEMPLATE_KEY, get_report_template_definition

REPORT_AVAILABILITY_BLOCKING_STATUSES = {
    "missing_history",
    "not_previously_synced",
    "partial",
    "permission_missing",
    "unsupported_metric",
}


class ReportingAvailabilityError(ValueError):
    """Safe API-facing availability error."""

    def __init__(self, errors: list[str], *, status_code: int = 400) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
        self.status_code = status_code


@dataclass(frozen=True)
class AvailabilityDateRange:
    start_date: date
    end_date: date
    label: str


def build_report_data_availability(*, tenant, params: Mapping[str, Any]) -> dict[str, Any]:
    """Return tenant-scoped stored data availability for report source selection."""

    template_key = str(params.get("template_key") or SLB_MONTHLY_TEMPLATE_KEY).strip()
    template = get_report_template_definition(template_key)
    if template is None:
        raise ReportingAvailabilityError([f"unknown report template '{template_key}'."])

    date_range = _resolve_date_range(params)
    client_id = str(params.get("client_id") or "").strip()
    account_id = str(params.get("account_id") or "").strip()
    page_id = str(params.get("page_id") or "").strip()
    _validate_scope(tenant=tenant, client_id=client_id, account_id=account_id, page_id=page_id)

    datasets = {
        "paid_meta_ads": _paid_meta_ads_availability(
            tenant=tenant,
            requested=date_range,
            account_id=account_id,
        ),
        "organic_facebook_page": _organic_page_availability(
            tenant=tenant,
            requested=date_range,
            page_id=page_id,
        ),
        "organic_facebook_posts": _organic_posts_availability(
            tenant=tenant,
            requested=date_range,
            page_id=page_id,
        ),
        "content_ops": _content_ops_availability(tenant=tenant, requested=date_range),
    }
    required = list(template.supported_datasets)
    required_for_template = {
        key: value
        for key, value in datasets.items()
        if key in required or (key == "organic_facebook_posts" and "organic_facebook_page" in required)
    }
    blocking = [
        key
        for key, value in required_for_template.items()
        if value["coverage_status"] in REPORT_AVAILABILITY_BLOCKING_STATUSES
    ]
    source_health = build_reporting_source_health(tenant=tenant)
    return {
        "schema_version": "report_data_availability.v1",
        "stored_aggregate_only": True,
        "no_live_provider_calls": True,
        "template": {
            "template_key": template.template_key,
            "label": template.label,
            "version": template.version,
            "supported_datasets": list(template.supported_datasets),
            "required_sources": list(template.required_sources),
            "eligibility": dict(template.eligibility),
        },
        "requested": {
            "date_range": date_range.label,
            "start_date": date_range.start_date.isoformat(),
            "end_date": date_range.end_date.isoformat(),
            "client_id": client_id,
            "account_id": account_id,
            "page_id": page_id,
        },
        "datasets": datasets,
        "blocking_datasets": blocking,
        "eligible_for_report_export": not blocking,
        "recommended_next_actions": source_health["recommended_next_actions"],
    }


def _validate_scope(*, tenant, client_id: str, account_id: str, page_id: str) -> None:
    errors: list[str] = []
    if client_id and not Client.all_objects.filter(id=client_id, tenant=tenant).exists():
        errors.append("client_id does not belong to the authenticated tenant.")
    if account_id and not _account_belongs_to_tenant(tenant=tenant, account_id=account_id):
        errors.append("account_id does not belong to the authenticated tenant.")
    if page_id and not MetaPage.all_objects.filter(tenant=tenant, page_id=page_id).exists():
        errors.append("page_id does not belong to the authenticated tenant.")
    if errors:
        raise ReportingAvailabilityError(errors)


def _paid_meta_ads_availability(
    *,
    tenant,
    requested: AvailabilityDateRange,
    account_id: str,
) -> dict[str, Any]:
    qs = RawPerformanceRecord.all_objects.filter(
        tenant=tenant,
        source__icontains="meta",
        date__gte=requested.start_date,
        date__lte=requested.end_date,
    )
    if account_id:
        qs = qs.filter(ad_account__in=_account_queryset(tenant=tenant, account_id=account_id))
    summary = _date_summary(qs, min_field="date", max_field="date", requested=requested)
    return {
        "dataset": "paid_meta_ads",
        "label": "Paid Meta Ads",
        **summary,
        "available_accounts": _available_accounts(tenant=tenant, requested=requested),
        "source_label": "Stored Meta Ads rows",
    }


def _organic_page_availability(
    *,
    tenant,
    requested: AvailabilityDateRange,
    page_id: str,
) -> dict[str, Any]:
    qs = MetaInsightPoint.all_objects.filter(
        tenant=tenant,
        end_time__date__gte=requested.start_date,
        end_time__date__lte=requested.end_date,
    )
    if page_id:
        qs = qs.filter(page__page_id=page_id)
    summary = _date_summary(qs, min_field="end_time", max_field="end_time", requested=requested)
    return {
        "dataset": "organic_facebook_page",
        "label": "Organic Facebook Page",
        **summary,
        "available_pages": _available_pages(tenant=tenant, requested=requested),
        "source_label": "Stored Facebook Page Insights rows",
    }


def _organic_posts_availability(
    *,
    tenant,
    requested: AvailabilityDateRange,
    page_id: str,
) -> dict[str, Any]:
    posts = MetaPost.all_objects.filter(
        tenant=tenant,
        created_time__date__gte=requested.start_date,
        created_time__date__lte=requested.end_date,
    )
    insights = MetaPostInsightPoint.all_objects.filter(
        tenant=tenant,
        end_time__date__gte=requested.start_date,
        end_time__date__lte=requested.end_date,
    )
    if page_id:
        posts = posts.filter(page__page_id=page_id)
        insights = insights.filter(post__page__page_id=page_id)
    summary = _date_summary(insights, min_field="end_time", max_field="end_time", requested=requested)
    post_dates = posts.aggregate(count=Count("id"), min_value=Min("created_time"), max_value=Max("created_time"))
    post_count = int(post_dates["count"] or 0)
    if post_count and summary["row_count"] == 0:
        summary = {
            **summary,
            "coverage_status": "partial",
            "coverage_note": "Facebook Page posts are stored, but post insight metric rows are unavailable for this range.",
            "min_date": _iso_date(post_dates["min_value"]),
            "max_date": _iso_date(post_dates["max_value"]),
        }
    return {
        "dataset": "organic_facebook_posts",
        "label": "Organic Facebook Top Posts",
        **summary,
        "post_count": post_count,
        "available_pages": _available_pages(tenant=tenant, requested=requested),
        "source_label": "Stored Facebook Page post rows",
    }


def _content_ops_availability(*, tenant, requested: AvailabilityDateRange) -> dict[str, Any]:
    snapshots = OrganicPostMetricSnapshot.all_objects.filter(
        tenant=tenant,
        metric_date__gte=requested.start_date,
        metric_date__lte=requested.end_date,
    )
    published = PublishedPost.all_objects.filter(
        tenant=tenant,
        published_at__date__gte=requested.start_date,
        published_at__date__lte=requested.end_date,
    )
    summary = _date_summary(snapshots, min_field="metric_date", max_field="metric_date", requested=requested)
    published_dates = published.aggregate(count=Count("id"), min_value=Min("published_at"), max_value=Max("published_at"))
    published_count = int(published_dates["count"] or 0)
    if published_count and summary["row_count"] == 0:
        summary = {
            **summary,
            "coverage_status": "partial",
            "coverage_note": "Content Ops published activity exists, but aggregate metric snapshots are unavailable for this range.",
            "min_date": _iso_date(published_dates["min_value"]),
            "max_date": _iso_date(published_dates["max_value"]),
        }
    return {
        "dataset": "content_ops",
        "label": "Content Ops",
        **summary,
        "published_post_count": published_count,
        "source_label": "Stored Content Ops aggregate rows",
    }


def _available_accounts(*, tenant, requested: AvailabilityDateRange) -> list[dict[str, Any]]:
    rows = (
        RawPerformanceRecord.all_objects.filter(
            tenant=tenant,
            source__icontains="meta",
            date__gte=requested.start_date,
            date__lte=requested.end_date,
            ad_account__isnull=False,
        )
        .values("ad_account_id")
        .annotate(row_count=Count("id"), min_date=Min("date"), max_date=Max("date"))
        .order_by("ad_account_id")
    )
    accounts = {
        account.id: account
        for account in AdAccount.all_objects.filter(
            tenant=tenant,
            id__in=[row["ad_account_id"] for row in rows if row.get("ad_account_id")],
        )
    }
    return [
        {
            "id": str(account.id),
            "account_id": account.account_id or account.external_id,
            "external_id": account.external_id,
            "name": account.name,
            "currency": account.currency,
            "row_count": int(row["row_count"] or 0),
            "min_date": _iso_date(row["min_date"]),
            "max_date": _iso_date(row["max_date"]),
        }
        for row in rows
        if (account := accounts.get(row["ad_account_id"])) is not None
    ]


def _available_pages(*, tenant, requested: AvailabilityDateRange) -> list[dict[str, Any]]:
    pages = MetaPage.all_objects.filter(tenant=tenant).order_by("name", "page_id")
    results = []
    for page in pages:
        page_insights = MetaInsightPoint.all_objects.filter(
            tenant=tenant,
            page=page,
            end_time__date__gte=requested.start_date,
            end_time__date__lte=requested.end_date,
        )
        posts = MetaPost.all_objects.filter(
            tenant=tenant,
            page=page,
            created_time__date__gte=requested.start_date,
            created_time__date__lte=requested.end_date,
        )
        post_insights = MetaPostInsightPoint.all_objects.filter(
            tenant=tenant,
            post__page=page,
            end_time__date__gte=requested.start_date,
            end_time__date__lte=requested.end_date,
        )
        insight_summary = page_insights.aggregate(
            row_count=Count("id"),
            min_date=Min("end_time"),
            max_date=Max("end_time"),
        )
        results.append(
            {
                "page_id": page.page_id,
                "name": page.name,
                "can_analyze": page.can_analyze,
                "is_default": page.is_default,
                "last_synced_at": _iso_datetime(page.last_synced_at),
                "last_posts_synced_at": _iso_datetime(page.last_posts_synced_at),
                "page_insight_row_count": int(insight_summary["row_count"] or 0),
                "post_count": posts.count(),
                "post_insight_row_count": post_insights.count(),
                "min_date": _iso_date(insight_summary["min_date"]),
                "max_date": _iso_date(insight_summary["max_date"]),
            }
        )
    return results


def _date_summary(
    queryset,
    *,
    min_field: str,
    max_field: str,
    requested: AvailabilityDateRange,
) -> dict[str, Any]:
    aggregate = queryset.aggregate(row_count=Count("id"), min_value=Min(min_field), max_value=Max(max_field))
    row_count = int(aggregate["row_count"] or 0)
    min_date = _as_date(aggregate["min_value"])
    max_date = _as_date(aggregate["max_value"])
    status = _coverage_status(
        row_count=row_count,
        min_date=min_date,
        max_date=max_date,
        requested=requested,
    )
    return {
        "row_count": row_count,
        "min_date": min_date.isoformat() if min_date else None,
        "max_date": max_date.isoformat() if max_date else None,
        "coverage_status": status,
        "coverage_note": _coverage_note(
            status=status,
            requested=requested,
            min_date=min_date,
            max_date=max_date,
        ),
    }


def _coverage_status(
    *,
    row_count: int,
    min_date: date | None,
    max_date: date | None,
    requested: AvailabilityDateRange,
) -> str:
    if row_count <= 0 or min_date is None or max_date is None:
        return "missing_history"
    if min_date <= requested.start_date and max_date >= requested.end_date:
        return "fresh"
    return "partial"


def _coverage_note(
    *,
    status: str,
    requested: AvailabilityDateRange,
    min_date: date | None,
    max_date: date | None,
) -> str:
    if status == "fresh":
        return "Stored rows cover the requested report range."
    if status == "partial" and min_date and max_date:
        return (
            f"Stored rows cover {min_date.isoformat()} through {max_date.isoformat()}, "
            f"not the full requested range {requested.start_date.isoformat()} through {requested.end_date.isoformat()}."
        )
    return "No stored rows are available for the requested report range."


def _resolve_date_range(params: Mapping[str, Any]) -> AvailabilityDateRange:
    today = timezone.localdate()
    label = str(params.get("date_range") or "").strip()
    start_raw = str(params.get("start_date") or "").strip()
    end_raw = str(params.get("end_date") or "").strip()
    if start_raw or end_raw:
        start = parse_date(start_raw)
        end = parse_date(end_raw)
        if start is None or end is None:
            raise ReportingAvailabilityError(["start_date and end_date must be ISO dates."])
        return _bounded_range(start=start, end=end, label=label or "custom")
    if label == "last_7d":
        return _bounded_range(start=today - timedelta(days=6), end=today, label=label)
    if label in {"last_28d", "last_30d"}:
        days = 27 if label == "last_28d" else 29
        return _bounded_range(start=today - timedelta(days=days), end=today, label=label)
    if label == "last_90d":
        return _bounded_range(start=today - timedelta(days=89), end=today, label=label)
    if label in {"mtd", "this_month"}:
        return _bounded_range(start=today.replace(day=1), end=today, label=label)
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    return _bounded_range(start=last_month_end.replace(day=1), end=last_month_end, label=label or "last_month")


def _bounded_range(*, start: date, end: date, label: str) -> AvailabilityDateRange:
    if end < start:
        raise ReportingAvailabilityError(["end_date must be on or after start_date."])
    if (end - start).days > 366:
        raise ReportingAvailabilityError(["date range cannot exceed 366 days."])
    return AvailabilityDateRange(start_date=start, end_date=end, label=label)


def _account_belongs_to_tenant(*, tenant, account_id: str) -> bool:
    return _account_queryset(tenant=tenant, account_id=account_id).exists()


def _account_queryset(*, tenant, account_id: str):
    aliases = {account_id}
    if account_id.startswith("act_") and account_id[4:]:
        aliases.add(account_id[4:])
    elif account_id.isdigit():
        aliases.add(f"act_{account_id}")
    return AdAccount.all_objects.filter(tenant=tenant).filter(
        models_any_account_alias(aliases)
    )


def models_any_account_alias(aliases: set[str]):
    from django.db.models import Q

    return Q(external_id__in=aliases) | Q(account_id__in=aliases) | Q(id__in=[value for value in aliases if _is_uuid(value)])


def _is_uuid(value: str) -> bool:
    try:
        import uuid

        uuid.UUID(value)
    except (TypeError, ValueError):
        return False
    return True


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value if not hasattr(value, "date") else value.date()
    return None


def _iso_date(value: object) -> str | None:
    parsed = _as_date(value)
    return parsed.isoformat() if parsed else None


def _iso_datetime(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None
