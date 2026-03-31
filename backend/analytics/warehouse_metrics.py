"""Warehouse-backed combined metrics helpers for truthful Meta dashboard queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any, Mapping, Sequence

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_date

from adapters.warehouse import (
    WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
    WAREHOUSE_SNAPSHOT_STATUS_KEY,
    WarehouseSnapshotUnavailable,
)
from analytics.models import TenantMetricsSnapshot

UNKNOWN_PARISH_LABELS = {"", "unknown", "unk", "n/a"}

CHANNEL_PLATFORM_MAP = {
    "meta": "meta_ads",
    "meta_ads": "meta_ads",
    "google": "google_ads",
    "google_ads": "google_ads",
    "linkedin": "linkedin",
    "tiktok": "tiktok",
}

PLATFORM_LABELS = {
    "meta_ads": "Meta Ads",
    "google_ads": "Google Ads",
    "linkedin": "LinkedIn",
    "tiktok": "TikTok",
}


@dataclass(frozen=True)
class WarehouseCombinedFilters:
    start_date: date | None = None
    end_date: date | None = None
    account_ids: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    parishes: tuple[str, ...] = ()
    campaign_search: str | None = None

    @classmethod
    def from_options(cls, options: Mapping[str, Any] | None) -> "WarehouseCombinedFilters":
        if not options:
            return cls()
        return cls(
            start_date=_parse_date(options.get("start_date")),
            end_date=_parse_date(options.get("end_date")),
            account_ids=_normalize_account_ids(options.get("account_id")),
            channels=_normalize_channels(options.get("channels")),
            parishes=_normalize_parishes(options.get("parish")),
            campaign_search=_normalize_search(options.get("campaign_search")),
        )

    def without_search_and_parish(self) -> "WarehouseCombinedFilters":
        return WarehouseCombinedFilters(
            start_date=self.start_date,
            end_date=self.end_date,
            account_ids=self.account_ids,
            channels=self.channels,
        )

    @property
    def has_refinement_filters(self) -> bool:
        return bool(self.parishes or self.campaign_search)


@dataclass(frozen=True)
class DatasetCoverage:
    start_date: date | None
    end_date: date | None
    row_count: int


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_date(value)
    return None


def _normalize_search(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    values: Sequence[Any]
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, str)):
        values = value
    else:
        return ()
    normalized = tuple(
        item.strip()
        for item in values
        if isinstance(item, str) and item.strip()
    )
    return normalized


def _account_aliases(value: str) -> set[str]:
    normalized = value.strip()
    if not normalized:
        return set()
    aliases = {normalized}
    if normalized.startswith("act_"):
        numeric = normalized[4:]
        if numeric:
            aliases.add(numeric)
    elif normalized.isdigit():
        aliases.add(f"act_{normalized}")
    return aliases


def _normalize_account_ids(value: Any) -> tuple[str, ...]:
    aliases = {
        alias
        for raw_value in _normalize_sequence(value)
        for alias in _account_aliases(raw_value)
    }
    return tuple(sorted(aliases))


def _normalize_channels(value: Any) -> tuple[str, ...]:
    platforms = []
    for raw_value in _normalize_sequence(value):
        platform = CHANNEL_PLATFORM_MAP.get(raw_value.strip().lower(), raw_value.strip().lower())
        if platform:
            platforms.append(platform)
    return tuple(dict.fromkeys(platforms))


def _normalize_parishes(value: Any) -> tuple[str, ...]:
    return _normalize_sequence(value)


@lru_cache(maxsize=32)
def _relation_has_column(table_name: str, column_name: str) -> bool:
    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = {row[1] for row in cursor.fetchall()}
            return column_name in columns

        cursor.execute(
            """
            select 1
            from information_schema.columns
            where table_schema = current_schema()
              and table_name = %s
              and column_name = %s
            """,
            [table_name, column_name],
        )
        return cursor.fetchone() is not None


@lru_cache(maxsize=16)
def _relation_exists(table_name: str) -> bool:
    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(
                "select 1 from sqlite_master where type in ('table', 'view') and name = ?",
                [table_name],
            )
            return cursor.fetchone() is not None

        cursor.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = current_schema()
              and table_name = %s
            union all
            select 1
            from information_schema.views
            where table_schema = current_schema()
              and table_name = %s
            """,
            [table_name, table_name],
        )
        return cursor.fetchone() is not None


