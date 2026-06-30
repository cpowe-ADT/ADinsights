"""Stored-data availability summaries for report target selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping

from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from analytics.models import AdAccount, RawPerformanceRecord
from content_ops.models import (
    ApprovalDecision,
    ContentDraft,
    ContentSchedule,
    OrganicPostMetricSnapshot,
    PublishedPost,
)
from integrations.clients.resolver import resolve_client_accounts
from integrations.models import (
    Client,
    ClientPlatformAccount,
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
    PlatformCredential,
)
from integrations.services.metric_registry import get_reporting_metric_source_map

from .reporting_catalog import (
    METRIC_AVAILABILITY_STATES,
    METRICS_BY_DATASET,
    PERMISSION_GATED_ORGANIC_FACEBOOK_METRICS,
    MetricDefinition,
    _metric_availability_note as _catalog_metric_availability_note,
    _metric_availability_state as _catalog_metric_availability_state,
)
from .reporting_source_health import build_reporting_source_health
from .reporting_templates import (
    SLB_MONTHLY_TEMPLATE_KEY,
    get_report_template_definition,
    get_template_export_policy,
)

REPORT_AVAILABILITY_BLOCKING_STATUSES = {
    "missing_history",
    "not_previously_synced",
    "partial",
    "permission_missing",
    "unsupported_metric",
}
METRIC_AVAILABILITY_SCHEMA_VERSION = "report_metric_availability.v1"
METRIC_AVAILABILITY_STATE_ORDER = (
    "available",
    "callable_no_data",
    "permission_gated",
    "unsupported",
)
PAID_META_ADS_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "spend": ("spend",),
    "impressions": ("impressions",),
    "reach": ("reach",),
    "clicks": ("clicks",),
    "conversions": ("conversions",),
    "conversion_value": ("conversion_value",),
    "ctr": ("clicks", "impressions"),
    "cpc": ("spend", "clicks"),
    "cpm": ("spend", "impressions"),
    "cpa": ("spend", "conversions"),
    "roas": ("conversions", "spend"),
    "frequency": ("impressions", "reach"),
}
PAID_META_ADS_DERIVED_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "ctr": ("clicks", "impressions"),
    "cpc": ("spend", "clicks"),
    "cpm": ("spend", "impressions"),
    "cpa": ("spend", "conversions"),
    "roas": ("conversions", "spend"),
    "frequency": ("impressions", "reach"),
}
PAID_META_ADS_STORED_FIELDS = {
    "spend",
    "impressions",
    "reach",
    "clicks",
    "conversions",
    "cpc",
    "cpm",
}
MANUAL_PAID_CSV_SOURCE = "manual_meta_paid_csv"
MANUAL_PAID_METRIC_COLUMNS = {
    "spend": {"spend", "amount_spent", "cost"},
    "impressions": {"impressions"},
    "reach": {"reach"},
    "clicks": {"clicks"},
    "conversions": {"conversions"},
    "cpc": {"cpc"},
    "cpm": {"cpm"},
}
ORGANIC_PAGE_METRIC_PREFIX = "page_"
ORGANIC_POST_METRICS = frozenset(
    {
        "post_activity",
        "post_reactions",
        "post_comments",
        "post_shares",
        "post_impressions",
        "post_reach",
        "post_clicks",
        "post_reactions_like",
        "post_reactions_love",
    }
)
CONTENT_OPS_SNAPSHOT_METRIC_FIELDS = {
    "content_ops_reach": "reach",
    "content_ops_engagements": "engagements",
    "content_ops_impressions": "impressions",
}
CONTENT_OPS_COUNT_METRICS = {
    "content_items_created",
    "published_posts",
    "scheduled_posts",
    "approved_items",
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


def build_report_data_availability(
    *, tenant, params: Mapping[str, Any]
) -> dict[str, Any]:
    """Return tenant-scoped stored data availability for report source selection."""

    template_key = str(params.get("template_key") or SLB_MONTHLY_TEMPLATE_KEY).strip()
    template = get_report_template_definition(template_key)
    if template is None:
        raise ReportingAvailabilityError([f"unknown report template '{template_key}'."])

    date_range = _resolve_date_range(params)
    client_id = str(params.get("client_id") or "").strip()
    account_id = str(params.get("account_id") or "").strip()
    page_id = str(params.get("page_id") or "").strip()
    _validate_scope(
        tenant=tenant, client_id=client_id, account_id=account_id, page_id=page_id
    )

    datasets = {
        "paid_meta_ads": _paid_meta_ads_availability(
            tenant=tenant,
            requested=date_range,
            client_id=client_id,
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
        if key in required
        or (key == "organic_facebook_posts" and "organic_facebook_page" in required)
    }
    blocking = [
        key
        for key, value in required_for_template.items()
        if _availability_status_blocks_export(
            key,
            str(value["coverage_status"]),
            template_key=template.template_key,
        )
    ]
    warnings = [
        key
        for key, value in required_for_template.items()
        if _availability_status_is_warning(
            key,
            str(value["coverage_status"]),
            template_key=template.template_key,
        )
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
        "warning_datasets": warnings,
        "eligible_for_report_export": not blocking,
        "recommended_next_actions": source_health["recommended_next_actions"],
    }


def _availability_status_blocks_export(
    dataset: str, status: str, *, template_key: str
) -> bool:
    if status in _warning_only_statuses(template_key=template_key, dataset=dataset):
        return False
    if dataset == "paid_meta_ads" and status == "partial":
        return False
    return status in REPORT_AVAILABILITY_BLOCKING_STATUSES


def _availability_status_is_warning(
    dataset: str, status: str, *, template_key: str
) -> bool:
    return (
        dataset == "paid_meta_ads" and status == "partial"
    ) or status in _warning_only_statuses(
        template_key=template_key,
        dataset=dataset,
    )


def _warning_only_statuses(*, template_key: str, dataset: str) -> set[str]:
    policy = get_template_export_policy(template_key)
    warning_only = policy.get("warning_only_coverage_statuses")
    if not isinstance(warning_only, Mapping):
        return set()
    statuses = warning_only.get(dataset)
    if not isinstance(statuses, list):
        return set()
    return {str(status) for status in statuses if isinstance(status, str)}


def _validate_scope(*, tenant, client_id: str, account_id: str, page_id: str) -> None:
    errors: list[str] = []
    if (
        client_id
        and not Client.all_objects.filter(id=client_id, tenant=tenant).exists()
    ):
        errors.append("client_id does not belong to the authenticated tenant.")
    if account_id and not _account_belongs_to_tenant(
        tenant=tenant, account_id=account_id
    ):
        errors.append("account_id does not belong to the authenticated tenant.")
    if (
        page_id
        and not MetaPage.all_objects.filter(tenant=tenant, page_id=page_id).exists()
    ):
        errors.append("page_id does not belong to the authenticated tenant.")
    if errors:
        raise ReportingAvailabilityError(errors)


def _paid_meta_ads_availability(
    *,
    tenant,
    requested: AvailabilityDateRange,
    client_id: str,
    account_id: str,
) -> dict[str, Any]:
    qs = RawPerformanceRecord.all_objects.filter(
        tenant=tenant,
        source__icontains="meta",
        date__gte=requested.start_date,
        date__lte=requested.end_date,
    )
    scope = _paid_meta_scope(tenant=tenant, client_id=client_id, account_id=account_id)
    if scope["aliases"] is not None:
        qs = (
            qs.filter(
                ad_account__in=_account_queryset_for_aliases(
                    tenant=tenant, aliases=scope["aliases"]
                )
            )
            if scope["aliases"]
            else qs.none()
        )
    summary = _date_summary(qs, min_field="date", max_field="date", requested=requested)
    available_accounts = _available_accounts(tenant=tenant, requested=requested)
    payload = {
        "dataset": "paid_meta_ads",
        "label": "Paid Meta Ads",
        **summary,
        "metric_availability": _paid_metric_availability(queryset=qs),
        "available_accounts": available_accounts,
        "source_label": "Stored Meta Ads rows",
    }
    diagnostic = _paid_scope_diagnostic(
        tenant=tenant,
        summary=summary,
        scope=scope,
        available_accounts=available_accounts,
    )
    if diagnostic:
        payload["scope_diagnostic"] = diagnostic
    return payload


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
    summary = _date_summary(
        qs, min_field="end_time", max_field="end_time", requested=requested
    )
    return {
        "dataset": "organic_facebook_page",
        "label": "Organic Facebook Page",
        **summary,
        "metric_availability": _organic_page_metric_availability(qs),
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
    summary = _date_summary(
        insights, min_field="end_time", max_field="end_time", requested=requested
    )
    post_dates = posts.aggregate(
        count=Count("id"), min_value=Min("created_time"), max_value=Max("created_time")
    )
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
        "metric_availability": _organic_post_metric_availability(
            insights,
            post_count=post_count,
        ),
        "post_count": post_count,
        "available_pages": _available_pages(tenant=tenant, requested=requested),
        "source_label": "Stored Facebook Page post rows",
    }


def _content_ops_availability(
    *, tenant, requested: AvailabilityDateRange
) -> dict[str, Any]:
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
    summary = _date_summary(
        snapshots, min_field="metric_date", max_field="metric_date", requested=requested
    )
    published_dates = published.aggregate(
        count=Count("id"), min_value=Min("published_at"), max_value=Max("published_at")
    )
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
        "metric_availability": _content_ops_metric_availability(
            tenant=tenant,
            requested=requested,
            snapshot_count=summary["row_count"],
            published_count=published_count,
        ),
        "published_post_count": published_count,
        "source_label": "Stored Content Ops aggregate rows",
    }


def _paid_metric_availability(*, queryset) -> dict[str, Any]:
    source_counts = _paid_source_counts(queryset)
    return _metric_availability_payload(
        definitions=_metric_definitions_for_dataset("paid_meta_ads"),
        source_counts=source_counts,
        source_key_map=PAID_META_ADS_SOURCE_KEYS,
        required_source_key_map=PAID_META_ADS_DERIVED_REQUIREMENTS,
    )


def _paid_source_counts(queryset) -> dict[str, int]:
    counts = {field: 0 for field in PAID_META_ADS_STORED_FIELDS}
    for raw_payload in queryset.values_list("raw_payload", flat=True):
        supplied_columns = _manual_paid_supplied_columns(raw_payload)
        if supplied_columns is None:
            for field in counts:
                counts[field] += 1
            continue
        for field, aliases in MANUAL_PAID_METRIC_COLUMNS.items():
            if supplied_columns & aliases:
                counts[field] += 1
    return counts


def _manual_paid_supplied_columns(raw_payload: object) -> set[str] | None:
    if not isinstance(raw_payload, Mapping):
        return None
    if raw_payload.get("source") != MANUAL_PAID_CSV_SOURCE:
        return None
    metric_columns = raw_payload.get("metric_columns")
    if not isinstance(metric_columns, (list, tuple, set)):
        return None
    return {str(column).strip().lower() for column in metric_columns}


def _organic_page_metric_availability(queryset) -> dict[str, Any]:
    source_map = get_reporting_metric_source_map(
        "organic_facebook_page",
        level=MetaMetricRegistry.LEVEL_PAGE,
    )
    source_counts = _metric_value_counts_by_source(queryset)
    return _metric_availability_payload(
        definitions=[
            definition
            for definition in _metric_definitions_for_dataset("organic_facebook_page")
            if definition.key.startswith(ORGANIC_PAGE_METRIC_PREFIX)
        ],
        source_counts=source_counts,
        source_key_map=source_map,
        permission_gated_exact_counts={
            key: source_counts.get(key, 0)
            for key in PERMISSION_GATED_ORGANIC_FACEBOOK_METRICS
        },
    )


def _organic_post_metric_availability(queryset, *, post_count: int) -> dict[str, Any]:
    source_map = {
        **get_reporting_metric_source_map(
            "organic_facebook_page",
            level=MetaMetricRegistry.LEVEL_POST,
        ),
        "post_activity": ("post_activity",),
    }
    source_counts = {
        **_metric_value_counts_by_source(queryset),
        "post_activity": int(post_count or 0),
    }
    return _metric_availability_payload(
        definitions=[
            definition
            for definition in _metric_definitions_for_dataset("organic_facebook_page")
            if definition.key in ORGANIC_POST_METRICS
        ],
        source_counts=source_counts,
        source_key_map=source_map,
        permission_gated_exact_counts={
            key: source_counts.get(key, 0)
            for key in PERMISSION_GATED_ORGANIC_FACEBOOK_METRICS
        },
    )


def _content_ops_metric_availability(
    *,
    tenant,
    requested: AvailabilityDateRange,
    snapshot_count: int,
    published_count: int,
) -> dict[str, Any]:
    draft_count = ContentDraft.all_objects.filter(
        tenant=tenant,
        created_at__date__gte=requested.start_date,
        created_at__date__lte=requested.end_date,
    ).count()
    schedule_count = ContentSchedule.all_objects.filter(
        tenant=tenant,
        scheduled_at__date__gte=requested.start_date,
        scheduled_at__date__lte=requested.end_date,
    ).count()
    approved_count = ApprovalDecision.all_objects.filter(
        tenant=tenant,
        decision=ApprovalDecision.DECISION_APPROVED,
        decided_at__date__gte=requested.start_date,
        decided_at__date__lte=requested.end_date,
    ).count()
    source_counts = {
        "content_items_created": int(draft_count or 0),
        "published_posts": int(published_count or 0),
        "scheduled_posts": int(schedule_count or 0),
        "approved_items": int(approved_count or 0),
    }
    for metric, field in CONTENT_OPS_SNAPSHOT_METRIC_FIELDS.items():
        source_counts[field] = int(snapshot_count or 0)
        source_counts[metric] = int(snapshot_count or 0)
    source_map = {
        "content_items_created": ("content_items_created",),
        "published_posts": ("published_posts",),
        "scheduled_posts": ("scheduled_posts",),
        "approved_items": ("approved_items",),
        **{
            metric: (field,)
            for metric, field in CONTENT_OPS_SNAPSHOT_METRIC_FIELDS.items()
        },
    }
    return _metric_availability_payload(
        definitions=_metric_definitions_for_dataset("content_ops"),
        source_counts=source_counts,
        source_key_map=source_map,
    )


def _metric_value_counts_by_source(queryset) -> dict[str, int]:
    rows = (
        queryset.values("metric_key")
        .annotate(
            row_count=Count(
                "id",
                filter=Q(value_num__isnull=False) | Q(value_json__isnull=False),
            )
        )
        .order_by("metric_key")
    )
    return {str(row["metric_key"]): int(row["row_count"] or 0) for row in rows}


def _metric_definitions_for_dataset(dataset: str) -> list[MetricDefinition]:
    definitions = [
        definition
        for (definition_dataset, _metric), definition in METRICS_BY_DATASET.items()
        if definition_dataset == dataset
    ]
    return sorted(definitions, key=lambda item: item.key)


def _metric_availability_payload(
    *,
    definitions: list[MetricDefinition],
    source_counts: Mapping[str, int],
    source_key_map: Mapping[str, tuple[str, ...]],
    required_source_key_map: Mapping[str, tuple[str, ...]] | None = None,
    permission_gated_exact_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    entries = [
        _metric_availability_entry(
            definition=definition,
            source_counts=source_counts,
            source_key_map=source_key_map,
            required_source_key_map=required_source_key_map or {},
            permission_gated_exact_counts=permission_gated_exact_counts or {},
        )
        for definition in definitions
    ]
    summary = {state: 0 for state in METRIC_AVAILABILITY_STATE_ORDER}
    for entry in entries:
        state = str(entry["availability_state"])
        summary[state] = summary.get(state, 0) + 1

    return {
        "schema_version": METRIC_AVAILABILITY_SCHEMA_VERSION,
        "states": [
            state
            for state in METRIC_AVAILABILITY_STATE_ORDER
            if state in METRIC_AVAILABILITY_STATES
        ],
        "summary": summary,
        "metrics": entries,
    }


def _metric_availability_entry(
    *,
    definition: MetricDefinition,
    source_counts: Mapping[str, int],
    source_key_map: Mapping[str, tuple[str, ...]],
    required_source_key_map: Mapping[str, tuple[str, ...]],
    permission_gated_exact_counts: Mapping[str, int],
) -> dict[str, Any]:
    source_keys = tuple(
        dict.fromkeys((definition.key, *source_key_map.get(definition.key, ())))
    )
    catalog_state = _catalog_metric_availability_state(definition)
    source_row_count = _source_row_count(
        source_counts=source_counts,
        source_keys=source_keys,
        required_source_keys=required_source_key_map.get(definition.key, ()),
    )

    # Replacement source rows such as page_media_view are useful diagnostics, but
    # they do not prove that permission-gated reach/impression product metrics
    # are available. Only an explicit stored product-metric row can do that.
    if definition.key in permission_gated_exact_counts:
        exact_count = int(permission_gated_exact_counts.get(definition.key) or 0)
        state = "available" if exact_count > 0 else "permission_gated"
        source_row_count = exact_count
    elif catalog_state == "unsupported":
        state = "unsupported"
    elif source_row_count > 0:
        state = "available"
    elif catalog_state == "permission_gated":
        state = "permission_gated"
    else:
        state = "callable_no_data"

    return {
        "key": definition.key,
        "catalog_dataset": definition.dataset,
        "availability_state": state,
        "availability_note": _runtime_metric_availability_note(
            definition=definition,
            state=state,
            catalog_state=catalog_state,
        ),
        "row_count": source_row_count,
        "source_metric_keys": list(source_keys),
        "supported": state not in {"permission_gated", "unsupported"},
    }


def _source_row_count(
    *,
    source_counts: Mapping[str, int],
    source_keys: tuple[str, ...],
    required_source_keys: tuple[str, ...] = (),
) -> int:
    if required_source_keys:
        return min(int(source_counts.get(key, 0) or 0) for key in required_source_keys)
    if not source_keys:
        return 0
    return max(int(source_counts.get(key, 0) or 0) for key in source_keys)


def _runtime_metric_availability_note(
    *,
    definition: MetricDefinition,
    state: str,
    catalog_state: str,
) -> str:
    if state == "available" and catalog_state == "permission_gated":
        return (
            "Stored product-metric rows exist for the selected scope; live Meta "
            "API access may still require approval."
        )
    if state == "available":
        return "Stored report-ready rows exist for the selected tenant/date scope."
    if state == "callable_no_data":
        return (
            "Metric is supported by the current reporting path, but no retained "
            "rows exist for the selected tenant/date scope. Keep values null, not zero."
        )
    return _catalog_metric_availability_note(definition)


def _paid_meta_scope(*, tenant, client_id: str, account_id: str) -> dict[str, Any]:
    if not client_id and not account_id:
        return {
            "aliases": None,
            "account_id": "",
            "client_id": "",
            "linked_meta_ad_account_ids": [],
            "reason": None,
        }

    account_aliases = _account_aliases(account_id) if account_id else None
    linked_meta_ids: list[str] = []
    client_aliases: set[str] | None = None
    reason: str | None = None
    if client_id:
        try:
            bundle = resolve_client_accounts(
                str(tenant.id),
                client_id,
                platforms={ClientPlatformAccount.PLATFORM_META_ADS},
            )
        except (Client.DoesNotExist, ValueError):
            client_aliases = set()
            reason = "client_not_found"
        else:
            linked_meta_ids = list(bundle.meta_ad_account_ids)
            client_aliases = set()
            for linked_account_id in linked_meta_ids:
                client_aliases.update(_account_aliases(str(linked_account_id)))
            if not client_aliases:
                reason = "client_has_no_meta_ad_accounts"

    aliases = account_aliases
    if client_aliases is not None and account_aliases is not None:
        aliases = client_aliases & account_aliases
        if not aliases and reason is None:
            reason = "requested_account_not_in_client"
    elif client_aliases is not None:
        aliases = client_aliases

    return {
        "aliases": aliases,
        "account_id": account_id,
        "client_id": client_id,
        "linked_meta_ad_account_ids": sorted(linked_meta_ids),
        "reason": reason,
    }


def _paid_scope_diagnostic(
    *,
    tenant,
    summary: Mapping[str, Any],
    scope: Mapping[str, Any],
    available_accounts: list[dict[str, Any]],
) -> dict[str, Any]:
    if scope["aliases"] is None or int(summary["row_count"] or 0) > 0:
        return {}

    account_id = str(scope["account_id"] or "")
    client_id = str(scope["client_id"] or "")
    reason = scope.get("reason")
    diagnostic = {
        "code": str(reason or "scoped_paid_rows_missing"),
        "message": "The selected paid Meta scope has no retained rows for the requested date range.",
        "required_action": "Reconnect Meta/Facebook, select the intended ad account, then run paid backfill.",
        "available_account_count": len(available_accounts),
    }
    linked_meta_ids = scope.get("linked_meta_ad_account_ids")
    if client_id:
        diagnostic["client_id"] = client_id
        diagnostic["linked_meta_ad_account_ids"] = list(linked_meta_ids or [])
    if account_id:
        diagnostic["requested_account"] = _account_payload(
            tenant=tenant, account_id=account_id
        )
        diagnostic["credential_status"] = _meta_credential_status_payload(
            tenant=tenant,
            aliases=_account_aliases(account_id),
        )

    if reason == "client_has_no_meta_ad_accounts":
        diagnostic["message"] = "The selected client has no linked Meta ad accounts."
        diagnostic["required_action"] = (
            "Link the client to the intended Meta ad account before preview or export."
        )
    elif reason == "requested_account_not_in_client":
        diagnostic["message"] = (
            "The requested Meta ad account is not linked to the selected client."
        )
        diagnostic["required_action"] = (
            "Select a client/account pair that references the same tenant-owned Meta ad account."
        )
    elif account_id and available_accounts:
        diagnostic["code"] = "requested_account_no_rows"
        diagnostic["message"] = (
            "The requested paid Meta account has no retained rows for the selected range; "
            "other tenant Meta accounts do have retained rows."
        )
    elif client_id and available_accounts:
        diagnostic["code"] = "client_scope_no_rows"
        diagnostic["message"] = (
            "The selected client-linked Meta ad accounts have no retained rows for the selected range; "
            "other tenant Meta accounts do have retained rows."
        )
    return diagnostic


def _account_payload(*, tenant, account_id: str) -> dict[str, Any]:
    account = (
        _account_queryset(tenant=tenant, account_id=account_id)
        .order_by("name", "external_id")
        .first()
    )
    if account is None:
        return {"account_id": account_id}
    return {
        "id": str(account.id),
        "account_id": account.account_id or account.external_id,
        "external_id": account.external_id,
        "name": account.name,
        "currency": account.currency,
    }


def _meta_credential_status_payload(*, tenant, aliases: set[str]) -> dict[str, Any]:
    credential = (
        PlatformCredential.all_objects.filter(
            tenant=tenant,
            provider=PlatformCredential.META,
            account_id__in=aliases,
        )
        .order_by("account_id")
        .first()
    )
    if credential is None:
        return {
            "status": "missing",
            "provider": PlatformCredential.META,
            "matched_account_id": None,
            "token_status": None,
            "last_validated_at": None,
        }
    return {
        "status": "present",
        "provider": credential.provider,
        "matched_account_id": credential.account_id,
        "token_status": credential.token_status,
        "last_validated_at": _iso_datetime(credential.last_validated_at),
    }


def _available_accounts(
    *, tenant, requested: AvailabilityDateRange
) -> list[dict[str, Any]]:
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


def _available_pages(
    *, tenant, requested: AvailabilityDateRange
) -> list[dict[str, Any]]:
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
    aggregate = queryset.aggregate(
        row_count=Count("id"), min_value=Min(min_field), max_value=Max(max_field)
    )
    row_count = int(aggregate["row_count"] or 0)
    min_date = _as_date(aggregate["min_value"])
    max_date = _as_date(aggregate["max_value"])
    data_dates = _distinct_dates(queryset, min_field)
    coverage_gap = _coverage_gap_payload(requested=requested, data_dates=data_dates)
    status = _coverage_status(
        row_count=row_count,
        min_date=min_date,
        max_date=max_date,
        requested=requested,
    )
    if status == "fresh" and coverage_gap:
        status = "partial"
    summary = {
        "row_count": row_count,
        "min_date": min_date.isoformat() if min_date else None,
        "max_date": max_date.isoformat() if max_date else None,
        "coverage_status": status,
        "coverage_note": _coverage_note(
            status=status,
            requested=requested,
            min_date=min_date,
            max_date=max_date,
            coverage_gap=coverage_gap,
        ),
    }
    if status == "partial" and coverage_gap:
        summary["coverage_gap"] = coverage_gap
    return summary


def _distinct_dates(queryset, field: str) -> list[date]:
    dates: set[date] = set()
    for value in queryset.values_list(field, flat=True).distinct():
        parsed = _as_date(value)
        if parsed is not None:
            dates.add(parsed)
    return sorted(dates)


def _coverage_gap_payload(
    *,
    requested: AvailabilityDateRange,
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
    coverage_gap: Mapping[str, Any] | None = None,
) -> str:
    if status == "fresh":
        return "Stored rows cover the requested report range."
    if status == "partial" and coverage_gap:
        missing_count = int(coverage_gap.get("missing_day_count") or 0)
        missing_start = str(coverage_gap.get("missing_start_date") or "")
        missing_end = str(coverage_gap.get("missing_end_date") or "")
        if missing_count and missing_start and missing_end:
            day_label = "day" if missing_count == 1 else "days"
            return (
                f"Stored rows are missing {missing_count} requested {day_label} "
                f"from {missing_start} through {missing_end}."
            )
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
            raise ReportingAvailabilityError(
                ["start_date and end_date must be ISO dates."]
            )
        return _bounded_range(start=start, end=end, label=label or "custom")
    if label == "last_7d":
        return _bounded_range(start=today - timedelta(days=6), end=today, label=label)
    if label in {"last_28d", "last_30d"}:
        days = 27 if label == "last_28d" else 29
        return _bounded_range(
            start=today - timedelta(days=days), end=today, label=label
        )
    if label == "last_90d":
        return _bounded_range(start=today - timedelta(days=89), end=today, label=label)
    if label in {"mtd", "this_month"}:
        return _bounded_range(start=today.replace(day=1), end=today, label=label)
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    return _bounded_range(
        start=last_month_end.replace(day=1),
        end=last_month_end,
        label=label or "last_month",
    )


def _bounded_range(*, start: date, end: date, label: str) -> AvailabilityDateRange:
    if end < start:
        raise ReportingAvailabilityError(["end_date must be on or after start_date."])
    if (end - start).days > 366:
        raise ReportingAvailabilityError(["date range cannot exceed 366 days."])
    return AvailabilityDateRange(start_date=start, end_date=end, label=label)


def _account_belongs_to_tenant(*, tenant, account_id: str) -> bool:
    return _account_queryset(tenant=tenant, account_id=account_id).exists()


def _account_queryset(*, tenant, account_id: str):
    return _account_queryset_for_aliases(
        tenant=tenant, aliases=_account_aliases(account_id)
    )


def _account_queryset_for_aliases(*, tenant, aliases: set[str]):
    return AdAccount.all_objects.filter(tenant=tenant).filter(
        models_any_account_alias(aliases)
    )


def _account_aliases(account_id: str) -> set[str]:
    aliases = {account_id}
    if account_id.startswith("act_") and account_id[4:]:
        aliases.add(account_id[4:])
    elif account_id.isdigit():
        aliases.add(f"act_{account_id}")
    return aliases


def models_any_account_alias(aliases: set[str]):
    from django.db.models import Q

    return (
        Q(external_id__in=aliases)
        | Q(account_id__in=aliases)
        | Q(id__in=[value for value in aliases if _is_uuid(value)])
    )


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
