"""Demo adapter serving curated datasets for showcase tenants."""

from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .base import AdapterInterface, MetricsAdapter, get_default_interfaces


@dataclass(frozen=True)
class SeededDemoData:
    tenant_order: list[str]
    tenants: dict[str, dict[str, Any]]
    campaigns: list[dict[str, Any]]
    creatives: list[dict[str, Any]]
    daily_campaign: list[dict[str, Any]]
    daily_creative: list[dict[str, Any]]
    daily_parish: list[dict[str, Any]]
    monthly_budgets: list[dict[str, Any]]


_DEMO_SEED_FILES = [
    "dim_tenants.csv",
    "dim_campaigns.csv",
    "dim_creatives.csv",
    "fact_daily_campaign_metrics.csv",
    "fact_daily_parish_metrics.csv",
    "fact_daily_creative_metrics.csv",
    "plan_monthly_budgets.csv",
]


def _demo_seed_dir() -> Path:
    configured = getattr(settings, "DEMO_SEED_DIR", None)
    if configured:
        return Path(configured)
    return Path(settings.BASE_DIR).parent / "dbt" / "seeds" / "demo"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _parse_date_value(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        parsed = parse_date(candidate)
        if parsed is not None:
            return parsed
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            return None
    return None


def _parse_datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        parsed = parse_datetime(candidate)
        if parsed is not None:
            return parsed
        if candidate.endswith("Z"):
            return parse_datetime(candidate.replace("Z", "+00:00"))
    return None


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return parse_date(value)
    return None


def _parse_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _normalize_parish(value: Any) -> str:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return "Unknown"


def _normalize_parish_filter(value: Any) -> list[str]:
    if value is None:
        return []
    values: list[str] = []
    if isinstance(value, str):
        values.extend(value.split(","))
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for item in value:
            if isinstance(item, str):
                values.extend(item.split(","))
    return [item.strip() for item in values if item.strip()]


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _resolve_snapshot_timestamp(value: Any) -> str:
    parsed = _parse_datetime_value(value)
    if parsed is None:
        parsed = timezone.now()
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed.isoformat()


@lru_cache(maxsize=4)
def _load_seeded_demo_data(seed_dir: Path) -> SeededDemoData | None:
    if not seed_dir.exists():
        return None

    required = [seed_dir / name for name in _DEMO_SEED_FILES]
    if not all(path.exists() for path in required):
        return None

    tenants_rows = _read_csv_rows(seed_dir / "dim_tenants.csv")
    tenant_order: list[str] = []
    tenants: dict[str, dict[str, Any]] = {}
    for row in tenants_rows:
        tenant_id = (row.get("tenant_id") or "").strip()
        if not tenant_id:
            continue
        tenant_order.append(tenant_id)
        tenants[tenant_id] = {
            "tenant_id": tenant_id,
            "tenant_name": (row.get("tenant_name") or tenant_id).strip() or tenant_id,
            "currency": (row.get("currency") or "USD").strip() or "USD",
            "timezone": (row.get("timezone") or "America/Jamaica").strip()
            or "America/Jamaica",
            "snapshot_generated_at": row.get("snapshot_generated_at"),
        }

    if not tenants:
        return None

    campaigns = []
    for row in _read_csv_rows(seed_dir / "dim_campaigns.csv"):
        tenant_id = (row.get("tenant_id") or "").strip()
        campaign_id = (row.get("campaign_id") or "").strip()
        if not tenant_id or not campaign_id:
            continue
        campaigns.append(
            {
                "tenant_id": tenant_id,
                "campaign_id": campaign_id,
                "channel": (row.get("channel") or "").strip(),
                "campaign_name": (row.get("campaign_name") or campaign_id).strip()
                or campaign_id,
                "objective": (row.get("objective") or "").strip(),
                "status": (row.get("status") or "").strip() or "ACTIVE",
                "start_date": _parse_date_value(row.get("start_date")),
                "end_date": _parse_date_value(row.get("end_date")),
                "parish": row.get("parish"),
            }
        )

    creatives = []
    for row in _read_csv_rows(seed_dir / "dim_creatives.csv"):
        tenant_id = (row.get("tenant_id") or "").strip()
        creative_id = (row.get("creative_id") or "").strip()
        if not tenant_id or not creative_id:
            continue
        creatives.append(
            {
                "tenant_id": tenant_id,
                "campaign_id": (row.get("campaign_id") or "").strip(),
                "channel": (row.get("channel") or "").strip(),
                "creative_id": creative_id,
                "creative_name": (row.get("creative_name") or creative_id).strip()
                or creative_id,
                "creative_type": (row.get("creative_type") or "").strip(),
            }
        )

    daily_campaign = []
    for row in _read_csv_rows(seed_dir / "fact_daily_campaign_metrics.csv"):
        tenant_id = (row.get("tenant_id") or "").strip()
        campaign_id = (row.get("campaign_id") or "").strip()
        date_value = _parse_date_value(row.get("date"))
        if not tenant_id or not campaign_id or date_value is None:
            continue
        daily_campaign.append(
            {
                "tenant_id": tenant_id,
                "campaign_id": campaign_id,
                "channel": (row.get("channel") or "").strip(),
                "date": date_value,
                "spend": _parse_float(row.get("spend")),
                "impressions": _parse_int(row.get("impressions")),
                "clicks": _parse_int(row.get("clicks")),
                "conversions": _parse_int(row.get("conversions")),
                "revenue": _parse_float(row.get("revenue")),
                "roas": _parse_float(row.get("roas")),
                "snapshot_generated_at": row.get("snapshot_generated_at"),
            }
        )

    daily_parish = []
    for row in _read_csv_rows(seed_dir / "fact_daily_parish_metrics.csv"):
        tenant_id = (row.get("tenant_id") or "").strip()
        date_value = _parse_date_value(row.get("date"))
        if not tenant_id or date_value is None:
            continue
        daily_parish.append(
            {
                "tenant_id": tenant_id,
                "channel": (row.get("channel") or "").strip(),
                "date": date_value,
                "parish": row.get("parish"),
                "spend": _parse_float(row.get("spend")),
                "impressions": _parse_int(row.get("impressions")),
                "clicks": _parse_int(row.get("clicks")),
                "conversions": _parse_int(row.get("conversions")),
                "revenue": _parse_float(row.get("revenue")),
                "roas": _parse_float(row.get("roas")),
            }
        )

    daily_creative = []
    for row in _read_csv_rows(seed_dir / "fact_daily_creative_metrics.csv"):
        tenant_id = (row.get("tenant_id") or "").strip()
        creative_id = (row.get("creative_id") or "").strip()
        date_value = _parse_date_value(row.get("date"))
        if not tenant_id or not creative_id or date_value is None:
            continue
        daily_creative.append(
            {
                "tenant_id": tenant_id,
                "campaign_id": (row.get("campaign_id") or "").strip(),
                "channel": (row.get("channel") or "").strip(),
                "creative_id": creative_id,
                "creative_type": (row.get("creative_type") or "").strip(),
                "date": date_value,
                "spend": _parse_float(row.get("spend")),
                "impressions": _parse_int(row.get("impressions")),
                "clicks": _parse_int(row.get("clicks")),
                "conversions": _parse_int(row.get("conversions")),
                "revenue": _parse_float(row.get("revenue")),
                "roas": _parse_float(row.get("roas")),
            }
        )

    monthly_budgets = []
    for row in _read_csv_rows(seed_dir / "plan_monthly_budgets.csv"):
        tenant_id = (row.get("tenant_id") or "").strip()
        campaign_id = (row.get("campaign_id") or "").strip()
        month_value = _parse_date_value(row.get("month"))
        if not tenant_id or not campaign_id or month_value is None:
            continue
        monthly_budgets.append(
            {
                "tenant_id": tenant_id,
                "campaign_id": campaign_id,
                "channel": (row.get("channel") or "").strip(),
                "month": month_value,
                "planned_budget": _parse_float(row.get("planned_budget")),
            }
        )

    return SeededDemoData(
        tenant_order=tenant_order,
        tenants=tenants,
        campaigns=campaigns,
        creatives=creatives,
        daily_campaign=daily_campaign,
        daily_creative=daily_creative,
        daily_parish=daily_parish,
        monthly_budgets=monthly_budgets,
    )


def clear_demo_seed_cache() -> None:
    _load_seeded_demo_data.cache_clear()


def _month_window(target: date) -> tuple[date, date, int]:
    month_start = date(target.year, target.month, 1)
    next_month = month_start.replace(day=28) + timedelta(days=4)
    month_end = next_month.replace(day=1) - timedelta(days=1)
    return month_start, month_end, month_end.day


def _build_seeded_payload(
    seed_data: SeededDemoData,
    demo_tenant_id: str,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_id = demo_tenant_id
    tenant = seed_data.tenants.get(tenant_id)
    if tenant is None:
        tenant_id = seed_data.tenant_order[0]
        tenant = seed_data.tenants[tenant_id]

    start_date = _coerce_date(options.get("start_date")) if options else None
    end_date = _coerce_date(options.get("end_date")) if options else None
    parish_filter = _normalize_parish_filter(options.get("parish")) if options else []
    normalized_parishes = {parish.lower() for parish in parish_filter}

    campaigns = [c for c in seed_data.campaigns if c["tenant_id"] == tenant_id]
    campaign_lookup = {c["campaign_id"]: c for c in campaigns}
    campaign_parish = {
        c["campaign_id"]: _normalize_parish(c.get("parish"))
        for c in campaigns
    }
    campaign_count_by_parish: dict[str, int] = {}
    for parish in campaign_parish.values():
        campaign_count_by_parish[parish] = campaign_count_by_parish.get(parish, 0) + 1

    def matches_parish(value: str) -> bool:
        if not normalized_parishes:
            return True
        return value.lower() in normalized_parishes

    filtered_daily = []
    for row in seed_data.daily_campaign:
        if row["tenant_id"] != tenant_id:
            continue
        date_value: date = row["date"]
        if start_date and date_value < start_date:
            continue
        if end_date and date_value > end_date:
            continue
        parish = _normalize_parish(campaign_parish.get(row["campaign_id"]))
        if normalized_parishes and not matches_parish(parish):
            continue
        filtered_daily.append(row)

    summary_spend = 0.0
    summary_revenue = 0.0
    summary_impressions = 0
    summary_clicks = 0
    summary_conversions = 0
    trend_totals: dict[date, dict[str, float]] = {}

    for row in filtered_daily:
        summary_spend += row["spend"]
        summary_revenue += row["revenue"]
        summary_impressions += row["impressions"]
        summary_clicks += row["clicks"]
        summary_conversions += row["conversions"]

        bucket = trend_totals.setdefault(
            row["date"],
            {"spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0},
        )
        bucket["spend"] += row["spend"]
        bucket["impressions"] += row["impressions"]
        bucket["clicks"] += row["clicks"]
        bucket["conversions"] += row["conversions"]

    trend = [
        {
            "date": date_key.isoformat(),
            "spend": round(metrics["spend"], 2),
            "impressions": int(metrics["impressions"]),
            "clicks": int(metrics["clicks"]),
            "conversions": int(metrics["conversions"]),
        }
        for date_key, metrics in sorted(trend_totals.items())
    ]

    campaign_totals: dict[str, dict[str, float]] = {}
    for row in filtered_daily:
        bucket = campaign_totals.setdefault(
            row["campaign_id"],
            {
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
            },
        )
        bucket["spend"] += row["spend"]
        bucket["impressions"] += row["impressions"]
        bucket["clicks"] += row["clicks"]
        bucket["conversions"] += row["conversions"]
        bucket["revenue"] += row["revenue"]

    campaign_rows = []
    for campaign_id, metrics in campaign_totals.items():
        meta = campaign_lookup.get(campaign_id, {})
        parish = _normalize_parish(campaign_parish.get(campaign_id))
        row = {
            "id": campaign_id,
            "name": meta.get("campaign_name") or campaign_id,
            "platform": meta.get("channel") or "",
            "status": meta.get("status") or "ACTIVE",
            "objective": meta.get("objective") or "",
            "parish": parish,
            "spend": round(metrics["spend"], 2),
            "impressions": int(metrics["impressions"]),
            "clicks": int(metrics["clicks"]),
            "conversions": int(metrics["conversions"]),
            "roas": round(_safe_divide(metrics["revenue"], metrics["spend"]), 2),
            "ctr": round(_safe_divide(metrics["clicks"], metrics["impressions"]), 4),
            "cpc": round(_safe_divide(metrics["spend"], metrics["clicks"]), 2),
            "cpm": round(_safe_divide(metrics["spend"] * 1000, metrics["impressions"]), 2),
        }
        if meta.get("start_date"):
            row["startDate"] = meta["start_date"].isoformat()
        if meta.get("end_date"):
            row["endDate"] = meta["end_date"].isoformat()
        campaign_rows.append(row)

    campaign_rows.sort(key=lambda row: row["spend"], reverse=True)

    creatives = [c for c in seed_data.creatives if c["tenant_id"] == tenant_id]
    creative_lookup = {c["creative_id"]: c for c in creatives}
    creative_totals: dict[str, dict[str, float]] = {}
    for row in seed_data.daily_creative:
        if row["tenant_id"] != tenant_id:
            continue
        date_value: date = row["date"]
        if start_date and date_value < start_date:
            continue
        if end_date and date_value > end_date:
            continue
        parish = _normalize_parish(campaign_parish.get(row["campaign_id"]))
        if normalized_parishes and not matches_parish(parish):
            continue
        bucket = creative_totals.setdefault(
            row["creative_id"],
            {
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
                "campaign_id": row["campaign_id"],
            },
        )
        bucket["spend"] += row["spend"]
        bucket["impressions"] += row["impressions"]
        bucket["clicks"] += row["clicks"]
        bucket["conversions"] += row["conversions"]
        bucket["revenue"] += row["revenue"]

    creative_rows = []
    for creative_id, metrics in creative_totals.items():
        meta = creative_lookup.get(creative_id, {})
        campaign_id = metrics["campaign_id"]
        campaign_meta = campaign_lookup.get(campaign_id, {})
        parish = _normalize_parish(campaign_parish.get(campaign_id))
        creative_rows.append(
            {
                "id": creative_id,
                "name": meta.get("creative_name") or creative_id,
                "campaignId": campaign_id,
                "campaignName": campaign_meta.get("campaign_name") or campaign_id,
                "platform": meta.get("channel") or campaign_meta.get("channel") or "",
                "parish": parish,
                "spend": round(metrics["spend"], 2),
                "impressions": int(metrics["impressions"]),
                "clicks": int(metrics["clicks"]),
                "conversions": int(metrics["conversions"]),
                "roas": round(_safe_divide(metrics["revenue"], metrics["spend"]), 2),
                "ctr": round(_safe_divide(metrics["clicks"], metrics["impressions"]), 4),
            }
        )

    creative_rows.sort(key=lambda row: row["spend"], reverse=True)

    tenant_dates = [
        row["date"] for row in seed_data.daily_campaign if row["tenant_id"] == tenant_id
    ]
    if end_date:
        window_end = end_date
    else:
        window_end = max(tenant_dates) if tenant_dates else timezone.now().date()
    month_start, month_end, days_in_month = _month_window(window_end)

    budget_rows = []
    for budget in seed_data.monthly_budgets:
        if budget["tenant_id"] != tenant_id:
            continue
        if budget["month"] != month_start:
            continue
        campaign_id = budget["campaign_id"]
        parish = _normalize_parish(campaign_parish.get(campaign_id))
        if normalized_parishes and not matches_parish(parish):
            continue
        campaign_meta = campaign_lookup.get(campaign_id, {})

        daily_spend = [
            row
            for row in filtered_daily
            if row["campaign_id"] == campaign_id
            and month_start <= row["date"] <= month_end
        ]
        spend_to_date = sum(row["spend"] for row in daily_spend)
        recent = sorted(daily_spend, key=lambda row: row["date"])[-7:]
        trailing_avg = (
            sum(row["spend"] for row in recent) / len(recent)
            if recent
            else 0.0
        )
        projected_spend = trailing_avg * days_in_month
        planned_budget = budget["planned_budget"]
        pacing_percent = _safe_divide(projected_spend, planned_budget)

        budget_rows.append(
            {
                "id": campaign_id,
                "campaignName": campaign_meta.get("campaign_name") or campaign_id,
                "parishes": [parish] if parish else ["Unknown"],
                "monthlyBudget": round(planned_budget, 2),
                "spendToDate": round(spend_to_date, 2),
                "projectedSpend": round(projected_spend, 2),
                "pacingPercent": round(pacing_percent, 4),
                "startDate": month_start.isoformat(),
                "endDate": month_end.isoformat(),
            }
        )

    budget_rows.sort(key=lambda row: row["spendToDate"], reverse=True)

    parish_totals: dict[str, dict[str, float]] = {}
    for row in seed_data.daily_parish:
        if row["tenant_id"] != tenant_id:
            continue
        date_value: date = row["date"]
        if start_date and date_value < start_date:
            continue
        if end_date and date_value > end_date:
            continue
        parish = _normalize_parish(row.get("parish"))
        if normalized_parishes and not matches_parish(parish):
            continue
        bucket = parish_totals.setdefault(
            parish,
            {
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
            },
        )
        bucket["spend"] += row["spend"]
        bucket["impressions"] += row["impressions"]
        bucket["clicks"] += row["clicks"]
        bucket["conversions"] += row["conversions"]
        bucket["revenue"] += row["revenue"]

    parish_rows = []
    for parish, metrics in parish_totals.items():
        parish_rows.append(
            {
                "parish": parish,
                "spend": round(metrics["spend"], 2),
                "impressions": int(metrics["impressions"]),
                "clicks": int(metrics["clicks"]),
                "conversions": int(metrics["conversions"]),
                "roas": round(_safe_divide(metrics["revenue"], metrics["spend"]), 2),
                "campaignCount": campaign_count_by_parish.get(parish, 0),
                "currency": tenant.get("currency"),
            }
        )

    parish_rows.sort(key=lambda row: row["spend"], reverse=True)

    summary_payload = {
        "currency": tenant.get("currency"),
        "totalSpend": round(summary_spend, 2),
        "totalImpressions": int(summary_impressions),
        "totalClicks": int(summary_clicks),
        "totalConversions": int(summary_conversions),
        "averageRoas": round(_safe_divide(summary_revenue, summary_spend), 2),
    }

    snapshot_generated_at = _resolve_snapshot_timestamp(
        tenant.get("snapshot_generated_at")
    )

    return {
        "tenant_id": tenant_id,
        "tenant_label": tenant.get("tenant_name"),
        "campaign": {
            "summary": summary_payload,
            "trend": trend,
            "rows": campaign_rows,
        },
        "creative": creative_rows,
        "budget": budget_rows,
        "parish": parish_rows,
        "snapshot_generated_at": snapshot_generated_at,
    }


DEMO_DATASETS: Mapping[str, Mapping[str, Any]] = {
    "bank-of-jamaica": {
        "label": "Bank of Jamaica",
        "payload": {
            "campaign": {
                "summary": {
                    "currency": "JMD",
                    "totalSpend": 4200000,
                    "totalImpressions": 1850000,
                    "totalClicks": 86000,
                    "totalConversions": 5400,
                    "averageRoas": 4.2,
                },
                "trend": [
                    {
                        "date": "2024-09-01",
                        "spend": 780000,
                        "conversions": 980,
                        "clicks": 16200,
                        "impressions": 310000,
                    },
                    {
                        "date": "2024-09-02",
                        "spend": 690000,
                        "conversions": 910,
                        "clicks": 15400,
                        "impressions": 295000,
                    },
                    {
                        "date": "2024-09-03",
                        "spend": 640000,
                        "conversions": 870,
                        "clicks": 14950,
                        "impressions": 288000,
                    },
                ],
                "rows": [
                    {
                        "id": "boj_fx_awareness",
                        "name": "FX Market Awareness",
                        "platform": "Meta",
                        "status": "Active",
                        "parish": "Kingston",
                        "spend": 1200000,
                        "impressions": 540000,
                        "clicks": 24500,
                        "conversions": 1600,
                        "roas": 3.9,
                        "ctr": 0.045,
                        "cpc": 49.0,
                        "cpm": 222.0,
                        "startDate": "2024-08-01",
                        "endDate": "2024-09-30",
                    },
                    {
                        "id": "boj_policy_updates",
                        "name": "Policy Update Series",
                        "platform": "Google Ads",
                        "status": "Active",
                        "parish": "St Andrew",
                        "spend": 980000,
                        "impressions": 460000,
                        "clicks": 22100,
                        "conversions": 1420,
                        "roas": 4.5,
                        "ctr": 0.048,
                        "cpc": 44.4,
                        "cpm": 213.0,
                        "startDate": "2024-08-10",
                        "endDate": "2024-09-28",
                    },
                    {
                        "id": "boj_digital_payments",
                        "name": "Digital Payments Launch",
                        "platform": "TikTok",
                        "status": "Learning",
                        "parish": "St James",
                        "spend": 880000,
                        "impressions": 410000,
                        "clicks": 18900,
                        "conversions": 1350,
                        "roas": 4.1,
                        "ctr": 0.046,
                        "cpc": 46.6,
                        "cpm": 214.6,
                        "startDate": "2024-08-18",
                        "endDate": "2024-10-05",
                    },
                ],
            },
            "creative": [
                {
                    "id": "boj_fx_video",
                    "name": "FX Explainer Video",
                    "campaignId": "boj_fx_awareness",
                    "campaignName": "FX Market Awareness",
                    "platform": "Meta",
                    "parish": "Kingston",
                    "spend": 420000,
                    "impressions": 210000,
                    "clicks": 10200,
                    "conversions": 680,
                    "roas": 3.6,
                    "ctr": 0.0486,
                },
                {
                    "id": "boj_policy_search",
                    "name": "Policy Hub Search",
                    "campaignId": "boj_policy_updates",
                    "campaignName": "Policy Update Series",
                    "platform": "Google Ads",
                    "parish": "St Andrew",
                    "spend": 360000,
                    "impressions": 176000,
                    "clicks": 8600,
                    "conversions": 540,
                    "roas": 4.2,
                    "ctr": 0.0489,
                },
            ],
            "budget": [
                {
                    "id": "boj_fx_awareness_budget",
                    "campaignName": "FX Market Awareness",
                    "parishes": ["Kingston", "St Andrew"],
                    "monthlyBudget": 1500000,
                    "spendToDate": 1200000,
                    "projectedSpend": 1480000,
                    "pacingPercent": 0.99,
                    "startDate": "2024-08-01",
                    "endDate": "2024-09-30",
                },
                {
                    "id": "boj_digital_payments_budget",
                    "campaignName": "Digital Payments Launch",
                    "parishes": ["St James", "Manchester"],
                    "monthlyBudget": 1200000,
                    "spendToDate": 880000,
                    "projectedSpend": 1185000,
                    "pacingPercent": 0.95,
                    "startDate": "2024-08-15",
                    "endDate": "2024-10-05",
                },
            ],
            "parish": [
                {
                    "parish": "Kingston",
                    "spend": 1500000,
                    "impressions": 720000,
                    "clicks": 31800,
                    "conversions": 2050,
                    "roas": 4.0,
                    "campaignCount": 2,
                    "currency": "JMD",
                },
                {
                    "parish": "St Andrew",
                    "spend": 1100000,
                    "impressions": 520000,
                    "clicks": 23800,
                    "conversions": 1580,
                    "roas": 4.4,
                    "campaignCount": 2,
                    "currency": "JMD",
                },
                {
                    "parish": "St James",
                    "spend": 800000,
                    "impressions": 410000,
                    "clicks": 18900,
                    "conversions": 1350,
                    "roas": 4.1,
                    "campaignCount": 1,
                    "currency": "JMD",
                },
            ],
        },
    },
    "grace-kennedy": {
        "label": "GraceKennedy",
        "payload": {
            "campaign": {
                "summary": {
                    "currency": "USD",
                    "totalSpend": 310000,
                    "totalImpressions": 1450000,
                    "totalClicks": 92000,
                    "totalConversions": 7200,
                    "averageRoas": 5.1,
                },
                "trend": [
                    {
                        "date": "2024-09-01",
                        "spend": 98000,
                        "conversions": 2300,
                        "clicks": 31200,
                        "impressions": 480000,
                    },
                    {
                        "date": "2024-09-02",
                        "spend": 102000,
                        "conversions": 2400,
                        "clicks": 30500,
                        "impressions": 520000,
                    },
                    {
                        "date": "2024-09-03",
                        "spend": 110000,
                        "conversions": 2500,
                        "clicks": 30300,
                        "impressions": 450000,
                    },
                ],
                "rows": [
                    {
                        "id": "gk_foods_autumn",
                        "name": "Grace Foods Autumn Push",
                        "platform": "Meta",
                        "status": "Active",
                        "parish": "St Catherine",
                        "spend": 150000,
                        "impressions": 620000,
                        "clicks": 41000,
                        "conversions": 3200,
                        "roas": 4.7,
                        "ctr": 0.066,
                        "cpc": 3.65,
                        "cpm": 242.0,
                        "startDate": "2024-08-12",
                        "endDate": "2024-10-15",
                    },
                    {
                        "id": "gk_financial_services",
                        "name": "GK Money Services",
                        "platform": "Google Ads",
                        "status": "Active",
                        "parish": "Kingston",
                        "spend": 90000,
                        "impressions": 420000,
                        "clicks": 29500,
                        "conversions": 2100,
                        "roas": 5.6,
                        "ctr": 0.07,
                        "cpc": 3.05,
                        "cpm": 214.0,
                        "startDate": "2024-08-01",
                        "endDate": "2024-09-30",
                    },
                    {
                        "id": "gk_remittances",
                        "name": "Western Union Remittances",
                        "platform": "TikTok",
                        "status": "Active",
                        "parish": "St James",
                        "spend": 70000,
                        "impressions": 410000,
                        "clicks": 21500,
                        "conversions": 1900,
                        "roas": 5.1,
                        "ctr": 0.052,
                        "cpc": 3.25,
                        "cpm": 170.7,
                        "startDate": "2024-08-20",
                        "endDate": "2024-10-01",
                    },
                ],
            },
            "creative": [
                {
                    "id": "gk_autumn_recipe",
                    "name": "Autumn Recipe Series",
                    "campaignId": "gk_foods_autumn",
                    "campaignName": "Grace Foods Autumn Push",
                    "platform": "Meta",
                    "parish": "St Catherine",
                    "spend": 64000,
                    "impressions": 280000,
                    "clicks": 18600,
                    "conversions": 1340,
                    "roas": 4.3,
                    "ctr": 0.066,
                },
                {
                    "id": "gk_money_search",
                    "name": "Money Services Search",
                    "campaignId": "gk_financial_services",
                    "campaignName": "GK Money Services",
                    "platform": "Google Ads",
                    "parish": "Kingston",
                    "spend": 42000,
                    "impressions": 190000,
                    "clicks": 14100,
                    "conversions": 980,
                    "roas": 5.2,
                    "ctr": 0.074,
                },
            ],
            "budget": [
                {
                    "id": "gk_foods_budget",
                    "campaignName": "Grace Foods Autumn Push",
                    "parishes": ["St Catherine", "Clarendon"],
                    "monthlyBudget": 180000,
                    "spendToDate": 150000,
                    "projectedSpend": 176000,
                    "pacingPercent": 0.98,
                    "startDate": "2024-08-12",
                    "endDate": "2024-10-15",
                },
                {
                    "id": "gk_money_budget",
                    "campaignName": "GK Money Services",
                    "parishes": ["Kingston", "St Andrew"],
                    "monthlyBudget": 120000,
                    "spendToDate": 90000,
                    "projectedSpend": 118000,
                    "pacingPercent": 0.98,
                    "startDate": "2024-08-01",
                    "endDate": "2024-09-30",
                },
            ],
            "parish": [
                {
                    "parish": "St Catherine",
                    "spend": 160000,
                    "impressions": 650000,
                    "clicks": 43000,
                    "conversions": 3300,
                    "roas": 4.9,
                    "campaignCount": 2,
                    "currency": "USD",
                },
                {
                    "parish": "Kingston",
                    "spend": 90000,
                    "impressions": 420000,
                    "clicks": 29500,
                    "conversions": 2100,
                    "roas": 5.6,
                    "campaignCount": 1,
                    "currency": "USD",
                },
                {
                    "parish": "St James",
                    "spend": 60000,
                    "impressions": 380000,
                    "clicks": 19500,
                    "conversions": 1800,
                    "roas": 4.9,
                    "campaignCount": 1,
                    "currency": "USD",
                },
            ],
        },
    },
    "jdic": {
        "label": "JDIC",
        "payload": {
            "campaign": {
                "summary": {
                    "currency": "JMD",
                    "totalSpend": 1800000,
                    "totalImpressions": 920000,
                    "totalClicks": 51000,
                    "totalConversions": 3100,
                    "averageRoas": 3.7,
                },
                "trend": [
                    {
                        "date": "2024-09-01",
                        "spend": 320000,
                        "conversions": 520,
                        "clicks": 9200,
                        "impressions": 160000,
                    },
                    {
                        "date": "2024-09-02",
                        "spend": 290000,
                        "conversions": 500,
                        "clicks": 8900,
                        "impressions": 150000,
                    },
                    {
                        "date": "2024-09-03",
                        "spend": 310000,
                        "conversions": 540,
                        "clicks": 9300,
                        "impressions": 155000,
                    },
                ],
                "rows": [
                    {
                        "id": "jdic_depositor_protection",
                        "name": "Depositor Protection",
                        "platform": "Meta",
                        "status": "Active",
                        "parish": "Kingston",
                        "spend": 620000,
                        "impressions": 320000,
                        "clicks": 17800,
                        "conversions": 1050,
                        "roas": 3.4,
                        "ctr": 0.055,
                        "cpc": 34.8,
                        "cpm": 193.7,
                        "startDate": "2024-08-05",
                        "endDate": "2024-09-30",
                    },
                    {
                        "id": "jdic_fdic_comparison",
                        "name": "FDIC Comparison",
                        "platform": "Google Ads",
                        "status": "Active",
                        "parish": "St Andrew",
                        "spend": 560000,
                        "impressions": 280000,
                        "clicks": 17200,
                        "conversions": 980,
                        "roas": 3.9,
                        "ctr": 0.061,
                        "cpc": 32.6,
                        "cpm": 200.0,
                        "startDate": "2024-08-10",
                        "endDate": "2024-09-28",
                    },
                    {
                        "id": "jdic_youth_finance",
                        "name": "Youth Financial Literacy",
                        "platform": "TikTok",
                        "status": "Active",
                        "parish": "Manchester",
                        "spend": 420000,
                        "impressions": 320000,
                        "clicks": 16000,
                        "conversions": 1070,
                        "roas": 3.8,
                        "ctr": 0.05,
                        "cpc": 26.3,
                        "cpm": 131.3,
                        "startDate": "2024-08-15",
                        "endDate": "2024-09-30",
                    },
                ],
            },
            "creative": [
                {
                    "id": "jdic_depositor_video",
                    "name": "Depositor Video Story",
                    "campaignId": "jdic_depositor_protection",
                    "campaignName": "Depositor Protection",
                    "platform": "Meta",
                    "parish": "Kingston",
                    "spend": 240000,
                    "impressions": 140000,
                    "clicks": 7800,
                    "conversions": 480,
                    "roas": 3.3,
                    "ctr": 0.055,
                },
                {
                    "id": "jdic_youth_tiktok",
                    "name": "Youth Finance Tips",
                    "campaignId": "jdic_youth_finance",
                    "campaignName": "Youth Financial Literacy",
                    "platform": "TikTok",
                    "parish": "Manchester",
                    "spend": 180000,
                    "impressions": 135000,
                    "clicks": 6500,
                    "conversions": 420,
                    "roas": 3.6,
                    "ctr": 0.048,
                },
            ],
            "budget": [
                {
                    "id": "jdic_depositor_budget",
                    "campaignName": "Depositor Protection",
                    "parishes": ["Kingston", "St Andrew"],
                    "monthlyBudget": 750000,
                    "spendToDate": 620000,
                    "projectedSpend": 732000,
                    "pacingPercent": 0.98,
                    "startDate": "2024-08-05",
                    "endDate": "2024-09-30",
                },
                {
                    "id": "jdic_youth_budget",
                    "campaignName": "Youth Financial Literacy",
                    "parishes": ["Manchester", "St Elizabeth"],
                    "monthlyBudget": 500000,
                    "spendToDate": 420000,
                    "projectedSpend": 498000,
                    "pacingPercent": 0.996,
                    "startDate": "2024-08-15",
                    "endDate": "2024-09-30",
                },
            ],
            "parish": [
                {
                    "parish": "Kingston",
                    "spend": 630000,
                    "impressions": 330000,
                    "clicks": 18100,
                    "conversions": 1080,
                    "roas": 3.5,
                    "campaignCount": 2,
                    "currency": "JMD",
                },
                {
                    "parish": "St Andrew",
                    "spend": 560000,
                    "impressions": 285000,
                    "clicks": 17500,
                    "conversions": 1000,
                    "roas": 3.9,
                    "campaignCount": 1,
                    "currency": "JMD",
                },
                {
                    "parish": "Manchester",
                    "spend": 420000,
                    "impressions": 320000,
                    "clicks": 16000,
                    "conversions": 1070,
                    "roas": 3.8,
                    "campaignCount": 1,
                    "currency": "JMD",
                },
            ],
        },
    },
}

DEFAULT_DEMO_TENANT = "bank-of-jamaica"


class DemoAdapter(MetricsAdapter):
    """Serve curated demo datasets for showcase tenants."""

    key = "demo"
    name = "Demo Tenants"
    description = "Curated sample data for showcase tenants."
    interfaces: tuple[AdapterInterface, ...] = get_default_interfaces()

    def metadata(self) -> dict[str, Any]:
        meta = super().metadata()
        seeded = _load_seeded_demo_data(_demo_seed_dir())
        if seeded and seeded.tenant_order:
            meta["options"] = {
                "demo_tenants": [
                    {
                        "id": tenant_id,
                        "label": seeded.tenants[tenant_id]["tenant_name"],
                    }
                    for tenant_id in seeded.tenant_order
                ]
            }
        else:
            meta["options"] = {
                "demo_tenants": [
                    {"id": slug, "label": dataset["label"]}
                    for slug, dataset in DEMO_DATASETS.items()
                ]
            }
        return meta

    def fetch_metrics(
        self,
        *,
        tenant_id: str,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        slug = (
            str(options.get("demo_tenant"))  # type: ignore[call-arg]
            if options and "demo_tenant" in options
            else DEFAULT_DEMO_TENANT
        )
        seeded = _load_seeded_demo_data(_demo_seed_dir())
        if seeded:
            return _build_seeded_payload(seeded, slug, options)

        dataset = DEMO_DATASETS.get(slug) or DEMO_DATASETS[DEFAULT_DEMO_TENANT]
        payload = deepcopy(dataset["payload"])
        payload.setdefault("tenant_id", slug)
        payload.setdefault("tenant_label", dataset["label"])
        payload.setdefault("snapshot_generated_at", timezone.now().isoformat())
        return payload