def _fetch_rows(sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_one(sql: str, params: Sequence[Any]) -> dict[str, Any] | None:
    rows = _fetch_rows(sql, params)
    return rows[0] if rows else None


def _append_clause(
    clauses: list[str],
    params: list[Any],
    *,
    column: str,
    operator: str,
    values: Sequence[Any],
) -> None:
    if not values:
        return
    placeholders = ", ".join(["%s"] * len(values))
    clauses.append(f"{column} {operator} ({placeholders})")
    params.extend(values)


def _build_campaign_where(
    *,
    alias: str,
    tenant_id: str,
    filters: WarehouseCombinedFilters,
    include_parish: bool,
    include_search: bool,
) -> tuple[list[str], list[Any]]:
    clauses = [f"{alias}.tenant_id::text = %s"]
    params: list[Any] = [tenant_id]

    if filters.start_date:
        clauses.append(f"{alias}.date_day >= %s")
        params.append(filters.start_date)
    if filters.end_date:
        clauses.append(f"{alias}.date_day <= %s")
        params.append(filters.end_date)
    _append_clause(
        clauses,
        params,
        column=f"{alias}.source_platform",
        operator="in",
        values=filters.channels,
    )
    _append_clause(
        clauses,
        params,
        column=f"{alias}.ad_account_id",
        operator="in",
        values=filters.account_ids,
    )
    if include_parish and filters.parishes:
        _append_clause(
            clauses,
            params,
            column=f"coalesce({alias}.parish_name, 'Unknown')",
            operator="in",
            values=filters.parishes,
        )
    if include_search and filters.campaign_search:
        clauses.append(f"lower(coalesce({alias}.campaign_name, '')) like %s")
        params.append(f"%{filters.campaign_search.lower()}%")
    return clauses, params


def _build_creative_where(
    *,
    alias: str,
    tenant_id: str,
    filters: WarehouseCombinedFilters,
) -> tuple[list[str], list[Any]]:
    clauses, params = _build_campaign_where(
        alias=alias,
        tenant_id=tenant_id,
        filters=filters,
        include_parish=True,
        include_search=False,
    )
    if filters.campaign_search:
        query = f"%{filters.campaign_search.lower()}%"
        clauses.append(
            "("
            f"lower(coalesce({alias}.campaign_name, '')) like %s or "
            f"lower(coalesce({alias}.ad_name, '')) like %s"
            ")"
        )
        params.extend([query, query])
    return clauses, params


def _build_fact_where(
    *,
    alias: str,
    tenant_id: str,
    filters: WarehouseCombinedFilters,
    include_parish: bool,
    include_search: bool,
) -> tuple[list[str], list[Any]]:
    clauses = [f"{alias}.tenant_id::text = %s", f"{alias}.source_platform = %s"]
    params: list[Any] = [tenant_id, "meta_ads"]

    if filters.start_date:
        clauses.append(f"{alias}.date_day >= %s")
        params.append(filters.start_date)
    if filters.end_date:
        clauses.append(f"{alias}.date_day <= %s")
        params.append(filters.end_date)
    if filters.channels and "meta_ads" not in filters.channels:
        clauses.append("1 = 0")
        return clauses, params
    _append_clause(
        clauses,
        params,
        column=f"{alias}.ad_account_id",
        operator="in",
        values=filters.account_ids,
    )
    if include_parish and filters.parishes:
        _append_clause(
            clauses,
            params,
            column=f"coalesce({alias}.parish_name, 'Unknown')",
            operator="in",
            values=filters.parishes,
        )
    if include_search and filters.campaign_search:
        clauses.append(f"lower(coalesce({alias}.campaign_name, '')) like %s")
        params.append(f"%{filters.campaign_search.lower()}%")
    return clauses, params


def _platform_label(value: Any) -> str:
    if not isinstance(value, str):
        return "Unknown"
    return PLATFORM_LABELS.get(value, value.replace("_", " ").title())


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_date_string(value: Any) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value
    return None


def _extract_known_parishes(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    parishes: list[str] = []
    for row in rows:
        parish = str(row.get("parish") or "").strip()
        if parish and parish.lower() not in UNKNOWN_PARISH_LABELS:
            parishes.append(parish)
    return parishes


def _derive_campaign_summary(summary: dict[str, Any]) -> dict[str, Any]:
    total_spend = _coerce_float(summary.get("totalSpend"))
    total_impressions = _coerce_int(summary.get("totalImpressions"))
    total_clicks = _coerce_int(summary.get("totalClicks"))
    total_conversions = _coerce_int(summary.get("totalConversions"))
    total_reach = _coerce_int(summary.get("totalReach"))
    summary.setdefault("ctr", total_clicks / total_impressions if total_impressions else 0.0)
    summary.setdefault("cpc", total_spend / total_clicks if total_clicks else 0.0)
    summary.setdefault(
        "cpm",
        (total_spend / total_impressions) * 1000 if total_impressions else 0.0,
    )
    summary.setdefault("cpa", total_spend / total_conversions if total_conversions else 0.0)
    summary.setdefault(
        "frequency",
        total_impressions / total_reach if total_reach else 0.0,
    )
    return summary


def _build_availability(
    *,
    base_coverage: DatasetCoverage,
    campaign_rows: Sequence[Mapping[str, Any]],
    creative_rows: Sequence[Mapping[str, Any]],
    budget_rows: Sequence[Mapping[str, Any]],
    parish_rows: Sequence[Mapping[str, Any]],
    filters: WarehouseCombinedFilters,
) -> dict[str, dict[str, Any]]:
    has_base_activity = base_coverage.row_count > 0
    empty_reason = (
        "no_matching_filters" if has_base_activity and filters.has_refinement_filters else "no_recent_data"
    )
    campaign_available = bool(campaign_rows)
    creative_available = bool(creative_rows)
    budget_available = bool(budget_rows)
    known_parishes = _extract_known_parishes(parish_rows)

    parish_status = {"status": "available", "reason": None}
    if not parish_rows:
        parish_status = {
            "status": "empty",
            "reason": empty_reason,
        }
    elif not known_parishes:
        parish_status = {
            "status": "unavailable",
            "reason": "geo_unavailable",
        }

    budget_reason = None
    budget_status = "available" if budget_available else "empty"
    if not budget_available:
        if campaign_available:
            budget_status = "unavailable"
            budget_reason = "budget_unavailable"
        else:
            budget_reason = empty_reason

    return {
        "campaign": {
            "status": "available" if campaign_available else "empty",
            "reason": None if campaign_available else empty_reason,
        },
        "creative": {
            "status": "available" if creative_available else "empty",
            "reason": None if creative_available else empty_reason,
        },
        "budget": {
            "status": budget_status,
            "reason": budget_reason,
        },
        "parish_map": parish_status,
    }


def _derive_coverage_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    coverage = payload.get("coverage")
    if isinstance(coverage, Mapping):
        start_date = coverage.get("startDate")
        end_date = coverage.get("endDate")
        if start_date or end_date:
            return {"startDate": start_date, "endDate": end_date}

    campaign = payload.get("campaign")
    start_candidates: list[str] = []
    end_candidates: list[str] = []
    if isinstance(campaign, Mapping):
        trend = campaign.get("trend")
        if isinstance(trend, Sequence):
            for point in trend:
                if isinstance(point, Mapping):
                    value = _normalize_date_string(point.get("date"))
                    if value:
                        start_candidates.append(value)
                        end_candidates.append(value)
        rows = campaign.get("rows")
        if isinstance(rows, Sequence):
            for row in rows:
                if isinstance(row, Mapping):
                    start_value = _normalize_date_string(row.get("startDate"))
                    end_value = _normalize_date_string(row.get("endDate"))
                    if start_value:
                        start_candidates.append(start_value)
                    if end_value:
                        end_candidates.append(end_value)

    return {
        "startDate": min(start_candidates) if start_candidates else None,
        "endDate": max(end_candidates) if end_candidates else None,
    }


def enrich_combined_payload_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Add coverage, availability, and derived KPI fields to a combined payload."""

    combined = dict(payload)
    campaign = dict(combined.get("campaign") or {})
    summary = dict(campaign.get("summary") or {})
    if summary:
        campaign["summary"] = _derive_campaign_summary(summary)
    combined["campaign"] = campaign
    combined["coverage"] = _derive_coverage_from_payload(combined)

    if "availability" not in combined:
        campaign_rows = list(campaign.get("rows") or [])
        creative_rows = list(combined.get("creative") or [])
        budget_rows = list(combined.get("budget") or [])
        parish_rows = list(combined.get("parish") or [])
        has_data = bool(campaign_rows or creative_rows or budget_rows or parish_rows)
        empty_reason = "no_recent_data"
        combined["availability"] = {
            "campaign": {
                "status": "available" if campaign_rows else "empty",
                "reason": None if campaign_rows else empty_reason,
            },
            "creative": {
                "status": "available" if creative_rows else "empty",
                "reason": None if creative_rows else empty_reason,
            },
            "budget": {
                "status": "available" if budget_rows else ("unavailable" if has_data else "empty"),
                "reason": None
                if budget_rows
                else ("budget_unavailable" if has_data else empty_reason),
            },
            "parish_map": {
                "status": "available"
                if _extract_known_parishes(parish_rows)
                else ("unavailable" if parish_rows else "empty"),
                "reason": None
                if _extract_known_parishes(parish_rows)
                else ("geo_unavailable" if parish_rows else empty_reason),
            },
        }

    return combined


def _ensure_live_warehouse_snapshot(*, tenant, ttl_seconds: int) -> str:
    snapshot = TenantMetricsSnapshot.latest_for(tenant=tenant, source="warehouse")
    if not snapshot or not snapshot.payload:
        raise WarehouseSnapshotUnavailable()

    stale_ttl_seconds = max(
        int(getattr(settings, "METRICS_SNAPSHOT_STALE_TTL_SECONDS", ttl_seconds) or ttl_seconds),
        1,
    )
    if (timezone.now() - snapshot.generated_at).total_seconds() > stale_ttl_seconds:
        raise WarehouseSnapshotUnavailable()

    payload = dict(snapshot.payload)
    snapshot_status = payload.get(WAREHOUSE_SNAPSHOT_STATUS_KEY)
    if snapshot_status and snapshot_status != WAREHOUSE_SNAPSHOT_STATUS_FETCHED:
        raise WarehouseSnapshotUnavailable()

    return snapshot.generated_at.isoformat()


def _fetch_coverage(
    *,
    tenant_id: str,
    filters: WarehouseCombinedFilters,
) -> DatasetCoverage:
    where_clauses, params = _build_campaign_where(
        alias="c",
        tenant_id=tenant_id,
        filters=filters,
        include_parish=True,
        include_search=True,
    )
    sql = f"""
        select
            min(c.date_day) as start_date,
            max(c.date_day) as end_date,
            count(*) as row_count
        from vw_campaign_daily c
        where {" and ".join(where_clauses)}
    """
    row = _fetch_one(sql, params) or {}
    return DatasetCoverage(
        start_date=row.get("start_date"),
        end_date=row.get("end_date"),
        row_count=_coerce_int(row.get("row_count")),
    )


def _fetch_campaign_payload(
    *,
    tenant_id: str,
    filters: WarehouseCombinedFilters,
) -> dict[str, Any]:
    has_reach = _relation_has_column("vw_campaign_daily", "reach")
    reach_sum_expr = "coalesce(sum(c.reach), 0)" if has_reach else "0"
    frequency_expr = (
        f"case when {reach_sum_expr} = 0 then 0 else coalesce(sum(c.impressions), 0) / {reach_sum_expr} end"
    )

    where_clauses, params = _build_campaign_where(
        alias="c",
        tenant_id=tenant_id,
        filters=filters,
        include_parish=True,
        include_search=True,
    )
    where_sql = " and ".join(where_clauses)

    summary_sql = f"""
        select
            'USD' as currency,
            coalesce(sum(c.spend), 0) as total_spend,
            coalesce(sum(c.impressions), 0) as total_impressions,
            coalesce(sum(c.clicks), 0) as total_clicks,
            coalesce(sum(c.conversions), 0) as total_conversions,
            {reach_sum_expr} as total_reach,
            case when coalesce(sum(c.spend), 0) = 0 then 0 else coalesce(sum(c.conversions), 0) / sum(c.spend) end as average_roas,
            case when coalesce(sum(c.impressions), 0) = 0 then 0 else coalesce(sum(c.clicks), 0) / sum(c.impressions) end as ctr,
            case when coalesce(sum(c.clicks), 0) = 0 then 0 else coalesce(sum(c.spend), 0) / sum(c.clicks) end as cpc,
            case when coalesce(sum(c.impressions), 0) = 0 then 0 else (coalesce(sum(c.spend), 0) / sum(c.impressions)) * 1000 end as cpm,
            case when coalesce(sum(c.conversions), 0) = 0 then 0 else coalesce(sum(c.spend), 0) / sum(c.conversions) end as cpa,
            {frequency_expr} as frequency
        from vw_campaign_daily c
        where {where_sql}
    """
    summary_row = _fetch_one(summary_sql, params) or {}
    summary = {
        "currency": summary_row.get("currency") or "USD",
        "totalSpend": _coerce_float(summary_row.get("total_spend")),
        "totalImpressions": _coerce_int(summary_row.get("total_impressions")),
        "totalClicks": _coerce_int(summary_row.get("total_clicks")),
        "totalConversions": _coerce_int(summary_row.get("total_conversions")),
        "totalReach": _coerce_int(summary_row.get("total_reach")),
        "averageRoas": _coerce_float(summary_row.get("average_roas")),
        "ctr": _coerce_float(summary_row.get("ctr")),
        "cpc": _coerce_float(summary_row.get("cpc")),
        "cpm": _coerce_float(summary_row.get("cpm")),
        "cpa": _coerce_float(summary_row.get("cpa")),
        "frequency": _coerce_float(summary_row.get("frequency")),
    }

    trend_sql = f"""
        select
            c.date_day as date,
            c.ad_account_id as ad_account_id,
            coalesce(sum(c.spend), 0) as spend,
            coalesce(sum(c.impressions), 0) as impressions,
            coalesce(sum(c.clicks), 0) as clicks,
            coalesce(sum(c.conversions), 0) as conversions,
            {reach_sum_expr} as reach
        from vw_campaign_daily c
        where {where_sql}
        group by c.date_day, c.ad_account_id
        order by c.date_day asc, c.ad_account_id asc
    """
    trend_rows = [
        {
            "date": _normalize_date_string(row.get("date")),
            "adAccountId": row.get("ad_account_id") or "",
            "spend": _coerce_float(row.get("spend")),
            "impressions": _coerce_int(row.get("impressions")),
            "clicks": _coerce_int(row.get("clicks")),
            "conversions": _coerce_int(row.get("conversions")),
            "reach": _coerce_int(row.get("reach")),
        }
        for row in _fetch_rows(trend_sql, params)
    ]

    rows_sql = f"""
        select
            c.campaign_id as id,
            c.ad_account_id as ad_account_id,
            max(c.campaign_name) as name,
            max(c.source_platform) as source_platform,
            coalesce(max(c.parish_name), 'Unknown') as parish,
            coalesce(sum(c.spend), 0) as spend,
            coalesce(sum(c.impressions), 0) as impressions,
            coalesce(sum(c.clicks), 0) as clicks,
            coalesce(sum(c.conversions), 0) as conversions,
            {reach_sum_expr} as reach,
            min(c.date_day) as start_date,
            max(c.date_day) as end_date
        from vw_campaign_daily c
        where {where_sql}
        group by c.campaign_id, c.ad_account_id
        order by spend desc, name asc
        limit 100
    """
    rows = []
    for row in _fetch_rows(rows_sql, params):
        spend = _coerce_float(row.get("spend"))
        impressions = _coerce_int(row.get("impressions"))
        clicks = _coerce_int(row.get("clicks"))
        conversions = _coerce_int(row.get("conversions"))
        reach = _coerce_int(row.get("reach"))
        rows.append(
            {
                "id": row.get("id") or "",
                "adAccountId": row.get("ad_account_id") or "",
                "name": row.get("name") or "Unnamed campaign",
                "platform": _platform_label(row.get("source_platform")),
                "status": "ACTIVE",
                "parish": row.get("parish") or "Unknown",
                "spend": spend,
                "impressions": impressions,
                "reach": reach,
                "clicks": clicks,
                "conversions": conversions,
                "roas": (conversions / spend) if spend else 0.0,
                "ctr": (clicks / impressions) if impressions else 0.0,
                "cpc": (spend / clicks) if clicks else 0.0,
                "cpm": ((spend / impressions) * 1000) if impressions else 0.0,
                "cpa": (spend / conversions) if conversions else 0.0,
                "frequency": (impressions / reach) if reach else 0.0,
                "startDate": _normalize_date_string(row.get("start_date")),
                "endDate": _normalize_date_string(row.get("end_date")),
            }
        )

    return {"summary": summary, "trend": trend_rows, "rows": rows}


def _fetch_creative_rows(*, tenant_id: str, filters: WarehouseCombinedFilters) -> list[dict[str, Any]]:
    has_reach = _relation_has_column("vw_creative_daily", "reach")
    reach_sum_expr = "coalesce(sum(c.reach), 0)" if has_reach else "0"
    has_dim_campaign = _relation_exists("dim_campaign") and _relation_has_column(
        "dim_campaign", "campaign_name"
    )
    where_clauses, params = _build_creative_where(
        alias="c",
        tenant_id=tenant_id,
        filters=filters,
    )
    campaign_name_expr = "max(c.campaign_id)"
    join_sql = ""
    if has_dim_campaign:
        campaign_name_expr = "coalesce(max(dc.campaign_name), max(c.campaign_id))"
        join_sql = """
        left join dim_campaign dc
            on c.tenant_id = dc.tenant_id
            and c.source_platform = dc.source_platform
            and c.ad_account_id = dc.ad_account_id
            and c.campaign_id = dc.campaign_id
            and c.date_day::timestamp between dc.dbt_valid_from
                and coalesce(dc.dbt_valid_to, cast('9999-12-31 23:59:59' as timestamp))
        """
    sql = f"""
        select
            c.ad_id as id,
            c.ad_account_id as ad_account_id,
            max(c.ad_name) as name,
            c.campaign_id as campaign_id,
            {campaign_name_expr} as campaign_name,
            max(c.source_platform) as source_platform,
            coalesce(max(c.parish_name), 'Unknown') as parish,
            coalesce(sum(c.spend), 0) as spend,
            coalesce(sum(c.impressions), 0) as impressions,
            coalesce(sum(c.clicks), 0) as clicks,
            coalesce(sum(c.conversions), 0) as conversions,
            {reach_sum_expr} as reach,
            min(c.date_day) as start_date,
            max(c.date_day) as end_date
        from vw_creative_daily c
        {join_sql}
        where {" and ".join(where_clauses)}
        group by c.ad_id, c.ad_account_id, c.campaign_id
        order by spend desc, name asc
        limit 100
    """
    rows = []
    for row in _fetch_rows(sql, params):
        spend = _coerce_float(row.get("spend"))
        impressions = _coerce_int(row.get("impressions"))
        clicks = _coerce_int(row.get("clicks"))
        conversions = _coerce_int(row.get("conversions"))
        reach = _coerce_int(row.get("reach"))
        rows.append(
            {
                "id": row.get("id") or "",
                "adAccountId": row.get("ad_account_id") or "",
                "name": row.get("name") or "Unnamed creative",
                "campaignId": row.get("campaign_id") or "",
                "campaignName": row.get("campaign_name") or "Unknown campaign",
                "platform": _platform_label(row.get("source_platform")),
                "parish": row.get("parish") or "Unknown",
                "spend": spend,
                "impressions": impressions,
                "reach": reach,
                "clicks": clicks,
                "conversions": conversions,
                "roas": (conversions / spend) if spend else 0.0,
                "ctr": (clicks / impressions) if impressions else 0.0,
                "cpc": (spend / clicks) if clicks else 0.0,
                "cpm": ((spend / impressions) * 1000) if impressions else 0.0,
                "cpa": (spend / conversions) if conversions else 0.0,
                "frequency": (impressions / reach) if reach else 0.0,
                "startDate": _normalize_date_string(row.get("start_date")),
                "endDate": _normalize_date_string(row.get("end_date")),
            }
        )
    return rows


def _fetch_budget_rows(*, tenant_id: str, filters: WarehouseCombinedFilters) -> list[dict[str, Any]]:
    if not _relation_exists("stg_meta_adsets"):
        return []

    budget_window_days = 30
    if filters.start_date and filters.end_date:
        budget_window_days = max((filters.end_date - filters.start_date).days + 1, 1)

    where_clauses, params = _build_fact_where(
        alias="f",
        tenant_id=tenant_id,
        filters=filters,
        include_parish=True,
        include_search=True,
    )
    sql = f"""
        with scoped as (
            select
                f.tenant_id,
                f.ad_account_id,
                f.campaign_id,
                f.date_day,
                max(f.campaign_name) as campaign_name,
                coalesce(sum(f.spend), 0) as spend,
                array_agg(distinct coalesce(f.parish_name, 'Unknown')) as parishes
            from fact_performance f
            where {" and ".join(where_clauses)}
              and f.campaign_id is not null
            group by f.tenant_id, f.ad_account_id, f.campaign_id, f.date_day
        ),
        campaign_window as (
            select
                s.tenant_id,
                s.ad_account_id,
                s.campaign_id,
                max(s.campaign_name) as campaign_name,
                coalesce(sum(s.spend), 0) as spend_to_date,
                min(s.date_day) as start_date,
                max(s.date_day) as end_date
            from scoped s
            group by s.tenant_id, s.ad_account_id, s.campaign_id
        ),
        campaign_trailing as (
            select
                s.tenant_id,
                s.ad_account_id,
                s.campaign_id,
                s.date_day,
                avg(s.spend) over (
                    partition by s.tenant_id, s.ad_account_id, s.campaign_id
                    order by s.date_day
                    rows between 6 preceding and current row
                ) as trailing_7d_avg_spend
            from scoped s
        ),
        latest_trailing as (
            select tenant_id, ad_account_id, campaign_id, trailing_7d_avg_spend
            from (
                select
                    t.*,
                    row_number() over (
                        partition by t.tenant_id, t.ad_account_id, t.campaign_id
                        order by t.date_day desc
                    ) as row_num
                from campaign_trailing t
            ) ranked
            where row_num = 1
        ),
        campaign_parishes as (
            select
                s.tenant_id,
                s.ad_account_id,
                s.campaign_id,
                array_remove(array_agg(distinct parish_value), null) as parishes
            from (
                select
                    tenant_id,
                    ad_account_id,
                    campaign_id,
                    unnest(parishes) as parish_value
                from scoped
            ) s
            group by s.tenant_id, s.ad_account_id, s.campaign_id
        ),
        campaign_budgets as (
            select
                a.tenant_id,
                a.ad_account_id,
                a.campaign_id,
                coalesce(sum(a.daily_budget), 0) as daily_budget
            from stg_meta_adsets a
            where a.campaign_id is not null
            group by a.tenant_id, a.ad_account_id, a.campaign_id
        )
        select
            w.campaign_id as id,
            w.ad_account_id as ad_account_id,
            coalesce(w.campaign_name, w.campaign_id) as campaign_name,
            coalesce(p.parishes, array[]::text[]) as parishes,
            b.daily_budget * %s as window_budget,
            b.daily_budget * 30 as monthly_budget,
            w.spend_to_date,
            coalesce(l.trailing_7d_avg_spend, 0) * %s as projected_spend,
            case
                when b.daily_budget * %s = 0 then 0
                else (coalesce(l.trailing_7d_avg_spend, 0) * %s) / (b.daily_budget * %s)
            end as pacing_percent,
            w.start_date,
            w.end_date
        from campaign_window w
        inner join campaign_budgets b
            on w.tenant_id = b.tenant_id
            and w.ad_account_id = b.ad_account_id
            and w.campaign_id = b.campaign_id
        left join latest_trailing l
            on w.tenant_id = l.tenant_id
            and w.ad_account_id = l.ad_account_id
            and w.campaign_id = l.campaign_id
        left join campaign_parishes p
            on w.tenant_id = p.tenant_id
            and w.ad_account_id = p.ad_account_id
            and w.campaign_id = p.campaign_id
        where b.daily_budget > 0
        order by w.spend_to_date desc, campaign_name asc
        limit 100
    """
    budget_params = [*params, budget_window_days, budget_window_days, budget_window_days, budget_window_days, budget_window_days]
    rows = []
    for row in _fetch_rows(sql, budget_params):
        parishes = row.get("parishes") or []
        rows.append(
            {
                "id": row.get("id") or "",
                "adAccountId": row.get("ad_account_id") or "",
                "campaignName": row.get("campaign_name") or "Unknown campaign",
                "platform": "Meta Ads",
                "parishes": [value for value in parishes if isinstance(value, str)],
                "monthlyBudget": _coerce_float(row.get("monthly_budget")),
                "windowBudget": _coerce_float(row.get("window_budget")),
                "windowDays": budget_window_days,
                "spendToDate": _coerce_float(row.get("spend_to_date")),
                "projectedSpend": _coerce_float(row.get("projected_spend")),
                "pacingPercent": _coerce_float(row.get("pacing_percent")),
                "startDate": _normalize_date_string(row.get("start_date")),
                "endDate": _normalize_date_string(row.get("end_date")),
            }
        )
    return rows


def _fetch_parish_rows(*, tenant_id: str, filters: WarehouseCombinedFilters) -> list[dict[str, Any]]:
    has_reach = _relation_has_column("vw_campaign_daily", "reach")
    reach_sum_expr = "coalesce(sum(c.reach), 0)" if has_reach else "0"
    where_clauses, params = _build_campaign_where(
        alias="c",
        tenant_id=tenant_id,
        filters=filters,
        include_parish=True,
        include_search=True,
    )
    sql = f"""
        select
            c.ad_account_id as ad_account_id,
            coalesce(c.parish_name, 'Unknown') as parish,
            coalesce(sum(c.spend), 0) as spend,
            coalesce(sum(c.impressions), 0) as impressions,
            coalesce(sum(c.clicks), 0) as clicks,
            coalesce(sum(c.conversions), 0) as conversions,
            {reach_sum_expr} as reach,
            count(distinct c.campaign_id) as campaign_count
        from vw_campaign_daily c
        where {" and ".join(where_clauses)}
        group by c.ad_account_id, coalesce(c.parish_name, 'Unknown')
        order by spend desc, parish asc
        limit 50
    """
    rows = []
    for row in _fetch_rows(sql, params):
        spend = _coerce_float(row.get("spend"))
        impressions = _coerce_int(row.get("impressions"))
        clicks = _coerce_int(row.get("clicks"))
        conversions = _coerce_int(row.get("conversions"))
        reach = _coerce_int(row.get("reach"))
        rows.append(
            {
                "adAccountId": row.get("ad_account_id") or "",
                "parish": row.get("parish") or "Unknown",
                "spend": spend,
                "impressions": impressions,
                "reach": reach,
                "clicks": clicks,
                "conversions": conversions,
                "roas": (conversions / spend) if spend else 0.0,
                "ctr": (clicks / impressions) if impressions else 0.0,
                "cpc": (spend / clicks) if clicks else 0.0,
                "cpm": ((spend / impressions) * 1000) if impressions else 0.0,
                "cpa": (spend / conversions) if conversions else 0.0,
                "frequency": (impressions / reach) if reach else 0.0,
                "campaignCount": _coerce_int(row.get("campaign_count")),
                "currency": "USD",
            }
        )
    return rows


def load_filtered_warehouse_metrics(
    *,
    tenant,
    tenant_id: str,
    options: Mapping[str, Any] | None,
    ttl_seconds: int,
) -> dict[str, Any]:
    """Return a truthful warehouse payload for filtered Meta dashboard requests."""

    snapshot_generated_at = _ensure_live_warehouse_snapshot(
        tenant=tenant,
        ttl_seconds=ttl_seconds,
    )
    filters = WarehouseCombinedFilters.from_options(options)
    base_coverage = _fetch_coverage(
        tenant_id=tenant_id,
        filters=filters.without_search_and_parish(),
    )
    coverage = _fetch_coverage(tenant_id=tenant_id, filters=filters)
    campaign = _fetch_campaign_payload(tenant_id=tenant_id, filters=filters)
    creative = _fetch_creative_rows(tenant_id=tenant_id, filters=filters)
    budget = _fetch_budget_rows(tenant_id=tenant_id, filters=filters)
    parish = _fetch_parish_rows(tenant_id=tenant_id, filters=filters)

    payload = {
        "tenant_id": tenant_id,
        "snapshot_generated_at": snapshot_generated_at,
        "campaign": campaign,
        "creative": creative,
        "budget": budget,
        "parish": parish,
        "coverage": {
            "startDate": coverage.start_date.isoformat() if coverage.start_date else None,
            "endDate": coverage.end_date.isoformat() if coverage.end_date else None,
        },
        "availability": _build_availability(
            base_coverage=base_coverage,
            campaign_rows=campaign.get("rows") or [],
            creative_rows=creative,
            budget_rows=budget,
            parish_rows=parish,
            filters=filters,
        ),
    }
    return enrich_combined_payload_metadata(payload)
