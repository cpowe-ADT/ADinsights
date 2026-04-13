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
            "parishes": [parish] if parish else ["Unknown"],
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
                "parishes": [parish] if parish else ["Unknown"],
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

    # --- Demographics demo data ---
    demographics = {
        "byAge": [
            {"ageRange": "18-24", "spend": 820.0, "impressions": 48200, "clicks": 1890, "conversions": 42, "reach": 31500},
            {"ageRange": "25-34", "spend": 2150.0, "impressions": 125800, "clicks": 5340, "conversions": 156, "reach": 82400},
            {"ageRange": "35-44", "spend": 1680.0, "impressions": 98500, "clicks": 3920, "conversions": 118, "reach": 64200},
            {"ageRange": "45-54", "spend": 890.0, "impressions": 52100, "clicks": 1780, "conversions": 48, "reach": 34100},
            {"ageRange": "55-64", "spend": 420.0, "impressions": 24600, "clicks": 680, "conversions": 15, "reach": 16100},
            {"ageRange": "65+", "spend": 180.0, "impressions": 10500, "clicks": 220, "conversions": 4, "reach": 6900},
        ],
        "byGender": [
            {"gender": "female", "spend": 3480.0, "impressions": 203800, "clicks": 8120, "conversions": 228, "reach": 133200},
            {"gender": "male", "spend": 2520.0, "impressions": 147600, "clicks": 5520, "conversions": 148, "reach": 96500},
            {"gender": "unknown", "spend": 140.0, "impressions": 8300, "clicks": 190, "conversions": 7, "reach": 5500},
        ],
        "byAgeGender": [
            {"ageRange": "18-24", "gender": "female", "spend": 480.0, "impressions": 28100, "clicks": 1120, "conversions": 26, "reach": 18400},
            {"ageRange": "18-24", "gender": "male", "spend": 340.0, "impressions": 20100, "clicks": 770, "conversions": 16, "reach": 13100},
            {"ageRange": "25-34", "gender": "female", "spend": 1250.0, "impressions": 73200, "clicks": 3180, "conversions": 96, "reach": 47900},
            {"ageRange": "25-34", "gender": "male", "spend": 900.0, "impressions": 52600, "clicks": 2160, "conversions": 60, "reach": 34500},
            {"ageRange": "35-44", "gender": "female", "spend": 980.0, "impressions": 57400, "clicks": 2340, "conversions": 72, "reach": 37400},
            {"ageRange": "35-44", "gender": "male", "spend": 700.0, "impressions": 41100, "clicks": 1580, "conversions": 46, "reach": 26800},
            {"ageRange": "45-54", "gender": "female", "spend": 520.0, "impressions": 30400, "clicks": 1060, "conversions": 29, "reach": 19900},
            {"ageRange": "45-54", "gender": "male", "spend": 370.0, "impressions": 21700, "clicks": 720, "conversions": 19, "reach": 14200},
            {"ageRange": "55-64", "gender": "female", "spend": 180.0, "impressions": 10500, "clicks": 310, "conversions": 4, "reach": 6900},
            {"ageRange": "55-64", "gender": "male", "spend": 240.0, "impressions": 14100, "clicks": 370, "conversions": 11, "reach": 9200},
            {"ageRange": "65+", "gender": "female", "spend": 70.0, "impressions": 4200, "clicks": 110, "conversions": 1, "reach": 2700},
            {"ageRange": "65+", "gender": "male", "spend": 110.0, "impressions": 6300, "clicks": 110, "conversions": 3, "reach": 4200},
        ],
    }

    # --- Platforms demo data ---
    platforms = {
        "byPlatform": [
            {"platform": "facebook", "spend": 3200.0, "impressions": 188500, "clicks": 6840, "conversions": 198, "reach": 123200},
            {"platform": "instagram", "spend": 2450.0, "impressions": 143600, "clicks": 5920, "conversions": 162, "reach": 93800},
            {"platform": "audience_network", "spend": 350.0, "impressions": 20500, "clicks": 680, "conversions": 15, "reach": 13400},
            {"platform": "messenger", "spend": 140.0, "impressions": 7100, "clicks": 390, "conversions": 8, "reach": 4800},
        ],
        "byDevice": [
            {"device": "mobile_app", "spend": 3850.0, "impressions": 225800, "clicks": 9120, "conversions": 258, "reach": 147600},
            {"device": "mobile_web", "spend": 1540.0, "impressions": 90200, "clicks": 3280, "conversions": 86, "reach": 59000},
            {"device": "desktop", "spend": 750.0, "impressions": 43700, "clicks": 1430, "conversions": 39, "reach": 28600},
        ],
        "byPlatformDevice": [
            {"platform": "facebook", "device": "mobile_app", "spend": 1920.0, "impressions": 112800, "clicks": 4100, "conversions": 120, "reach": 73800},
            {"platform": "facebook", "device": "mobile_web", "spend": 830.0, "impressions": 48700, "clicks": 1780, "conversions": 51, "reach": 31800},
            {"platform": "facebook", "device": "desktop", "spend": 450.0, "impressions": 27000, "clicks": 960, "conversions": 27, "reach": 17600},
            {"platform": "instagram", "device": "mobile_app", "spend": 1680.0, "impressions": 98400, "clicks": 4280, "conversions": 118, "reach": 64300},
            {"platform": "instagram", "device": "mobile_web", "spend": 570.0, "impressions": 33400, "clicks": 1220, "conversions": 32, "reach": 21800},
            {"platform": "instagram", "device": "desktop", "spend": 200.0, "impressions": 11800, "clicks": 420, "conversions": 12, "reach": 7700},
            {"platform": "audience_network", "device": "mobile_app", "spend": 250.0, "impressions": 14600, "clicks": 480, "conversions": 12, "reach": 9500},
            {"platform": "audience_network", "device": "mobile_web", "spend": 100.0, "impressions": 5900, "clicks": 200, "conversions": 3, "reach": 3900},
            {"platform": "messenger", "device": "mobile_app", "spend": 140.0, "impressions": 7100, "clicks": 390, "conversions": 8, "reach": 4800},
        ],
    }

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
        "demographics": demographics,
        "platforms": platforms,
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
                        "parishes": ["Kingston"],
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
                        "parishes": ["St Andrew"],
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
                        "parishes": ["St James"],
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
                    "parishes": ["Kingston"],
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
                    "parishes": ["St Andrew"],
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
            "demographics": {
                "byAge": [
                    {"ageRange": "18-24", "spend": 580000.0, "impressions": 255000, "clicks": 11900, "conversions": 740, "reach": 166500},
                    {"ageRange": "25-34", "spend": 1520000.0, "impressions": 666000, "clicks": 31000, "conversions": 1940, "reach": 435600},
                    {"ageRange": "35-44", "spend": 1180000.0, "impressions": 518000, "clicks": 24200, "conversions": 1510, "reach": 338800},
                    {"ageRange": "45-54", "spend": 520000.0, "impressions": 228000, "clicks": 10600, "conversions": 540, "reach": 149100},
                    {"ageRange": "55-64", "spend": 260000.0, "impressions": 114000, "clicks": 5300, "conversions": 190, "reach": 74500},
                    {"ageRange": "65+", "spend": 140000.0, "impressions": 69000, "clicks": 3000, "conversions": 80, "reach": 45100},
                ],
                "byGender": [
                    {"gender": "female", "spend": 2420000.0, "impressions": 1065000, "clicks": 49600, "conversions": 2920, "reach": 696400},
                    {"gender": "male", "spend": 1680000.0, "impressions": 740000, "clicks": 34500, "conversions": 2380, "reach": 483900},
                    {"gender": "unknown", "spend": 100000.0, "impressions": 45000, "clicks": 1900, "conversions": 100, "reach": 29400},
                ],
                "byAgeGender": [
                    {"ageRange": "18-24", "gender": "female", "spend": 340000.0, "impressions": 149000, "clicks": 7000, "conversions": 440, "reach": 97200},
                    {"ageRange": "18-24", "gender": "male", "spend": 240000.0, "impressions": 106000, "clicks": 4900, "conversions": 300, "reach": 69300},
                    {"ageRange": "25-34", "gender": "female", "spend": 880000.0, "impressions": 388000, "clicks": 18100, "conversions": 1140, "reach": 253800},
                    {"ageRange": "25-34", "gender": "male", "spend": 640000.0, "impressions": 278000, "clicks": 12900, "conversions": 800, "reach": 181800},
                    {"ageRange": "35-44", "gender": "female", "spend": 690000.0, "impressions": 302000, "clicks": 14100, "conversions": 890, "reach": 197500},
                    {"ageRange": "35-44", "gender": "male", "spend": 490000.0, "impressions": 216000, "clicks": 10100, "conversions": 620, "reach": 141300},
                    {"ageRange": "45-54", "gender": "female", "spend": 300000.0, "impressions": 133000, "clicks": 6200, "conversions": 310, "reach": 86900},
                    {"ageRange": "45-54", "gender": "male", "spend": 220000.0, "impressions": 95000, "clicks": 4400, "conversions": 230, "reach": 62200},
                    {"ageRange": "55-64", "gender": "female", "spend": 150000.0, "impressions": 66000, "clicks": 3100, "conversions": 100, "reach": 43100},
                    {"ageRange": "55-64", "gender": "male", "spend": 110000.0, "impressions": 48000, "clicks": 2200, "conversions": 90, "reach": 31400},
                    {"ageRange": "65+", "gender": "female", "spend": 60000.0, "impressions": 27000, "clicks": 1100, "conversions": 40, "reach": 17900},
                    {"ageRange": "65+", "gender": "male", "spend": 80000.0, "impressions": 42000, "clicks": 1900, "conversions": 40, "reach": 27200},
                ],
            },
            "platforms": {
                "byPlatform": [
                    {"platform": "facebook", "spend": 2240000.0, "impressions": 990000, "clicks": 46100, "conversions": 2880, "reach": 646800},
                    {"platform": "instagram", "spend": 1520000.0, "impressions": 666000, "clicks": 31000, "conversions": 1940, "reach": 435600},
                    {"platform": "audience_network", "spend": 280000.0, "impressions": 124000, "clicks": 5800, "conversions": 360, "reach": 81100},
                    {"platform": "messenger", "spend": 160000.0, "impressions": 70000, "clicks": 3100, "conversions": 120, "reach": 46200},
                ],
                "byDevice": [
                    {"device": "mobile_app", "spend": 2640000.0, "impressions": 1160000, "clicks": 54100, "conversions": 3380, "reach": 758200},
                    {"device": "mobile_web", "spend": 1060000.0, "impressions": 462000, "clicks": 21500, "conversions": 1350, "reach": 302200},
                    {"device": "desktop", "spend": 500000.0, "impressions": 228000, "clicks": 10400, "conversions": 570, "reach": 149300},
                ],
                "byPlatformDevice": [
                    {"platform": "facebook", "device": "mobile_app", "spend": 1340000.0, "impressions": 594000, "clicks": 27600, "conversions": 1730, "reach": 388100},
                    {"platform": "facebook", "device": "mobile_web", "spend": 580000.0, "impressions": 257000, "clicks": 12000, "conversions": 750, "reach": 168100},
                    {"platform": "facebook", "device": "desktop", "spend": 320000.0, "impressions": 139000, "clicks": 6500, "conversions": 400, "reach": 90600},
                    {"platform": "instagram", "device": "mobile_app", "spend": 1060000.0, "impressions": 466000, "clicks": 21700, "conversions": 1360, "reach": 304700},
                    {"platform": "instagram", "device": "mobile_web", "spend": 340000.0, "impressions": 147000, "clicks": 6800, "conversions": 430, "reach": 96100},
                    {"platform": "instagram", "device": "desktop", "spend": 120000.0, "impressions": 53000, "clicks": 2500, "conversions": 150, "reach": 34800},
                    {"platform": "audience_network", "device": "mobile_app", "spend": 200000.0, "impressions": 86000, "clicks": 4000, "conversions": 250, "reach": 56200},
                    {"platform": "audience_network", "device": "mobile_web", "spend": 80000.0, "impressions": 38000, "clicks": 1800, "conversions": 110, "reach": 24900},
                    {"platform": "messenger", "device": "mobile_app", "spend": 160000.0, "impressions": 70000, "clicks": 3100, "conversions": 120, "reach": 46200},
                ],
            },
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
                        "parishes": ["St Catherine"],
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
                        "parishes": ["Kingston"],
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
                        "parishes": ["St James"],
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
                    "parishes": ["St Catherine"],
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
                    "parishes": ["Kingston"],
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
            "demographics": {
                "byAge": [
                    {"ageRange": "18-24", "spend": 42000.0, "impressions": 195000, "clicks": 12400, "conversions": 970, "reach": 127400},
                    {"ageRange": "25-34", "spend": 110000.0, "impressions": 520000, "clicks": 33000, "conversions": 2590, "reach": 340000},
                    {"ageRange": "35-44", "spend": 86000.0, "impressions": 400000, "clicks": 25500, "conversions": 2000, "reach": 261500},
                    {"ageRange": "45-54", "spend": 43000.0, "impressions": 200000, "clicks": 12700, "conversions": 1000, "reach": 130800},
                    {"ageRange": "55-64", "spend": 20000.0, "impressions": 95000, "clicks": 6000, "conversions": 470, "reach": 62100},
                    {"ageRange": "65+", "spend": 9000.0, "impressions": 40000, "clicks": 2400, "conversions": 170, "reach": 26100},
                ],
                "byGender": [
                    {"gender": "female", "spend": 176000.0, "impressions": 826000, "clicks": 52400, "conversions": 4100, "reach": 539600},
                    {"gender": "male", "spend": 124000.0, "impressions": 580000, "clicks": 36800, "conversions": 2890, "reach": 379200},
                    {"gender": "unknown", "spend": 10000.0, "impressions": 44000, "clicks": 2800, "conversions": 210, "reach": 28800},
                ],
                "byAgeGender": [
                    {"ageRange": "18-24", "gender": "female", "spend": 24000.0, "impressions": 114000, "clicks": 7200, "conversions": 570, "reach": 74400},
                    {"ageRange": "18-24", "gender": "male", "spend": 18000.0, "impressions": 81000, "clicks": 5200, "conversions": 400, "reach": 53000},
                    {"ageRange": "25-34", "gender": "female", "spend": 63000.0, "impressions": 304000, "clicks": 19200, "conversions": 1510, "reach": 198600},
                    {"ageRange": "25-34", "gender": "male", "spend": 47000.0, "impressions": 216000, "clicks": 13800, "conversions": 1080, "reach": 141400},
                    {"ageRange": "35-44", "gender": "female", "spend": 50000.0, "impressions": 233000, "clicks": 14900, "conversions": 1170, "reach": 152400},
                    {"ageRange": "35-44", "gender": "male", "spend": 36000.0, "impressions": 167000, "clicks": 10600, "conversions": 830, "reach": 109100},
                    {"ageRange": "45-54", "gender": "female", "spend": 25000.0, "impressions": 117000, "clicks": 7400, "conversions": 580, "reach": 76500},
                    {"ageRange": "45-54", "gender": "male", "spend": 18000.0, "impressions": 83000, "clicks": 5300, "conversions": 420, "reach": 54300},
                    {"ageRange": "55-64", "gender": "female", "spend": 10000.0, "impressions": 42000, "clicks": 2700, "conversions": 200, "reach": 27500},
                    {"ageRange": "55-64", "gender": "male", "spend": 10000.0, "impressions": 53000, "clicks": 3300, "conversions": 270, "reach": 34600},
                    {"ageRange": "65+", "gender": "female", "spend": 4000.0, "impressions": 16000, "clicks": 1000, "conversions": 70, "reach": 10200},
                    {"ageRange": "65+", "gender": "male", "spend": 5000.0, "impressions": 24000, "clicks": 1400, "conversions": 100, "reach": 15900},
                ],
            },
            "platforms": {
                "byPlatform": [
                    {"platform": "facebook", "spend": 164000.0, "impressions": 760000, "clicks": 48300, "conversions": 3790, "reach": 496800},
                    {"platform": "instagram", "spend": 108000.0, "impressions": 510000, "clicks": 32400, "conversions": 2540, "reach": 333500},
                    {"platform": "audience_network", "spend": 24000.0, "impressions": 116000, "clicks": 7300, "conversions": 580, "reach": 75800},
                    {"platform": "messenger", "spend": 14000.0, "impressions": 64000, "clicks": 4000, "conversions": 290, "reach": 41700},
                ],
                "byDevice": [
                    {"device": "mobile_app", "spend": 195000.0, "impressions": 913000, "clicks": 58000, "conversions": 4560, "reach": 596800},
                    {"device": "mobile_web", "spend": 77000.0, "impressions": 363000, "clicks": 23000, "conversions": 1810, "reach": 237400},
                    {"device": "desktop", "spend": 38000.0, "impressions": 174000, "clicks": 11000, "conversions": 830, "reach": 113600},
                ],
                "byPlatformDevice": [
                    {"platform": "facebook", "device": "mobile_app", "spend": 98000.0, "impressions": 456000, "clicks": 29000, "conversions": 2280, "reach": 298100},
                    {"platform": "facebook", "device": "mobile_web", "spend": 43000.0, "impressions": 197000, "clicks": 12500, "conversions": 990, "reach": 128800},
                    {"platform": "facebook", "device": "desktop", "spend": 23000.0, "impressions": 107000, "clicks": 6800, "conversions": 520, "reach": 69900},
                    {"platform": "instagram", "device": "mobile_app", "spend": 76000.0, "impressions": 357000, "clicks": 22700, "conversions": 1780, "reach": 233400},
                    {"platform": "instagram", "device": "mobile_web", "spend": 23000.0, "impressions": 112000, "clicks": 7100, "conversions": 560, "reach": 73200},
                    {"platform": "instagram", "device": "desktop", "spend": 9000.0, "impressions": 41000, "clicks": 2600, "conversions": 200, "reach": 26900},
                    {"platform": "audience_network", "device": "mobile_app", "spend": 17000.0, "impressions": 80000, "clicks": 5000, "conversions": 400, "reach": 52300},
                    {"platform": "audience_network", "device": "mobile_web", "spend": 7000.0, "impressions": 36000, "clicks": 2300, "conversions": 180, "reach": 23500},
                    {"platform": "messenger", "device": "mobile_app", "spend": 14000.0, "impressions": 64000, "clicks": 4000, "conversions": 290, "reach": 41700},
                ],
            },
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
                        "parishes": ["Kingston"],
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
                        "parishes": ["St Andrew"],
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
                        "parishes": ["Manchester"],
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
                    "parishes": ["Kingston"],
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
                    "parishes": ["Manchester"],
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
            "demographics": {
                "byAge": [
                    {"ageRange": "18-24", "spend": 250000.0, "impressions": 128000, "clicks": 7100, "conversions": 430, "reach": 83500},
                    {"ageRange": "25-34", "spend": 640000.0, "impressions": 330000, "clicks": 18300, "conversions": 1120, "reach": 215600},
                    {"ageRange": "35-44", "spend": 500000.0, "impressions": 258000, "clicks": 14300, "conversions": 870, "reach": 168400},
                    {"ageRange": "45-54", "spend": 240000.0, "impressions": 120000, "clicks": 6600, "conversions": 400, "reach": 78400},
                    {"ageRange": "55-64", "spend": 120000.0, "impressions": 60000, "clicks": 3300, "conversions": 200, "reach": 39200},
                    {"ageRange": "65+", "spend": 50000.0, "impressions": 24000, "clicks": 1400, "conversions": 80, "reach": 15700},
                ],
                "byGender": [
                    {"gender": "female", "spend": 1020000.0, "impressions": 524000, "clicks": 29100, "conversions": 1770, "reach": 342200},
                    {"gender": "male", "spend": 720000.0, "impressions": 368000, "clicks": 20400, "conversions": 1240, "reach": 240300},
                    {"gender": "unknown", "spend": 60000.0, "impressions": 28000, "clicks": 1500, "conversions": 90, "reach": 18300},
                ],
                "byAgeGender": [
                    {"ageRange": "18-24", "gender": "female", "spend": 145000.0, "impressions": 74500, "clicks": 4100, "conversions": 250, "reach": 48600},
                    {"ageRange": "18-24", "gender": "male", "spend": 105000.0, "impressions": 53500, "clicks": 3000, "conversions": 180, "reach": 34900},
                    {"ageRange": "25-34", "gender": "female", "spend": 370000.0, "impressions": 192000, "clicks": 10600, "conversions": 650, "reach": 125300},
                    {"ageRange": "25-34", "gender": "male", "spend": 270000.0, "impressions": 138000, "clicks": 7700, "conversions": 470, "reach": 90300},
                    {"ageRange": "35-44", "gender": "female", "spend": 290000.0, "impressions": 150000, "clicks": 8300, "conversions": 510, "reach": 98000},
                    {"ageRange": "35-44", "gender": "male", "spend": 210000.0, "impressions": 108000, "clicks": 6000, "conversions": 360, "reach": 70400},
                    {"ageRange": "45-54", "gender": "female", "spend": 140000.0, "impressions": 70000, "clicks": 3800, "conversions": 230, "reach": 45700},
                    {"ageRange": "45-54", "gender": "male", "spend": 100000.0, "impressions": 50000, "clicks": 2800, "conversions": 170, "reach": 32700},
                    {"ageRange": "55-64", "gender": "female", "spend": 55000.0, "impressions": 26000, "clicks": 1700, "conversions": 90, "reach": 17000},
                    {"ageRange": "55-64", "gender": "male", "spend": 65000.0, "impressions": 34000, "clicks": 1600, "conversions": 110, "reach": 22200},
                    {"ageRange": "65+", "gender": "female", "spend": 20000.0, "impressions": 11500, "clicks": 600, "conversions": 40, "reach": 7600},
                    {"ageRange": "65+", "gender": "male", "spend": 30000.0, "impressions": 12500, "clicks": 800, "conversions": 40, "reach": 8100},
                ],
            },
            "platforms": {
                "byPlatform": [
                    {"platform": "facebook", "spend": 960000.0, "impressions": 496000, "clicks": 27500, "conversions": 1670, "reach": 323800},
                    {"platform": "instagram", "spend": 580000.0, "impressions": 296000, "clicks": 16400, "conversions": 1000, "reach": 193300},
                    {"platform": "audience_network", "spend": 160000.0, "impressions": 82000, "clicks": 4500, "conversions": 280, "reach": 53500},
                    {"platform": "messenger", "spend": 100000.0, "impressions": 46000, "clicks": 2600, "conversions": 150, "reach": 30200},
                ],
                "byDevice": [
                    {"device": "mobile_app", "spend": 1140000.0, "impressions": 588000, "clicks": 32600, "conversions": 1980, "reach": 383800},
                    {"device": "mobile_web", "spend": 440000.0, "impressions": 228000, "clicks": 12600, "conversions": 770, "reach": 148800},
                    {"device": "desktop", "spend": 220000.0, "impressions": 104000, "clicks": 5800, "conversions": 350, "reach": 67900},
                ],
                "byPlatformDevice": [
                    {"platform": "facebook", "device": "mobile_app", "spend": 576000.0, "impressions": 298000, "clicks": 16500, "conversions": 1000, "reach": 194300},
                    {"platform": "facebook", "device": "mobile_web", "spend": 250000.0, "impressions": 128000, "clicks": 7100, "conversions": 440, "reach": 83600},
                    {"platform": "facebook", "device": "desktop", "spend": 134000.0, "impressions": 70000, "clicks": 3900, "conversions": 230, "reach": 45900},
                    {"platform": "instagram", "device": "mobile_app", "spend": 406000.0, "impressions": 207000, "clicks": 11500, "conversions": 700, "reach": 135300},
                    {"platform": "instagram", "device": "mobile_web", "spend": 120000.0, "impressions": 62000, "clicks": 3400, "conversions": 210, "reach": 40500},
                    {"platform": "instagram", "device": "desktop", "spend": 54000.0, "impressions": 27000, "clicks": 1500, "conversions": 90, "reach": 17500},
                    {"platform": "audience_network", "device": "mobile_app", "spend": 112000.0, "impressions": 57000, "clicks": 3200, "conversions": 200, "reach": 37200},
                    {"platform": "audience_network", "device": "mobile_web", "spend": 48000.0, "impressions": 25000, "clicks": 1300, "conversions": 80, "reach": 16300},
                    {"platform": "messenger", "device": "mobile_app", "spend": 100000.0, "impressions": 46000, "clicks": 2600, "conversions": 150, "reach": 30200},
                ],
            },
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
