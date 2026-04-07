"""Adapter that aggregates live Meta sync tables without requiring warehouse views."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from django.db.models import Q
from django.utils import timezone

from analytics.models import RawPerformanceRecord
from analytics.serializers import CombinedMetricsQueryParamsSerializer

from .base import AdapterInterface, MetricsAdapter

META_CHANNEL_ALIASES = {"meta", "meta_ads"}
META_PLATFORM_LABEL = "Meta Ads"
FALLBACK_CURRENCY = "USD"


@dataclass(frozen=True)
class MetaDirectFilters:
    start_date: date | None = None
    end_date: date | None = None
    account_id: str | None = None
    channels: tuple[str, ...] = ()
    campaign_search: str | None = None

    @property
    def excludes_meta_channel(self) -> bool:
        return bool(self.channels) and not any(channel in META_CHANNEL_ALIASES for channel in self.channels)


def _normalize_account_aliases(value: str | None) -> set[str]:
    if not value:
        return set()
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


def _normalize_channels(value: Iterable[str] | None) -> tuple[str, ...]:
    if not value:
        return ()
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().lower()
        if not cleaned:
            continue
        if cleaned == "meta ads":
            cleaned = "meta_ads"
        normalized.append(cleaned)
    return tuple(dict.fromkeys(normalized))


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _validated_filters(options: Mapping[str, Any] | None) -> MetaDirectFilters:
    serializer_input = options.dict() if options is not None and hasattr(options, "dict") else dict(options or {})
    for key, value in list(serializer_input.items()):
        if isinstance(value, (list, tuple)):
            cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            if key in {"channels", "parish"}:
                serializer_input[key] = ",".join(cleaned)
            else:
                serializer_input[key] = cleaned[0] if cleaned else None

    serializer = CombinedMetricsQueryParamsSerializer(data=serializer_input)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    return MetaDirectFilters(
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        account_id=data.get("account_id"),
        channels=_normalize_channels(data.get("channels")),
        campaign_search=data.get("campaign_search"),
    )


def _coverage_payload(filters: MetaDirectFilters, records: Sequence[RawPerformanceRecord]) -> dict[str, str | None]:
    if filters.start_date or filters.end_date:
        return {
            "startDate": filters.start_date.isoformat() if filters.start_date else None,
            "endDate": filters.end_date.isoformat() if filters.end_date else None,
        }
    if not records:
        return {"startDate": None, "endDate": None}
    return {
        "startDate": min(record.date for record in records).isoformat(),
        "endDate": max(record.date for record in records).isoformat(),
    }


def _snapshot_generated_at(records: Sequence[RawPerformanceRecord]) -> str | None:
    if not records:
        return None
    freshest = max(
        (
            record.ingested_at
            or record.updated_at
            or timezone.make_aware(datetime.combine(record.date, time.max))
        )
        for record in records
    )
    return freshest.isoformat()


def _empty_payload(*, tenant_id: str, filters: MetaDirectFilters, reason: str) -> dict[str, Any]:
    coverage = _coverage_payload(filters, [])
    return {
        "tenant_id": tenant_id,
        "campaign": {
            "summary": {
                "currency": FALLBACK_CURRENCY,
                "totalSpend": 0.0,
                "totalImpressions": 0,
                "totalReach": 0,
                "totalClicks": 0,
                "totalConversions": 0,
                "averageRoas": 0.0,
                "ctr": 0.0,
                "cpc": 0.0,
                "cpm": 0.0,
                "cpa": 0.0,
                "frequency": 0.0,
            },
            "trend": [],
            "rows": [],
        },
        "creative": [],
        "budget": [],
        "parish": [],
        "coverage": coverage,
        "availability": {
            "campaign": {"status": "empty", "reason": reason},
            "creative": {"status": "empty", "reason": reason},
            "budget": {"status": "empty", "reason": reason},
            "parish_map": {"status": "empty", "reason": reason, "coverage_percent": 0.0},
        },
        "snapshot_generated_at": None,
    }


def _record_currency(record: RawPerformanceRecord) -> str:
    candidates = [
        record.currency,
        record.campaign.currency if record.campaign_id and record.campaign is not None else None,
        record.ad_account.currency if record.ad_account_id and record.ad_account is not None else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            trimmed = candidate.strip()
            if trimmed:
                return trimmed
    return FALLBACK_CURRENCY


class MetaDirectAdapter(MetricsAdapter):
    key = "meta_direct"
    name = "Meta direct sync"
    description = "Aggregated directly from synced Meta tables when warehouse reporting is unavailable."
    interfaces: tuple[AdapterInterface, ...] = (
        AdapterInterface(
            key="meta",
            label="Meta Ads",
            description="Uses tenant-scoped Meta campaign/ad/ad set/performance rows without warehouse views.",
        ),
    )

    def fetch_metrics(
        self,
        *,
        tenant_id: str,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        filters = _validated_filters(options)
        if filters.excludes_meta_channel:
            return _empty_payload(
                tenant_id=tenant_id,
                filters=filters,
                reason="no_matching_filters",
            )

        queryset = RawPerformanceRecord.objects.filter(
            tenant_id=tenant_id,
            source__iexact="meta",
        ).select_related(
            "ad_account",
            "campaign",
            "adset",
            "ad",
        )
        if filters.start_date:
            queryset = queryset.filter(date__gte=filters.start_date)
        if filters.end_date:
            queryset = queryset.filter(date__lte=filters.end_date)
        if filters.account_id:
            aliases = _normalize_account_aliases(filters.account_id)
            numeric_aliases = {alias[4:] if alias.startswith("act_") else alias for alias in aliases}
            queryset = queryset.filter(
                Q(ad_account__external_id__in=aliases)
                | Q(ad_account__account_id__in=numeric_aliases)
                | Q(campaign__account_external_id__in=aliases)
                | Q(campaign__account_external_id__in=numeric_aliases)
            )
        if filters.campaign_search:
            queryset = queryset.filter(
                Q(campaign__name__icontains=filters.campaign_search)
                | Q(ad__name__icontains=filters.campaign_search)
                | Q(adset__name__icontains=filters.campaign_search)
            )

        records = list(queryset.order_by("date", "campaign__name", "ad__name", "external_id"))
        if not records:
            empty_reason = "no_matching_filters" if filters.campaign_search else "no_recent_data"
            return _empty_payload(
                tenant_id=tenant_id,
                filters=filters,
                reason=empty_reason,
            )

        coverage = _coverage_payload(filters, records)
        coverage_start = filters.start_date or min(record.date for record in records)
        coverage_end = filters.end_date or max(record.date for record in records)
        window_days = max((coverage_end - coverage_start).days + 1, 1)
        today = timezone.localdate()
        elapsed_end = min(coverage_end, today) if coverage_start <= today else coverage_start
        elapsed_days = max((elapsed_end - coverage_start).days + 1, 1)

        currency = next(
            (
                candidate
                for candidate in (_record_currency(record) for record in records)
                if candidate != FALLBACK_CURRENCY
            ),
            FALLBACK_CURRENCY,
        )

        trend_by_date: dict[str, dict[str, Any]] = {}
        campaign_groups: dict[str, dict[str, Any]] = {}
        creative_groups: dict[str, dict[str, Any]] = {}
        campaign_budgets: dict[str, dict[str, float]] = defaultdict(dict)

        for record in records:
            spend = _to_float(record.spend)
            impressions = _to_int(record.impressions)
            reach = _to_int(record.reach)
            clicks = _to_int(record.clicks)
            conversions = _to_int(record.conversions)
            ad_account_id = (
                record.ad_account.external_id
                if record.ad_account_id and record.ad_account is not None
                else record.campaign.account_external_id
                if record.campaign_id and record.campaign is not None
                else ""
            )

            trend_key = record.date.isoformat()
            trend_point = trend_by_date.setdefault(
                trend_key,
                {
                    "date": trend_key,
                    "spend": 0.0,
                    "impressions": 0,
                    "reach": 0,
                    "clicks": 0,
                    "conversions": 0,
                    "adAccountId": ad_account_id or None,
                },
            )
            trend_point["spend"] += spend
            trend_point["impressions"] += impressions
            trend_point["reach"] += reach
            trend_point["clicks"] += clicks
            trend_point["conversions"] += conversions

            if record.campaign_id and record.campaign is not None:
                campaign_key = record.campaign.external_id
                campaign_group = campaign_groups.setdefault(
                    campaign_key,
                    {
                        "id": campaign_key,
                        "adAccountId": ad_account_id,
                        "name": record.campaign.name,
                        "platform": META_PLATFORM_LABEL,
                        "status": record.campaign.status or "Unknown",
                        "objective": record.campaign.objective or None,
                        "parishes": [],
                        "spend": 0.0,
                        "impressions": 0,
                        "reach": 0,
                        "clicks": 0,
                        "conversions": 0,
                        "startDate": record.date.isoformat(),
                        "endDate": record.date.isoformat(),
                    },
                )
                campaign_group["spend"] += spend
                campaign_group["impressions"] += impressions
                campaign_group["reach"] += reach
                campaign_group["clicks"] += clicks
                campaign_group["conversions"] += conversions
                campaign_group["startDate"] = min(campaign_group["startDate"], record.date.isoformat())
                campaign_group["endDate"] = max(campaign_group["endDate"], record.date.isoformat())

                if record.adset_id and record.adset is not None:
                    campaign_budgets[campaign_key][record.adset.external_id] = _to_float(
                        record.adset.daily_budget
                    )

            if record.ad_id and record.ad is not None and record.campaign_id and record.campaign is not None:
                creative_key = record.ad.external_id
                creative_group = creative_groups.setdefault(
                    creative_key,
                    {
                        "id": creative_key,
                        "adAccountId": ad_account_id,
                        "name": record.ad.name,
                        "campaignId": record.campaign.external_id,
                        "campaignName": record.campaign.name,
                        "platform": META_PLATFORM_LABEL,
                        "parishes": [],
                        "spend": 0.0,
                        "impressions": 0,
                        "reach": 0,
                        "clicks": 0,
                        "conversions": 0,
                        "startDate": record.date.isoformat(),
                        "endDate": record.date.isoformat(),
                        "thumbnailUrl": (
                            record.ad.creative.get("thumbnail_url")
                            if isinstance(record.ad.creative, Mapping)
                            and isinstance(record.ad.creative.get("thumbnail_url"), str)
                            else None
                        ),
                    },
                )
                creative_group["spend"] += spend
                creative_group["impressions"] += impressions
                creative_group["reach"] += reach
                creative_group["clicks"] += clicks
                creative_group["conversions"] += conversions
                creative_group["startDate"] = min(creative_group["startDate"], record.date.isoformat())
                creative_group["endDate"] = max(creative_group["endDate"], record.date.isoformat())

        campaign_rows = list(campaign_groups.values())
        for row in campaign_rows:
            spend = row["spend"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            conversions = row["conversions"]
            reach = row["reach"]
            row["roas"] = _safe_divide(conversions, spend)
            row["ctr"] = _safe_divide(clicks, impressions)
            row["cpc"] = _safe_divide(spend, clicks)
            row["cpm"] = _safe_divide(spend * 1000, impressions)
            row["cpa"] = _safe_divide(spend, conversions)
            row["frequency"] = _safe_divide(impressions, reach)

        creative_rows = list(creative_groups.values())
        for row in creative_rows:
            spend = row["spend"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            conversions = row["conversions"]
            reach = row["reach"]
            row["roas"] = _safe_divide(conversions, spend)
            row["ctr"] = _safe_divide(clicks, impressions)
            row["cpc"] = _safe_divide(spend, clicks)
            row["cpm"] = _safe_divide(spend * 1000, impressions)
            row["cpa"] = _safe_divide(spend, conversions)
            row["frequency"] = _safe_divide(impressions, reach)
            if row["thumbnailUrl"] is None:
                row.pop("thumbnailUrl", None)

        budget_rows: list[dict[str, Any]] = []
        for campaign_key, campaign_row in campaign_groups.items():
            unique_budgets = [budget for budget in campaign_budgets.get(campaign_key, {}).values() if budget > 0]
            if not unique_budgets:
                continue
            daily_budget_total = sum(unique_budgets)
            monthly_budget = daily_budget_total * 30
            window_budget = daily_budget_total * window_days
            spend_to_date = campaign_row["spend"]
            projected_spend = (
                _safe_divide(spend_to_date, elapsed_days) * window_days
                if coverage_end >= today
                else spend_to_date
            )
            budget_rows.append(
                {
                    "id": campaign_key,
                    "adAccountId": campaign_row["adAccountId"],
                    "campaignName": campaign_row["name"],
                    "platform": META_PLATFORM_LABEL,
                    "parishes": [],
                    "monthlyBudget": monthly_budget,
                    "windowBudget": window_budget,
                    "windowDays": window_days,
                    "spendToDate": spend_to_date,
                    "projectedSpend": projected_spend,
                    "pacingPercent": _safe_divide(projected_spend, window_budget),
                    "startDate": coverage_start.isoformat(),
                    "endDate": coverage_end.isoformat(),
                }
            )

        trend_rows = [trend_by_date[key] for key in sorted(trend_by_date)]
        total_spend = sum(point["spend"] for point in trend_rows)
        total_impressions = sum(point["impressions"] for point in trend_rows)
        total_reach = sum(point["reach"] for point in trend_rows)
        total_clicks = sum(point["clicks"] for point in trend_rows)
        total_conversions = sum(point["conversions"] for point in trend_rows)
        summary = {
            "currency": currency,
            "totalSpend": total_spend,
            "totalImpressions": total_impressions,
            "totalReach": total_reach,
            "totalClicks": total_clicks,
            "totalConversions": total_conversions,
            "averageRoas": _safe_divide(total_conversions, total_spend),
            "ctr": _safe_divide(total_clicks, total_impressions),
            "cpc": _safe_divide(total_spend, total_clicks),
            "cpm": _safe_divide(total_spend * 1000, total_impressions),
            "cpa": _safe_divide(total_spend, total_conversions),
            "frequency": _safe_divide(total_impressions, total_reach),
        }

        availability = {
            "campaign": {
                "status": "available" if campaign_rows else "empty",
                "reason": None if campaign_rows else "no_recent_data",
            },
            "creative": {
                "status": "available" if creative_rows else "empty",
                "reason": None if creative_rows else "no_recent_data",
            },
            "budget": {
                "status": "available" if budget_rows else ("unavailable" if campaign_rows else "empty"),
                "reason": None if budget_rows else ("budget_unavailable" if campaign_rows else "no_recent_data"),
            },
            "parish_map": {
                "status": "unavailable" if campaign_rows else "empty",
                "reason": "geo_unavailable" if campaign_rows else "no_recent_data",
                "coverage_percent": 0.0,
            },
        }

        return {
            "tenant_id": tenant_id,
            "campaign": {
                "summary": summary,
                "trend": trend_rows,
                "rows": sorted(campaign_rows, key=lambda row: (-row["spend"], row["name"])),
            },
            "creative": sorted(creative_rows, key=lambda row: (-row["spend"], row["name"])),
            "budget": sorted(budget_rows, key=lambda row: (-row["spendToDate"], row["campaignName"])),
            "parish": [],
            "coverage": coverage,
            "availability": availability,
            "snapshot_generated_at": _snapshot_generated_at(records),
        }
