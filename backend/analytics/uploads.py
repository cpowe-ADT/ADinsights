"""CSV upload parsing and aggregation helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from django.utils import timezone


@dataclass(frozen=True)
class UploadParseResult:
    rows: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]


REQUIRED_CAMPAIGN_COLUMNS = (
    "date",
    "campaign_id",
    "campaign_name",
    "platform",
    "spend",
    "impressions",
    "clicks",
    "conversions",
)

REQUIRED_PARISH_COLUMNS = ("parish", "spend", "impressions", "clicks", "conversions")

REQUIRED_BUDGET_COLUMNS = ("month", "campaign_name", "planned_budget")


COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "day", "date_day"),
    "campaign_id": ("campaign_id", "campaignid", "campaign id", "campaign"),
    "campaign_name": ("campaign_name", "campaignname", "campaign name", "name"),
    "platform": ("platform", "channel", "source", "source_platform"),
    "parish": ("parish", "parish_name"),
    "spend": ("spend", "cost"),
    "impressions": ("impressions",),
    "clicks": ("clicks",),
    "conversions": ("conversions",),
    "revenue": ("revenue", "conversion_value", "conversion value"),
    "roas": ("roas",),
    "status": ("status",),
    "objective": ("objective",),
    "start_date": ("start_date", "start date"),
    "end_date": ("end_date", "end date"),
    "currency": ("currency",),
    "campaign_count": ("campaign_count", "campaign count"),
    "month": ("month", "period", "date"),
    "planned_budget": ("planned_budget", "monthly_budget", "budget", "planned"),
    "spend_to_date": ("spend_to_date", "spend to date"),
    "projected_spend": ("projected_spend", "projected spend", "forecast_spend"),
    "pacing_percent": ("pacing_percent", "pacing", "pacing percent"),
    "parishes": ("parishes", "parish_list", "parish list"),
}


def _normalize_header(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("/", "_")
        .replace("&", "and")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _resolve_column(headers: Iterable[str], column_key: str) -> str | None:
    normalized = {_normalize_header(header): header for header in headers}
    aliases = COLUMN_ALIASES.get(column_key, (column_key,))
    for alias in aliases:
        key = _normalize_header(alias)
        if key in normalized:
            return normalized[key]
    return None


def _parse_number(value: str, errors: list[str], field: str, row_index: int) -> float | None:
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        errors.append(f"Row {row_index}: {field} is required.")
        return None
    try:
        return float(cleaned)
    except ValueError:
        errors.append(f"Row {row_index}: {field} is invalid.")
        return None


def _parse_optional_number(value: str) -> float | None:
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        if len(cleaned) == 10:
            datetime.strptime(cleaned, "%Y-%m-%d")
            return cleaned
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    return parsed.date().isoformat()


def _parse_month(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) == 7:
        return f"{cleaned}-01"
    parsed = _parse_date(cleaned)
    if parsed:
        return f"{parsed[:7]}-01"
    return None


def _end_of_month(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    if parsed.month == 12:
        end = parsed.replace(year=parsed.year + 1, month=1, day=1)
    else:
        end = parsed.replace(month=parsed.month + 1, day=1)
    end = end - timedelta(days=1)
    return end.date().isoformat()


def _parse_csv(file_obj) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader((line.decode("utf-8") for line in file_obj.readlines()))
    headers = reader.fieldnames or []
    rows = [row for row in reader]
    return headers, rows


def _build_missing_column_errors(headers: list[str], required: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for column in required:
        if _resolve_column(headers, column) is None:
            errors.append(f"Missing required column: {column}")
    return errors


def parse_campaign_csv(file_obj) -> UploadParseResult:
    errors: list[str] = []
    warnings: list[str] = []
    headers, rows = _parse_csv(file_obj)
    errors.extend(_build_missing_column_errors(headers, REQUIRED_CAMPAIGN_COLUMNS))
    if not rows:
        errors.append("CSV file has no data rows.")
    if errors:
        return UploadParseResult([], errors, warnings)

    parsed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        date_header = _resolve_column(headers, "date")
        date_value = _parse_date(row.get(date_header or "", ""))
        if not date_value:
            errors.append(f"Row {index}: date is invalid.")
            continue

        campaign_id = (row.get(_resolve_column(headers, "campaign_id") or "", "") or "").strip()
        campaign_name = (
            row.get(_resolve_column(headers, "campaign_name") or "", "") or ""
        ).strip()
        if not campaign_id or not campaign_name:
            errors.append(f"Row {index}: campaign_id and campaign_name are required.")
            continue

        spend = _parse_number(
            row.get(_resolve_column(headers, "spend") or "", ""),
            errors,
            "spend",
            index,
        )
        impressions = _parse_number(
            row.get(_resolve_column(headers, "impressions") or "", ""),
            errors,
            "impressions",
            index,
        )
        clicks = _parse_number(
            row.get(_resolve_column(headers, "clicks") or "", ""),
            errors,
            "clicks",
            index,
        )
        conversions = _parse_number(
            row.get(_resolve_column(headers, "conversions") or "", ""),
            errors,
            "conversions",
            index,
        )
        if None in (spend, impressions, clicks, conversions):
            continue

        parish = (row.get(_resolve_column(headers, "parish") or "", "") or "").strip() or None
        if not parish:
            warnings.append(f"Row {index}: parish missing. Using 'Unknown'.")

        parsed_rows.append(
            {
                "date": date_value,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "platform": (row.get(_resolve_column(headers, "platform") or "", "") or "").strip()
                or "Unknown",
                "parish": parish or "Unknown",
                "spend": float(spend),
                "impressions": float(impressions),
                "clicks": float(clicks),
                "conversions": float(conversions),
                "revenue": _parse_optional_number(
                    row.get(_resolve_column(headers, "revenue") or "", "") or ""
                ),
                "roas": _parse_optional_number(
                    row.get(_resolve_column(headers, "roas") or "", "") or ""
                ),
                "status": (row.get(_resolve_column(headers, "status") or "", "") or "").strip()
                or None,
                "objective": (
                    row.get(_resolve_column(headers, "objective") or "", "") or ""
                ).strip()
                or None,
                "start_date": _parse_date(
                    row.get(_resolve_column(headers, "start_date") or "", "") or ""
                ),
                "end_date": _parse_date(
                    row.get(_resolve_column(headers, "end_date") or "", "") or ""
                ),
                "currency": (row.get(_resolve_column(headers, "currency") or "", "") or "").strip()
                or None,
            }
        )

    return UploadParseResult(parsed_rows, errors, warnings)


def parse_parish_csv(file_obj) -> UploadParseResult:
    errors: list[str] = []
    warnings: list[str] = []
    headers, rows = _parse_csv(file_obj)
    errors.extend(_build_missing_column_errors(headers, REQUIRED_PARISH_COLUMNS))
    if not rows:
        errors.append("CSV file has no data rows.")
    if errors:
        return UploadParseResult([], errors, warnings)

    parsed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        parish = (row.get(_resolve_column(headers, "parish") or "", "") or "").strip()
        if not parish:
            errors.append(f"Row {index}: parish is required.")
            continue

        spend = _parse_number(
            row.get(_resolve_column(headers, "spend") or "", ""),
            errors,
            "spend",
            index,
        )
        impressions = _parse_number(
            row.get(_resolve_column(headers, "impressions") or "", ""),
            errors,
            "impressions",
            index,
        )
        clicks = _parse_number(
            row.get(_resolve_column(headers, "clicks") or "", ""),
            errors,
            "clicks",
            index,
        )
        conversions = _parse_number(
            row.get(_resolve_column(headers, "conversions") or "", ""),
            errors,
            "conversions",
            index,
        )
        if None in (spend, impressions, clicks, conversions):
            continue

        parsed_rows.append(
            {
                "date": _parse_date(row.get(_resolve_column(headers, "date") or "", "") or ""),
                "parish": parish,
                "spend": float(spend),
                "impressions": float(impressions),
                "clicks": float(clicks),
                "conversions": float(conversions),
                "revenue": _parse_optional_number(
                    row.get(_resolve_column(headers, "revenue") or "", "") or ""
                ),
                "roas": _parse_optional_number(
                    row.get(_resolve_column(headers, "roas") or "", "") or ""
                ),
                "campaign_count": _parse_optional_number(
                    row.get(_resolve_column(headers, "campaign_count") or "", "") or ""
                ),
                "currency": (row.get(_resolve_column(headers, "currency") or "", "") or "").strip()
                or None,
            }
        )

    return UploadParseResult(parsed_rows, errors, warnings)


def parse_budget_csv(file_obj) -> UploadParseResult:
    errors: list[str] = []
    warnings: list[str] = []
    headers, rows = _parse_csv(file_obj)
    errors.extend(_build_missing_column_errors(headers, REQUIRED_BUDGET_COLUMNS))
    if not rows:
        errors.append("CSV file has no data rows.")
    if errors:
        return UploadParseResult([], errors, warnings)

    parsed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        month = _parse_month(row.get(_resolve_column(headers, "month") or "", "") or "")
        if not month:
            errors.append(f"Row {index}: month is invalid.")
            continue

        campaign_name = (
            row.get(_resolve_column(headers, "campaign_name") or "", "") or ""
        ).strip()
        if not campaign_name:
            errors.append(f"Row {index}: campaign_name is required.")
            continue

        planned_budget = _parse_number(
            row.get(_resolve_column(headers, "planned_budget") or "", ""),
            errors,
            "planned_budget",
            index,
        )
        if planned_budget is None:
            continue

        parishes_raw = (row.get(_resolve_column(headers, "parishes") or "", "") or "").strip()
        parishes = [value.strip() for value in parishes_raw.split(",") if value.strip()]

        parsed_rows.append(
            {
                "month": month,
                "campaign_name": campaign_name,
                "planned_budget": float(planned_budget),
                "spend_to_date": _parse_optional_number(
                    row.get(_resolve_column(headers, "spend_to_date") or "", "") or ""
                ),
                "projected_spend": _parse_optional_number(
                    row.get(_resolve_column(headers, "projected_spend") or "", "") or ""
                ),
                "pacing_percent": _parse_optional_number(
                    row.get(_resolve_column(headers, "pacing_percent") or "", "") or ""
                ),
                "parishes": parishes or None,
                "platform": (row.get(_resolve_column(headers, "platform") or "", "") or "").strip()
                or None,
            }
        )

    return UploadParseResult(parsed_rows, errors, warnings)


def build_combined_payload(
    *,
    campaign_rows: list[dict[str, Any]],
    parish_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
    uploaded_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (uploaded_at or timezone.now()).isoformat()
    currency = "JMD"
    for row in campaign_rows + parish_rows:
        candidate = (row.get("currency") or "").strip()
        if candidate:
            currency = candidate.upper()
            break

    totals = {"spend": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0}
    revenue_total = 0.0
    trend: dict[str, dict[str, float]] = {}
    campaign_map: dict[str, dict[str, Any]] = {}
    campaign_revenue: dict[str, float] = {}

    for row in campaign_rows:
        totals["spend"] += row["spend"]
        totals["impressions"] += row["impressions"]
        totals["clicks"] += row["clicks"]
        totals["conversions"] += row["conversions"]
        revenue = row.get("revenue")
        if revenue is None and row.get("roas") is not None:
            revenue = row["roas"] * row["spend"]
        revenue_total += revenue or 0.0

        entry = trend.setdefault(
            row["date"],
            {"spend": 0.0, "conversions": 0.0, "clicks": 0.0, "impressions": 0.0},
        )
        entry["spend"] += row["spend"]
        entry["conversions"] += row["conversions"]
        entry["clicks"] += row["clicks"]
        entry["impressions"] += row["impressions"]

        campaign_id = row["campaign_id"]
        campaign_entry = campaign_map.get(campaign_id)
        if campaign_entry is None:
            campaign_entry = {
                "id": campaign_id,
                "name": row["campaign_name"],
                "platform": row["platform"],
                "status": row.get("status") or "Active",
                "objective": row.get("objective"),
                "parish": row.get("parish") or "Unknown",
                "spend": 0.0,
                "impressions": 0.0,
                "clicks": 0.0,
                "conversions": 0.0,
                "roas": 0.0,
                "ctr": 0.0,
                "cpc": 0.0,
                "cpm": 0.0,
                "startDate": row.get("start_date") or row["date"],
                "endDate": row.get("end_date") or row["date"],
            }
            campaign_map[campaign_id] = campaign_entry
            campaign_revenue[campaign_id] = 0.0

        campaign_entry["spend"] += row["spend"]
        campaign_entry["impressions"] += row["impressions"]
        campaign_entry["clicks"] += row["clicks"]
        campaign_entry["conversions"] += row["conversions"]
        campaign_revenue[campaign_id] += revenue or 0.0
        if campaign_entry["spend"] > 0:
            campaign_entry["roas"] = campaign_revenue[campaign_id] / campaign_entry["spend"]
        if campaign_entry["impressions"] > 0:
            campaign_entry["ctr"] = campaign_entry["clicks"] / campaign_entry["impressions"]
            campaign_entry["cpm"] = (campaign_entry["spend"] / campaign_entry["impressions"]) * 1000
        if campaign_entry["clicks"] > 0:
            campaign_entry["cpc"] = campaign_entry["spend"] / campaign_entry["clicks"]
        if row["date"] < campaign_entry["startDate"]:
            campaign_entry["startDate"] = row["date"]
        if row["date"] > campaign_entry["endDate"]:
            campaign_entry["endDate"] = row["date"]

    trend_rows = [
        {"date": date, **values} for date, values in sorted(trend.items(), key=lambda item: item[0])
    ]
    campaign_rows_output = list(campaign_map.values())

    if parish_rows:
        parish_source = parish_rows
    else:
        parish_source = [
            {
                "parish": row.get("parish") or "Unknown",
                "spend": row["spend"],
                "impressions": row["impressions"],
                "clicks": row["clicks"],
                "conversions": row["conversions"],
                "revenue": row.get("revenue"),
                "campaign_id": row["campaign_id"],
                "currency": row.get("currency"),
            }
            for row in campaign_rows
        ]

    parish_map: dict[str, dict[str, Any]] = {}
    parish_campaigns: dict[str, set[str]] = {}
    parish_revenue: dict[str, float] = {}
    for row in parish_source:
        parish_name = row["parish"]
        entry = parish_map.get(parish_name)
        if entry is None:
            entry = {
                "parish": parish_name,
                "spend": 0.0,
                "impressions": 0.0,
                "clicks": 0.0,
                "conversions": 0.0,
                "roas": 0.0,
                "campaignCount": 0,
                "currency": currency,
            }
            parish_map[parish_name] = entry
            parish_revenue[parish_name] = 0.0

        entry["spend"] += row["spend"]
        entry["impressions"] += row["impressions"]
        entry["clicks"] += row["clicks"]
        entry["conversions"] += row["conversions"]
        parish_revenue[parish_name] += row.get("revenue") or 0.0
        if entry["spend"] > 0:
            entry["roas"] = parish_revenue[parish_name] / entry["spend"]

        campaign_id = row.get("campaign_id")
        if campaign_id:
            parish_campaigns.setdefault(parish_name, set()).add(campaign_id)
            entry["campaignCount"] = len(parish_campaigns[parish_name])
        elif row.get("campaign_count") is not None:
            entry["campaignCount"] = row["campaign_count"]

    parish_rows_output = list(parish_map.values())

    budget_output: list[dict[str, Any]] = []
    for row in budget_rows:
        month_start = row["month"]
        month_end = _end_of_month(month_start)
        spend_to_date = row.get("spend_to_date")
        if spend_to_date is None:
            spend_to_date = sum(
                item["spend"]
                for item in campaign_rows
                if item["campaign_name"] == row["campaign_name"]
                and month_start <= item["date"] <= month_end
            )
        projected_spend = row.get("projected_spend", spend_to_date)
        pacing_percent = row.get("pacing_percent")
        if pacing_percent is None:
            pacing_percent = spend_to_date / row["planned_budget"] if row["planned_budget"] else 0

        budget_output.append(
            {
                "id": f"{row['campaign_name']}-{row['month']}",
                "campaignName": row["campaign_name"],
                "parishes": row.get("parishes") or [],
                "monthlyBudget": row["planned_budget"],
                "spendToDate": spend_to_date,
                "projectedSpend": projected_spend,
                "pacingPercent": pacing_percent,
                "startDate": month_start,
                "endDate": month_end,
            }
        )

    payload = {
        "campaign": {
            "summary": {
                "currency": currency,
                "totalSpend": totals["spend"],
                "totalImpressions": totals["impressions"],
                "totalClicks": totals["clicks"],
                "totalConversions": totals["conversions"],
                "averageRoas": revenue_total / totals["spend"] if totals["spend"] else 0,
            },
            "trend": trend_rows,
            "rows": campaign_rows_output,
        },
        "creative": [],
        "budget": budget_output,
        "parish": parish_rows_output,
        "snapshot_generated_at": timestamp,
    }
    return payload
