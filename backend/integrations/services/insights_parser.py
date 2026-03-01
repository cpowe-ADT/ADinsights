from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils.dateparse import parse_datetime


@dataclass(slots=True)
class InsightPoint:
    metric_key: str
    period: str
    end_time: datetime
    value_num: Decimal | None
    value_json: dict[str, Any] | list[Any] | None
    breakdown_key: str | None
    breakdown_json: dict[str, Any] | None


@dataclass(slots=True)
class MetricMetadata:
    metric_key: str
    period: str
    title: str | None
    description: str | None


def normalize_insights_payload(
    payload: dict[str, Any],
    *,
    fallback_end_time: datetime | None = None,
) -> tuple[list[InsightPoint], list[MetricMetadata]]:
    points: list[InsightPoint] = []
    metadata: list[MetricMetadata] = []

    data = payload.get("data")
    if not isinstance(data, list):
        return points, metadata

    for metric_row in data:
        if not isinstance(metric_row, dict):
            continue
        metric_key = str(metric_row.get("name") or "").strip()
        period = str(metric_row.get("period") or "").strip()
        if not metric_key or not period:
            continue

        title = metric_row.get("title") if isinstance(metric_row.get("title"), str) else None
        description = (
            metric_row.get("description") if isinstance(metric_row.get("description"), str) else None
        )
        metadata.append(
            MetricMetadata(
                metric_key=metric_key,
                period=period,
                title=title,
                description=description,
            )
        )

        values = metric_row.get("values")
        if not isinstance(values, list):
            continue

        for value_row in values:
            if not isinstance(value_row, dict):
                continue
            end_time = _parse_end_time(value_row.get("end_time"), fallback_end_time=fallback_end_time)
            if end_time is None:
                continue
            raw_value = value_row.get("value")

            numeric = _to_decimal(raw_value)
            if numeric is not None:
                points.append(
                    InsightPoint(
                        metric_key=metric_key,
                        period=period,
                        end_time=end_time,
                        value_num=numeric,
                        value_json=None,
                        breakdown_key=None,
                        breakdown_json=None,
                    )
                )
                continue

            if isinstance(raw_value, dict):
                if not raw_value:
                    points.append(
                        InsightPoint(
                            metric_key=metric_key,
                            period=period,
                            end_time=end_time,
                            value_num=None,
                            value_json={},
                            breakdown_key=None,
                            breakdown_json=None,
                        )
                    )
                    continue

                for key, value in raw_value.items():
                    breakdown_key = str(key)
                    points.append(
                        InsightPoint(
                            metric_key=metric_key,
                            period=period,
                            end_time=end_time,
                            value_num=_to_decimal(value),
                            value_json=raw_value,
                            breakdown_key=breakdown_key,
                            breakdown_json={"key": breakdown_key, "value": value},
                        )
                    )
                continue

            if isinstance(raw_value, list):
                points.append(
                    InsightPoint(
                        metric_key=metric_key,
                        period=period,
                        end_time=end_time,
                        value_num=None,
                        value_json=raw_value,
                        breakdown_key=None,
                        breakdown_json=None,
                    )
                )

    return points, metadata


def normalize_breakdown_key(value: str | None) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else "__none__"


def _parse_end_time(raw_value: Any, *, fallback_end_time: datetime | None) -> datetime | None:
    if isinstance(raw_value, str) and raw_value.strip():
        candidate = parse_datetime(raw_value)
        if candidate is None:
            candidate = _parse_isoformat_fallback(raw_value)
        if candidate is not None:
            if candidate.tzinfo is None:
                return candidate.replace(tzinfo=dt_timezone.utc)
            return candidate

    if fallback_end_time is not None:
        if fallback_end_time.tzinfo is None:
            return fallback_end_time.replace(tzinfo=dt_timezone.utc)
        return fallback_end_time
    return None


def _parse_isoformat_fallback(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    return None
