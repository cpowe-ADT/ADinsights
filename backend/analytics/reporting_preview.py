"""Read-only dashboard.v1 widget preview over stored aggregate data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Mapping

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from adapters.meta_direct import MetaDirectAdapter
from analytics.models import AdAccount, TenantMetricsSnapshot
from integrations.clients.resolver import resolve_client_accounts
from integrations.models import (
    AirbyteConnection,
    Client,
    ClientPlatformAccount,
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)
from integrations.services.metric_registry import (
    get_reporting_metric_source_map,
    map_reporting_source_metric_to_product_metric,
)

from .reporting_catalog import (
    COVERAGE_STATUSES,
    ReportingCatalogValidationError,
    validate_dashboard_widget,
)


class ReportingWidgetPreviewError(ValueError):
    """Safe API-facing preview error."""

    def __init__(self, errors: list[str], *, status_code: int = 400) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
        self.status_code = status_code


@dataclass(frozen=True)
class PreviewDateRange:
    start_date: date
    end_date: date
    label: str


PAGE_METRIC_SOURCE_KEYS = get_reporting_metric_source_map(
    "organic_facebook_page",
    level=MetaMetricRegistry.LEVEL_PAGE,
)

POST_METRIC_SOURCE_KEYS = get_reporting_metric_source_map(
    "organic_facebook_page",
    level=MetaMetricRegistry.LEVEL_POST,
)

SUMMARY_KEYS = {
    "spend": ("totalSpend", "spend", "cost"),
    "impressions": ("totalImpressions", "impressions"),
    "reach": ("totalReach", "reach"),
    "clicks": ("totalClicks", "clicks"),
    "conversions": ("totalConversions", "conversions"),
    "conversion_value": (
        "totalConversionValue",
        "conversion_value",
        "conversions_value",
    ),
    "ctr": ("ctr",),
    "cpc": ("averageCpc", "cpc"),
    "cpm": ("averageCpm", "cpm"),
    "cpa": ("averageCpa", "cpa"),
    "roas": ("averageRoas", "roas"),
    "frequency": ("frequency",),
}

CONTENT_OPS_METRIC_FIELDS = {
    "content_ops_reach": "reach",
    "content_ops_engagements": "engagements",
    "content_ops_impressions": "impressions",
}

PAID_SNAPSHOT_SOURCE_LABELS = {
    "meta_direct": "Direct Meta stored snapshot",
    "warehouse": "Warehouse aggregate metrics",
    "upload": "Stored upload metrics",
}

PAID_SUMMARY_TOTAL_KEYS = {
    "spend": "totalSpend",
    "impressions": "totalImpressions",
    "reach": "totalReach",
    "clicks": "totalClicks",
    "conversions": "totalConversions",
    "conversion_value": "totalConversionValue",
}


def _source_keys_for_metrics(
    *,
    metrics: list[str],
    mapping: Mapping[str, tuple[str, ...]],
) -> list[str]:
    keys: list[str] = []
    for metric in metrics:
        source_keys = mapping.get(metric)
        if source_keys is None:
            continue
        if metric not in keys:
            keys.append(metric)
        for source_key in source_keys:
            if source_key not in keys:
                keys.append(source_key)
    return keys


def _reverse_source_map(mapping: Mapping[str, tuple[str, ...]]) -> dict[str, str]:
    reverse: dict[str, str] = {}
    for product_metric, source_keys in mapping.items():
        for source_key in source_keys:
            reverse.setdefault(source_key, product_metric)
    return reverse


def build_widget_preview(*, tenant, payload: Mapping[str, Any]) -> dict[str, Any]:
    widget_payload = payload.get("widget")
    if not isinstance(widget_payload, Mapping):
        raise ReportingWidgetPreviewError(["widget is required."])

    widget = dict(widget_payload)
    filters = dict(widget.get("filters") or {})
    for scope_key in ("client_id", "account_id", "page_id"):
        scope_value = payload.get(scope_key)
        if scope_value and not filters.get(scope_key):
            filters[scope_key] = scope_value
    request_range = payload.get("date_range")
    if isinstance(request_range, Mapping):
        filters.update(
            {
                key: value
                for key, value in request_range.items()
                if key in {"date_range", "start_date", "end_date"} and value
            }
        )
    widget["filters"] = filters

    try:
        widget = validate_dashboard_widget(widget)
    except ReportingCatalogValidationError as exc:
        raise ReportingWidgetPreviewError(exc.errors) from exc

    _validate_tenant_references(tenant=tenant, payload=payload, widget=widget)
    date_range = _resolve_date_range(widget.get("filters"))
    dataset = str(widget["dataset"])

    result = _preview_dataset(
        tenant=tenant, widget=widget, date_range=date_range, payload=payload
    )

    coverage = result["coverage"]
    policy = str(widget.get("coverage_policy") or "render_with_warning")
    block_reason = _coverage_block_reason(policy=policy, coverage=coverage)
    if block_reason:
        raise ReportingWidgetPreviewError([block_reason], status_code=409)

    return {
        "widget_id": widget["id"],
        "dataset": dataset,
        "type": widget["type"],
        "metrics": _string_list(widget.get("metrics")),
        "dimensions": _string_list(widget.get("dimensions")),
        "data": result["data"],
        "coverage": coverage,
        "warnings": result["warnings"],
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _preview_dataset(
    *,
    tenant,
    widget: Mapping[str, Any],
    date_range: PreviewDateRange,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    dataset = str(widget["dataset"])
    adapter = DATASET_PREVIEW_ADAPTERS.get(dataset)
    if adapter is None:
        raise ReportingWidgetPreviewError(
            [f"dataset '{dataset}' is unsupported for preview."]
        )
    return adapter(tenant=tenant, widget=widget, date_range=date_range, payload=payload)


def _validate_tenant_references(
    *, tenant, payload: Mapping[str, Any], widget: Mapping[str, Any]
) -> None:
    errors: list[str] = []
    filters = (
        widget.get("filters") if isinstance(widget.get("filters"), Mapping) else {}
    )

    client_id = str(payload.get("client_id") or filters.get("client_id") or "").strip()
    if (
        client_id
        and not Client.all_objects.filter(id=client_id, tenant=tenant).exists()
    ):
        errors.append("client_id does not belong to the authenticated tenant.")

    account_id = str(
        payload.get("account_id") or filters.get("account_id") or ""
    ).strip()
    if account_id and not _account_belongs_to_tenant(
        tenant=tenant, account_id=account_id
    ):
        errors.append("account_id does not belong to the authenticated tenant.")

    page_id = str(payload.get("page_id") or filters.get("page_id") or "").strip()
    if (
        page_id
        and not MetaPage.all_objects.filter(tenant=tenant, page_id=page_id).exists()
    ):
        errors.append("page_id does not belong to the authenticated tenant.")

    if errors:
        raise ReportingWidgetPreviewError(errors)


def _account_belongs_to_tenant(*, tenant, account_id: str) -> bool:
    aliases = _account_aliases(account_id)
    return (
        AdAccount.all_objects.filter(
            tenant=tenant,
            external_id__in=aliases,
        ).exists()
        or AdAccount.all_objects.filter(
            tenant=tenant,
            account_id__in=aliases,
        ).exists()
    )


def _account_aliases(account_id: str) -> set[str]:
    aliases = {account_id}
    if account_id.startswith("act_") and account_id[4:]:
        aliases.add(account_id[4:])
    elif account_id.isdigit():
        aliases.add(f"act_{account_id}")
    return {alias for alias in aliases if alias}


def _resolve_date_range(filters: object) -> PreviewDateRange:
    if not isinstance(filters, Mapping):
        raise ReportingWidgetPreviewError(
            ["widget.filters must include a bounded date range."]
        )

    today = timezone.localdate()
    date_range = str(filters.get("date_range") or "").strip()
    if date_range == "custom":
        start = _parse_required_date(filters.get("start_date"), field="start_date")
        end = _parse_required_date(filters.get("end_date"), field="end_date")
        return _bounded_range(start=start, end=end, label="custom")
    if filters.get("start_date") and filters.get("end_date"):
        start = _parse_required_date(filters.get("start_date"), field="start_date")
        end = _parse_required_date(filters.get("end_date"), field="end_date")
        return _bounded_range(start=start, end=end, label=date_range or "custom")

    if date_range == "last_7d":
        return _bounded_range(
            start=today - timedelta(days=6), end=today, label=date_range
        )
    if date_range in {"last_28d", "last_30d"}:
        days = 27 if date_range == "last_28d" else 29
        return _bounded_range(
            start=today - timedelta(days=days), end=today, label=date_range
        )
    if date_range == "last_90d":
        return _bounded_range(
            start=today - timedelta(days=89), end=today, label=date_range
        )
    if date_range in {"mtd", "this_month"}:
        return _bounded_range(start=today.replace(day=1), end=today, label=date_range)
    if date_range == "last_month":
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        return _bounded_range(
            start=last_month_end.replace(day=1),
            end=last_month_end,
            label=date_range,
        )
    raise ReportingWidgetPreviewError(
        ["widget.filters must include a bounded date range."]
    )


def _parse_required_date(value: object, *, field: str) -> date:
    parsed = parse_date(str(value or ""))
    if parsed is None:
        raise ReportingWidgetPreviewError([f"{field} must be an ISO date."])
    return parsed


def _bounded_range(*, start: date, end: date, label: str) -> PreviewDateRange:
    if end < start:
        raise ReportingWidgetPreviewError(["end_date must be on or after start_date."])
    if (end - start).days > 397:
        raise ReportingWidgetPreviewError(
            ["date range cannot exceed 13 months for dashboard preview."]
        )
    return PreviewDateRange(start_date=start, end_date=end, label=label)


def _preview_paid_dataset(
    *, tenant, widget: Mapping[str, Any], date_range: PreviewDateRange
) -> dict[str, Any]:
    source = "meta_direct"
    snapshot = None
    payload = _paid_direct_payload_for_range(
        tenant=tenant, widget=widget, date_range=date_range
    )
    payload_generated_at = _generated_at_from_payload(payload)

    if payload is None:
        source, snapshot = _select_paid_snapshot(
            tenant=tenant, dataset=str(widget["dataset"])
        )
        payload = snapshot.payload if snapshot else {}

    payload = _snapshot_payload(payload)
    campaign = (
        payload.get("campaign") if isinstance(payload.get("campaign"), Mapping) else {}
    )
    snapshot_summary = (
        campaign.get("summary") if isinstance(campaign.get("summary"), Mapping) else {}
    )
    rows = _filter_rows_by_date_range(
        rows=_normalize_paid_rows(
            [row for row in campaign.get("rows", []) if isinstance(row, Mapping)]
        ),
        date_range=date_range,
    )
    trend = _filter_rows_by_date_range(
        rows=[row for row in campaign.get("trend", []) if isinstance(row, Mapping)],
        date_range=date_range,
    )
    summary = _paid_summary_for_range(
        snapshot_summary=snapshot_summary, rows=rows, trend=trend
    )

    data = _render_widget_data(widget=widget, summary=summary, rows=rows, trend=trend)
    row_count = len(rows) or len(trend) or (1 if summary else 0)
    coverage = _build_snapshot_coverage(
        dataset=str(widget["dataset"]),
        source_label=PAID_SNAPSHOT_SOURCE_LABELS.get(
            source, "Stored aggregate metrics"
        ),
        requested=date_range,
        snapshot=snapshot,
        generated_at=payload_generated_at,
        row_count=row_count,
        data_dates=_dates_from_rows([*rows, *trend]),
        source_disconnected=_has_inactive_meta_connection(tenant=tenant),
    )
    return {
        "data": data,
        "coverage": coverage,
        "warnings": _warnings_for_coverage(coverage),
    }


def _select_paid_snapshot(
    *, tenant, dataset: str
) -> tuple[str, TenantMetricsSnapshot | None]:
    sources = (
        ("upload",)
        if dataset == "csv_upload"
        else ("meta_direct", "warehouse", "upload")
    )
    candidates: list[tuple[str, TenantMetricsSnapshot, int]] = []
    for source in sources:
        snapshot = TenantMetricsSnapshot.latest_for(tenant=tenant, source=source)
        if snapshot is not None:
            candidates.append((source, snapshot, _paid_snapshot_row_count(snapshot)))

    if not candidates:
        return sources[0], None

    non_empty = [candidate for candidate in candidates if candidate[2] > 0]
    source, snapshot, _row_count = max(
        non_empty or candidates,
        key=lambda candidate: (candidate[1].generated_at, candidate[1].created_at),
    )
    return source, snapshot


def _paid_snapshot_row_count(snapshot: TenantMetricsSnapshot) -> int:
    payload = _snapshot_payload(snapshot.payload)
    return _paid_payload_row_count(payload)


def _paid_payload_row_count(payload: Mapping[str, Any]) -> int:
    campaign = (
        payload.get("campaign") if isinstance(payload.get("campaign"), Mapping) else {}
    )
    summary = (
        campaign.get("summary") if isinstance(campaign.get("summary"), Mapping) else {}
    )
    rows = [row for row in campaign.get("rows", []) if isinstance(row, Mapping)]
    trend = [row for row in campaign.get("trend", []) if isinstance(row, Mapping)]
    return len(rows) or len(trend) or (1 if summary else 0)


def _paid_direct_payload_for_range(
    *,
    tenant,
    widget: Mapping[str, Any],
    date_range: PreviewDateRange,
) -> dict[str, Any] | None:
    if str(widget["dataset"]) == "csv_upload":
        return None

    filters = (
        widget.get("filters") if isinstance(widget.get("filters"), Mapping) else {}
    )
    options: dict[str, Any] = {
        "start_date": date_range.start_date.isoformat(),
        "end_date": date_range.end_date.isoformat(),
    }
    for key in ("account_id", "client_id", "channels", "campaign_search"):
        value = filters.get(key)
        if value:
            options[key] = value
    options.update(
        _client_meta_scoping_options(
            tenant=tenant,
            client_id=str(filters.get("client_id") or "").strip(),
            account_id=str(filters.get("account_id") or "").strip(),
        )
    )

    payload = dict(
        MetaDirectAdapter().fetch_metrics(tenant_id=str(tenant.id), options=options)
    )
    normalized_payload = _snapshot_payload(payload)
    if not _paid_payload_has_rows(normalized_payload):
        has_specific_filters = any(
            filters.get(key)
            for key in ("account_id", "client_id", "channels", "campaign_search")
        )
        return normalized_payload if has_specific_filters else None
    return normalized_payload


def _client_meta_scoping_options(
    *, tenant, client_id: str, account_id: str
) -> dict[str, Any]:
    if not client_id:
        return {}
    try:
        bundle = resolve_client_accounts(
            str(tenant.id),
            client_id,
            platforms={ClientPlatformAccount.PLATFORM_META_ADS},
        )
    except (Client.DoesNotExist, ValueError):
        return {
            "client_scoped_meta_ad_account_ids": [],
            "client_scope_requested": True,
        }

    scoped_aliases: set[str] = set()
    for linked_account_id in bundle.meta_ad_account_ids:
        scoped_aliases.update(_account_aliases(str(linked_account_id)))
    if account_id:
        scoped_aliases &= _account_aliases(account_id)
    return {
        "client_scoped_meta_ad_account_ids": sorted(scoped_aliases),
        "client_scope_requested": True,
    }


def _paid_payload_has_rows(payload: Mapping[str, Any]) -> bool:
    campaign = (
        payload.get("campaign") if isinstance(payload.get("campaign"), Mapping) else {}
    )
    rows = [row for row in campaign.get("rows", []) if isinstance(row, Mapping)]
    trend = [row for row in campaign.get("trend", []) if isinstance(row, Mapping)]
    return bool(rows or trend)


def _generated_at_from_payload(payload: Mapping[str, Any] | None):
    if not isinstance(payload, Mapping):
        return None
    generated_at = payload.get("snapshot_generated_at")
    if not generated_at:
        return None
    parsed = parse_datetime(str(generated_at))
    if parsed is None:
        return None
    return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)


def _normalize_paid_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    normalized: list[Mapping[str, Any]] = []
    for row in rows:
        if "campaign" in row or "name" not in row:
            normalized.append(row)
            continue
        normalized.append({**row, "campaign": row.get("name")})
    return normalized


def _filter_rows_by_date_range(
    *,
    rows: list[Mapping[str, Any]],
    date_range: PreviewDateRange,
) -> list[Mapping[str, Any]]:
    filtered: list[Mapping[str, Any]] = []
    for row in rows:
        if _row_overlaps_date_range(row=row, date_range=date_range):
            filtered.append(row)
    return filtered


def _row_overlaps_date_range(
    *, row: Mapping[str, Any], date_range: PreviewDateRange
) -> bool:
    row_date = _row_date(row)
    if row_date is not None:
        return date_range.start_date <= row_date <= date_range.end_date

    row_start = _row_start_date(row)
    row_end = _row_end_date(row)
    if row_start is None and row_end is None:
        return False
    row_start = row_start or row_end
    row_end = row_end or row_start
    if row_start is None or row_end is None:
        return False
    return row_start <= date_range.end_date and row_end >= date_range.start_date


def _row_date(row: Mapping[str, Any]) -> date | None:
    for key in ("date", "date_day", "day"):
        value = row.get(key)
        if value:
            return parse_date(str(value)[:10])
    return None


def _row_start_date(row: Mapping[str, Any]) -> date | None:
    for key in ("start_date", "startDate"):
        value = row.get(key)
        if value:
            return parse_date(str(value)[:10])
    return None


def _row_end_date(row: Mapping[str, Any]) -> date | None:
    for key in ("end_date", "endDate"):
        value = row.get(key)
        if value:
            return parse_date(str(value)[:10])
    return None


def _paid_summary_for_range(
    *,
    snapshot_summary: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    trend: list[Mapping[str, Any]],
) -> dict[str, Any]:
    source_rows = rows or trend
    if not source_rows:
        return {}

    summary = dict(snapshot_summary)
    totals: dict[str, float | None] = {}
    for metric, summary_key in PAID_SUMMARY_TOTAL_KEYS.items():
        total = _sum_metric_values(rows=source_rows, metric=metric)
        totals[metric] = total
        summary[summary_key] = total
        summary[metric] = total

    impressions = totals.get("impressions")
    reach = totals.get("reach")
    clicks = totals.get("clicks")
    spend = totals.get("spend")
    conversions = totals.get("conversions")
    conversion_value = totals.get("conversion_value")

    summary["ctr"] = _metric_ratio(clicks, impressions)
    summary["averageCpc"] = _metric_ratio(spend, clicks)
    summary["cpc"] = summary["averageCpc"]
    summary["averageCpm"] = _metric_ratio(spend, impressions, scale=1000)
    summary["cpm"] = summary["averageCpm"]
    summary["averageCpa"] = _metric_ratio(spend, conversions)
    summary["cpa"] = summary["averageCpa"]
    summary["averageRoas"] = _metric_ratio(conversion_value, spend)
    summary["roas"] = summary["averageRoas"]
    summary["frequency"] = _metric_ratio(impressions, reach)
    return summary


def _sum_metric_values(
    *, rows: list[Mapping[str, Any]], metric: str
) -> float | None:
    values = [
        float(value)
        for row in rows
        if (value := _metric_value(row, metric)) is not None
    ]
    return sum(values) if values else None


def _metric_ratio(
    numerator: float | None, denominator: float | None, *, scale: float = 1.0
) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * scale


def _preview_organic_page_dataset(
    *,
    tenant,
    widget: Mapping[str, Any],
    date_range: PreviewDateRange,
    page_id: str,
) -> dict[str, Any]:
    metrics = [str(metric) for metric in widget.get("metrics", [])]
    dimensions = [str(dimension) for dimension in widget.get("dimensions", [])]
    page_filter = {"page__page_id": page_id} if page_id else {}
    page_metric_keys = _source_keys_for_metrics(
        metrics=metrics, mapping=PAGE_METRIC_SOURCE_KEYS
    )
    post_metric_keys = _source_keys_for_metrics(
        metrics=metrics, mapping=POST_METRIC_SOURCE_KEYS
    )

    if "post" in dimensions or post_metric_keys:
        rows = _post_rows(
            tenant=tenant,
            metric_keys=post_metric_keys,
            product_metrics=metrics,
            date_range=date_range,
            page_filter=page_filter,
            limit=_row_limit(widget),
        )
        summary = _sum_rows(rows=rows, metrics=metrics)
        data = _render_widget_data(
            widget=widget, summary=summary, rows=rows, trend=rows
        )
        data_dates = [row["date"] for row in rows if row.get("date")]
        has_metric_values = any(
            row.get(metric) is not None
            for row in rows
            for metric in metrics
            if metric in POST_METRIC_SOURCE_KEYS
        )
        source_label = (
            "Facebook Page Post Insights stored rows"
            if has_metric_values
            else "Facebook Page synced posts"
        )
    else:
        rows = _page_metric_rows(
            tenant=tenant,
            metric_keys=page_metric_keys,
            date_range=date_range,
            page_filter=page_filter,
        )
        summary = _sum_rows(rows=rows, metrics=metrics)
        data = _render_widget_data(
            widget=widget, summary=summary, rows=rows, trend=rows
        )
        data_dates = [row["date"] for row in rows if row.get("date")]
        source_label = "Facebook Page Insights stored rows"

    row_count = len(rows)
    coverage = _build_row_coverage(
        dataset="organic_facebook_page",
        source_label=source_label,
        requested=date_range,
        row_count=row_count,
        data_dates=data_dates,
        source_disconnected=_has_inactive_meta_connection(tenant=tenant),
    )
    if rows and source_label == "Facebook Page synced posts":
        coverage = {
            **coverage,
            "coverage_note": (
                "Facebook Page posts are stored, but post insight metric rows are unavailable "
                "for this range."
            ),
        }
    return {
        "data": data,
        "coverage": coverage,
        "warnings": _warnings_for_coverage(coverage),
    }


def _preview_content_ops_dataset(
    *, tenant, widget: Mapping[str, Any], date_range: PreviewDateRange
) -> dict[str, Any]:
    from content_ops.models import OrganicPostMetricSnapshot, PublishedPost

    metrics = [str(metric) for metric in widget.get("metrics", [])]
    rows: list[dict[str, Any]] = []
    snapshot_qs = OrganicPostMetricSnapshot.all_objects.filter(
        tenant=tenant,
        metric_date__gte=date_range.start_date,
        metric_date__lte=date_range.end_date,
    )
    snapshot_by_date = snapshot_qs.values("metric_date").annotate(
        reach=Sum("reach"),
        engagements=Sum("engagements"),
        impressions=Sum("impressions"),
        clicks=Sum("clicks"),
    )
    for row in snapshot_by_date:
        rows.append(
            {
                "date": row["metric_date"].isoformat(),
                "content_ops_reach": _number(row.get("reach")),
                "content_ops_engagements": _number(row.get("engagements")),
                "content_ops_impressions": _number(row.get("impressions")),
                "clicks": _number(row.get("clicks")),
            }
        )

    published_count = PublishedPost.all_objects.filter(
        tenant=tenant,
        published_at__date__gte=date_range.start_date,
        published_at__date__lte=date_range.end_date,
    ).count()
    if "published_posts" in metrics:
        rows.append(
            {
                "date": date_range.end_date.isoformat(),
                "published_posts": published_count,
            }
        )

    summary = _sum_rows(rows=rows, metrics=metrics)
    if "published_posts" in metrics:
        summary["published_posts"] = published_count

    aggregate = snapshot_qs.aggregate(count=Count("id"))
    snapshot_count = int(aggregate["count"] or 0)
    row_count = snapshot_count or published_count
    data_dates = [row["date"] for row in rows if row.get("date")]
    coverage = _build_row_coverage(
        dataset="content_ops",
        source_label=(
            "Content Ops aggregate snapshots"
            if snapshot_count
            else "Content Ops imported post activity"
        ),
        requested=date_range,
        row_count=row_count,
        data_dates=data_dates,
        source_disconnected=False,
    )
    if published_count and not snapshot_count:
        coverage = {
            **coverage,
            "coverage_status": "partial",
            "freshness_status": "partial",
            "history_status": "available",
            "coverage_note": (
                f"Content Ops has {published_count} Meta-linked published post(s), "
                "but post insight metric snapshots are unavailable for this range."
            ),
        }
    data = _render_widget_data(widget=widget, summary=summary, rows=rows, trend=rows)
    return {
        "data": data,
        "coverage": coverage,
        "warnings": _warnings_for_coverage(coverage),
    }


def _preview_paid_adapter(
    *,
    tenant,
    widget: Mapping[str, Any],
    date_range: PreviewDateRange,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    del payload
    return _preview_paid_dataset(tenant=tenant, widget=widget, date_range=date_range)


def _preview_organic_page_adapter(
    *,
    tenant,
    widget: Mapping[str, Any],
    date_range: PreviewDateRange,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    filters = (
        widget.get("filters") if isinstance(widget.get("filters"), Mapping) else {}
    )
    return _preview_organic_page_dataset(
        tenant=tenant,
        widget=widget,
        date_range=date_range,
        page_id=str(payload.get("page_id") or filters.get("page_id") or "").strip(),
    )


def _preview_content_ops_adapter(
    *,
    tenant,
    widget: Mapping[str, Any],
    date_range: PreviewDateRange,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    del payload
    return _preview_content_ops_dataset(
        tenant=tenant, widget=widget, date_range=date_range
    )


DATASET_PREVIEW_ADAPTERS = {
    "paid_meta_ads": _preview_paid_adapter,
    "combined_paid_media": _preview_paid_adapter,
    "csv_upload": _preview_paid_adapter,
    "organic_facebook_page": _preview_organic_page_adapter,
    "content_ops": _preview_content_ops_adapter,
}


def _snapshot_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    for key in ("metrics", "snapshot", "data", "results", "payload"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return dict(payload)


def _render_widget_data(
    *,
    widget: Mapping[str, Any],
    summary: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    trend: list[Mapping[str, Any]],
) -> dict[str, Any]:
    widget_type = str(widget["type"])
    metrics = [str(metric) for metric in widget.get("metrics", [])]
    dimensions = [str(dimension) for dimension in widget.get("dimensions", [])]

    if widget_type == "kpi":
        return {
            "kind": "kpi",
            "metrics": [
                {
                    "key": metric,
                    "label": _label(metric),
                    "value": _metric_value(summary, metric),
                }
                for metric in metrics
            ],
        }
    if widget_type == "line_chart":
        return {
            "kind": "timeseries",
            "x": dimensions[0] if dimensions else "date",
            "rows": [
                _project_row(row, dimensions=["date"], metrics=metrics) for row in trend
            ],
        }
    if widget_type == "bar_chart":
        dimension = dimensions[0] if dimensions else "source"
        return {
            "kind": "bar",
            "x": dimension,
            "rows": _group_rows(rows=rows, dimension=dimension, metrics=metrics),
        }
    if widget_type == "data_table":
        limit = _row_limit(widget)
        columns = [*dimensions, *metrics]
        extra_columns = [
            extra_column
            for extra_column in ("date", "content", "permalink")
            if (
                extra_column not in columns
                and any(row.get(extra_column) not in {None, ""} for row in rows)
            )
        ]
        if extra_columns:
            if "post" in columns:
                columns = [
                    "post",
                    *extra_columns,
                    *[column for column in columns if column != "post"],
                ]
            else:
                columns = [*dimensions, *extra_columns, *metrics]
        return {
            "kind": "table",
            "columns": columns,
            "row_limit": limit,
            "rows": [
                _project_row(row, dimensions=columns, metrics=[])
                for row in rows[:limit]
            ],
        }
    return {"kind": widget_type, "rows": []}


def _page_metric_rows(
    *,
    tenant,
    metric_keys: list[str],
    date_range: PreviewDateRange,
    page_filter: dict[str, str],
) -> list[dict[str, Any]]:
    if not metric_keys:
        return []
    queryset = (
        MetaInsightPoint.all_objects.filter(
            tenant=tenant,
            metric_key__in=metric_keys,
            end_time__date__gte=date_range.start_date,
            end_time__date__lte=date_range.end_date,
            **page_filter,
        )
        .values("end_time__date", "metric_key")
        .annotate(value=Sum("value_num"))
        .order_by("end_time__date")
    )
    by_date: dict[str, dict[str, Any]] = {}
    for point in queryset:
        day = point["end_time__date"].isoformat()
        row = by_date.setdefault(day, {"date": day})
        product_metric = map_reporting_source_metric_to_product_metric(
            "organic_facebook_page",
            str(point["metric_key"]),
            level=MetaMetricRegistry.LEVEL_PAGE,
        )
        target_metric = product_metric or point["metric_key"]
        value = _number(point["value"])
        if value is not None or row.get(target_metric) is None:
            row[target_metric] = value
    return list(by_date.values())


def _post_rows(
    *,
    tenant,
    metric_keys: list[str],
    product_metrics: list[str],
    date_range: PreviewDateRange,
    page_filter: dict[str, str],
    limit: int,
) -> list[dict[str, Any]]:
    if not metric_keys:
        return _post_activity_rows(
            tenant=tenant,
            product_metrics=product_metrics,
            date_range=date_range,
            page_filter=page_filter,
            limit=limit,
        )
    post_filter = {f"post__{key}": value for key, value in page_filter.items()}
    queryset = (
        MetaPostInsightPoint.all_objects.filter(
            tenant=tenant,
            metric_key__in=metric_keys,
            end_time__date__gte=date_range.start_date,
            end_time__date__lte=date_range.end_date,
            **post_filter,
        )
        .values(
            "post__post_id",
            "post__message",
            "end_time__date",
            "metric_key",
            "breakdown_key",
            "breakdown_key_normalized",
        )
        .annotate(value=Sum("value_num"))
        .order_by("post__post_id", "metric_key", "breakdown_key_normalized")[
            : max(limit * max(len(metric_keys), 1), limit)
        ]
    )
    rows: dict[str, dict[str, Any]] = {}
    for point in queryset:
        post_id = point["post__post_id"]
        row = rows.setdefault(
            post_id,
            {
                "post": post_id,
                "date": point["end_time__date"].isoformat(),
                "content": point["post__message"] or "",
            },
        )
        product_metric = map_reporting_source_metric_to_product_metric(
            "organic_facebook_page",
            str(point["metric_key"]),
            breakdown_key=str(
                point.get("breakdown_key_normalized")
                or point.get("breakdown_key")
                or ""
            ),
            level=MetaMetricRegistry.LEVEL_POST,
        )
        if product_metric is None:
            continue
        value = _number(point["value"])
        if value is not None or row.get(product_metric) is None:
            row[product_metric] = value
    rendered_rows = list(rows.values())[:limit]
    if rendered_rows:
        return rendered_rows
    return _post_activity_rows(
        tenant=tenant,
        product_metrics=product_metrics,
        date_range=date_range,
        page_filter=page_filter,
        limit=limit,
    )


def _post_activity_rows(
    *,
    tenant,
    product_metrics: list[str],
    date_range: PreviewDateRange,
    page_filter: dict[str, str],
    limit: int,
) -> list[dict[str, Any]]:
    posts = MetaPost.all_objects.filter(
        tenant=tenant,
        created_time__date__gte=date_range.start_date,
        created_time__date__lte=date_range.end_date,
        **page_filter,
    ).order_by("-created_time", "post_id")[:limit]
    rows: list[dict[str, Any]] = []
    for post in posts:
        row: dict[str, Any] = {
            "post": post.post_id,
            "date": post.created_time.date().isoformat() if post.created_time else "",
            "content": post.message or "",
            "permalink": post.permalink_url or "",
        }
        for metric in product_metrics:
            if metric in POST_METRIC_SOURCE_KEYS:
                row.setdefault(metric, None)
        rows.append(row)
    return rows


def _sum_rows(
    *, rows: list[Mapping[str, Any]], metrics: list[str]
) -> dict[str, float | None]:
    summary: dict[str, float | None] = {}
    for metric in metrics:
        values = [
            float(value)
            for row in rows
            if (value := _metric_value(row, metric)) is not None
        ]
        summary[metric] = sum(values) if values else None
    return summary


def _group_rows(
    *,
    rows: list[Mapping[str, Any]],
    dimension: str,
    metrics: list[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(dimension) or row.get(_camel(dimension)) or "Unspecified")
        target = grouped.setdefault(key, {dimension: key})
        for metric in metrics:
            value = _metric_value(row, metric)
            if value is None:
                target.setdefault(metric, None)
                continue
            current = target.get(metric)
            target[metric] = float(value) if current is None else float(current) + float(value)
    return list(grouped.values())


def _project_row(
    row: Mapping[str, Any],
    *,
    dimensions: list[str],
    metrics: list[str],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for dimension in dimensions:
        output[dimension] = row.get(dimension) or row.get(_camel(dimension))
    for metric in metrics:
        output[metric] = _metric_value(row, metric)
    return output


def _metric_value(source: Mapping[str, Any], metric: str) -> Any:
    for key in SUMMARY_KEYS.get(metric, (metric, _camel(metric))):
        if key in source and source[key] is not None:
            return _number(source[key])
    if metric in CONTENT_OPS_METRIC_FIELDS:
        for key in (metric, CONTENT_OPS_METRIC_FIELDS[metric]):
            if key in source and source[key] is not None:
                return _number(source[key])
        return None
    for key in (metric, _camel(metric)):
        if key in source and source[key] is not None:
            return _number(source[key])
    return None


def _number(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_limit(widget: Mapping[str, Any]) -> int:
    for source in (widget, widget.get("visual"), widget.get("options")):
        if isinstance(source, Mapping) and isinstance(source.get("row_limit"), int):
            return max(1, min(int(source["row_limit"]), 500))
    return 50


def _dates_from_rows(rows: list[Mapping[str, Any]]) -> list[str]:
    dates = []
    for row in rows:
        row_date = _row_date(row)
        if row_date is not None:
            dates.append(row_date.isoformat())
            continue
        for value in (_row_start_date(row), _row_end_date(row)):
            if value is not None:
                dates.append(value.isoformat())
    return dates


def _build_snapshot_coverage(
    *,
    dataset: str,
    source_label: str,
    requested: PreviewDateRange,
    snapshot: TenantMetricsSnapshot | None,
    generated_at=None,
    row_count: int,
    data_dates: list[str],
    source_disconnected: bool,
) -> dict[str, Any]:
    if snapshot is None and generated_at is None:
        return _coverage_payload(
            dataset=dataset,
            requested=requested,
            status="not_previously_synced",
            source_label=source_label,
            row_count=0,
            note=f"{source_label} has not been synced for this tenant yet.",
        )
    generated_at = generated_at or snapshot.generated_at
    base_status = _coverage_status_from_dates(
        requested=requested,
        row_count=row_count,
        data_dates=data_dates,
    )
    if base_status == "fresh" and _is_stale(generated_at):
        base_status = "stale"
    if source_disconnected and row_count and base_status in {"fresh", "stale"}:
        base_status = "source_disconnected"
    return _coverage_payload(
        dataset=dataset,
        requested=requested,
        status=base_status,
        source_label=source_label,
        row_count=row_count,
        generated_at=generated_at,
        data_dates=data_dates,
    )


def _build_row_coverage(
    *,
    dataset: str,
    source_label: str,
    requested: PreviewDateRange,
    row_count: int,
    data_dates: list[str],
    source_disconnected: bool,
) -> dict[str, Any]:
    status = _coverage_status_from_dates(
        requested=requested,
        row_count=row_count,
        data_dates=data_dates,
    )
    if source_disconnected and row_count and status == "fresh":
        status = "source_disconnected"
    return _coverage_payload(
        dataset=dataset,
        requested=requested,
        status=status,
        source_label=source_label,
        row_count=row_count,
        data_dates=data_dates,
    )


def _coverage_status_from_dates(
    *,
    requested: PreviewDateRange,
    row_count: int,
    data_dates: list[str],
) -> str:
    if row_count <= 0:
        return "missing_history"
    parsed = sorted(
        parse_date(value[:10]) for value in data_dates if parse_date(value[:10])
    )
    if not parsed:
        return "fresh"
    if parsed[0] > requested.start_date or parsed[-1] < requested.end_date:
        return "partial"
    covered_dates = {
        value for value in parsed if requested.start_date <= value <= requested.end_date
    }
    if any(
        value not in covered_dates
        for value in _date_range(requested.start_date, requested.end_date)
    ):
        return "partial"
    return "fresh"


def _coverage_payload(
    *,
    dataset: str,
    requested: PreviewDateRange,
    status: str,
    source_label: str,
    row_count: int,
    note: str | None = None,
    generated_at=None,
    data_dates: list[str] | None = None,
) -> dict[str, Any]:
    parsed_dates = (
        sorted(
            parse_date(value[:10])
            for value in (data_dates or [])
            if parse_date(value[:10])
        )
        if row_count > 0
        else []
    )
    covered_start = parsed_dates[0] if parsed_dates else None
    covered_end = parsed_dates[-1] if parsed_dates else None
    status = status if status in COVERAGE_STATUSES else "unsupported_metric"
    coverage_gap = _coverage_gap_payload(requested=requested, data_dates=parsed_dates)
    coverage_note = note or _coverage_note(
        status=status,
        source_label=source_label,
        covered_end=covered_end,
        coverage_gap=coverage_gap,
    )
    payload = {
        "dataset": dataset,
        "requested_start_date": requested.start_date.isoformat(),
        "requested_end_date": requested.end_date.isoformat(),
        "covered_start_date": covered_start.isoformat() if covered_start else None,
        "covered_end_date": covered_end.isoformat() if covered_end else None,
        "coverage_status": status,
        "history_status": "available" if row_count else "missing",
        "freshness_status": "stale"
        if status in {"stale", "source_disconnected"}
        else status,
        "last_successful_sync_at": generated_at.isoformat() if generated_at else None,
        "row_count": row_count,
        "source_label": source_label,
        "coverage_note": coverage_note,
    }
    if status == "partial" and coverage_gap:
        payload["coverage_gap"] = coverage_gap
    return payload


def _coverage_gap_payload(
    *,
    requested: PreviewDateRange,
    data_dates: list[date],
) -> dict[str, Any]:
    requested_dates = list(_date_range(requested.start_date, requested.end_date))
    covered_dates = {
        value
        for value in data_dates
        if requested.start_date <= value <= requested.end_date
    }
    missing_dates = [value for value in requested_dates if value not in covered_dates]
    if not missing_dates:
        return {}

    include_missing_dates = len(requested_dates) <= 92
    return {
        "requested_day_count": len(requested_dates),
        "covered_day_count": len(covered_dates),
        "missing_day_count": len(missing_dates),
        "missing_start_date": missing_dates[0].isoformat(),
        "missing_end_date": missing_dates[-1].isoformat(),
        "missing_dates": [value.isoformat() for value in missing_dates]
        if include_missing_dates
        else [],
        "missing_dates_truncated": not include_missing_dates,
        "has_leading_gap": requested.start_date in missing_dates,
        "has_trailing_gap": requested.end_date in missing_dates,
    }


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _coverage_note(
    *,
    status: str,
    source_label: str,
    covered_end: date | None,
    coverage_gap: Mapping[str, Any] | None = None,
) -> str:
    if status == "fresh":
        return f"{source_label} covers the requested range."
    if status == "source_disconnected":
        suffix = f" through {covered_end.isoformat()}" if covered_end else ""
        return f"{source_label} is disconnected. This preview uses stored data{suffix}."
    if status == "partial":
        if coverage_gap:
            missing_count = int(coverage_gap.get("missing_day_count") or 0)
            missing_start = str(coverage_gap.get("missing_start_date") or "")
            missing_end = str(coverage_gap.get("missing_end_date") or "")
            if missing_count and missing_start and missing_end:
                day_label = "day" if missing_count == 1 else "days"
                return (
                    f"{source_label} is missing {missing_count} requested {day_label} "
                    f"from {missing_start} through {missing_end}."
                )
        return f"{source_label} has partial retained history for the requested range."
    if status == "stale":
        return f"{source_label} is stale. This preview uses the latest stored snapshot."
    if status == "not_previously_synced":
        return f"{source_label} has not been synced for this tenant yet."
    if status == "missing_history":
        return f"{source_label} has no retained rows for the requested range."
    if status == "permission_missing":
        return f"{source_label} is blocked by missing permissions."
    return f"{source_label} cannot render this metric."


def _warnings_for_coverage(coverage: Mapping[str, Any]) -> list[str]:
    status = coverage.get("coverage_status")
    if status == "fresh":
        return []
    note = coverage.get("coverage_note")
    return [str(note)] if note else [f"Coverage status: {status}"]


def _coverage_block_reason(*, policy: str, coverage: Mapping[str, Any]) -> str | None:
    status = coverage.get("coverage_status")
    if policy == "require_full_coverage" and status in {
        "partial",
        "missing_history",
        "not_previously_synced",
        "permission_missing",
        "unsupported_metric",
    }:
        return f"coverage_policy require_full_coverage blocks coverage_status {status}."
    if policy == "block_if_stale" and status in {"stale", "source_disconnected"}:
        return f"coverage_policy block_if_stale blocks coverage_status {status}."
    return None


def _has_inactive_meta_connection(*, tenant) -> bool:
    return AirbyteConnection.all_objects.filter(
        tenant=tenant,
        provider="META",
        is_active=False,
    ).exists()


def _is_stale(generated_at) -> bool:
    ttl_seconds = max(
        int(getattr(settings, "METRICS_SNAPSHOT_STALE_TTL_SECONDS", 3600) or 3600), 1
    )
    return (timezone.now() - generated_at).total_seconds() > ttl_seconds


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])
