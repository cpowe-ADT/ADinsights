"""Adapter that serves metrics sourced from the analytics warehouse."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping, Sequence

from django.utils import timezone
from django.utils.dateparse import parse_date

from analytics.models import TenantMetricsSnapshot

from .base import AdapterInterface, MetricsAdapter, get_default_interfaces


class WarehouseAdapter(MetricsAdapter):
    key = "warehouse"
    name = "Warehouse"
    description = "Metrics aggregated from warehouse views."
    interfaces: tuple[AdapterInterface, ...] = get_default_interfaces()

    def fetch_metrics(
        self,
        *,
        tenant_id: str,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        snapshot = TenantMetricsSnapshot.objects.filter(
            tenant_id=tenant_id,
            source=self.key,
        ).order_by("-generated_at", "-created_at").first()

        if snapshot and snapshot.payload:
            payload = dict(snapshot.payload)
            payload.setdefault("snapshot_generated_at", snapshot.generated_at.isoformat())
            return self._apply_filters(payload, options)

        return {
            "campaign": {
                "summary": {
                    "currency": None,
                    "totalSpend": 0,
                    "totalImpressions": 0,
                    "totalClicks": 0,
                    "totalConversions": 0,
                    "averageRoas": 0,
                },
                "trend": [],
                "rows": [],
            },
            "creative": [],
            "budget": [],
            "parish": [],
            "snapshot_generated_at": timezone.now().isoformat(),
        }

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return parse_date(value)
        return None

    @staticmethod
    def _normalize_parishes(parish: Any) -> list[str]:
        if parish is None:
            return []
        values: Sequence[Any]
        if isinstance(parish, str):
            values = parish.split(",")
        elif isinstance(parish, Iterable):
            values = list(parish)
        else:
            return []
        normalized = [
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        ]
        return normalized

    @staticmethod
    def _matches_parishes(value: Any, parishes: Sequence[str]) -> bool:
        if not parishes:
            return True
        normalized = {parish.strip().lower() for parish in parishes if parish.strip()}
        if not normalized:
            return True
        if isinstance(value, str):
            return value.strip().lower() in normalized
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return any(
                isinstance(item, str) and item.strip().lower() in normalized
                for item in value
            )
        return False

    @staticmethod
    def _date_in_range(value: date | None, start: date | None, end: date | None) -> bool:
        if value is None:
            return False
        if start and value < start:
            return False
        if end and value > end:
            return False
        return True

    @staticmethod
    def _ranges_overlap(
        row_start: date | None,
        row_end: date | None,
        start: date | None,
        end: date | None,
    ) -> bool:
        if start is None and end is None:
            return True
        if row_start is None and row_end is None:
            return True
        if row_start and end and row_start > end:
            return False
        if row_end and start and row_end < start:
            return False
        return True

    def _apply_filters(
        self,
        payload: Mapping[str, Any],
        options: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        if not options:
            return payload

        start_date = self._parse_date(options.get("start_date"))
        end_date = self._parse_date(options.get("end_date"))
        parishes = self._normalize_parishes(options.get("parish"))

        if not start_date and not end_date and not parishes:
            return payload

        filtered: dict[str, Any] = dict(payload)

        campaign = dict(filtered.get("campaign") or {})
        trend = list(campaign.get("trend") or [])
        if start_date or end_date:
            trend = [
                point
                for point in trend
                if self._date_in_range(
                    self._parse_date(point.get("date")), start_date, end_date
                )
            ]
        if parishes:
            trend = [
                point
                for point in trend
                if self._matches_parishes(
                    point.get("parish") or point.get("parishes"), parishes
                )
            ]
        rows = list(campaign.get("rows") or [])
        if start_date or end_date:
            rows = [
                row
                for row in rows
                if self._ranges_overlap(
                    self._parse_date(row.get("startDate")),
                    self._parse_date(row.get("endDate")),
                    start_date,
                    end_date,
                )
            ]
        rows = [row for row in rows if self._matches_parishes(row.get("parish"), parishes)]
        campaign["summary"] = self._recalculate_campaign_summary(
            campaign.get("summary"), rows
        )
        campaign["trend"] = trend
        campaign["rows"] = rows
        filtered["campaign"] = campaign

        creative = list(filtered.get("creative") or [])
        creative = [
            row for row in creative if self._matches_parishes(row.get("parish"), parishes)
        ]
        filtered["creative"] = creative

        budget = list(filtered.get("budget") or [])
        if start_date or end_date:
            budget = [
                row
                for row in budget
                if self._ranges_overlap(
                    self._parse_date(row.get("startDate")),
                    self._parse_date(row.get("endDate")),
                    start_date,
                    end_date,
                )
            ]
        budget = [
            row
            for row in budget
            if self._matches_parishes(row.get("parishes") or row.get("parish"), parishes)
        ]
        filtered["budget"] = budget

        parish_metrics = list(filtered.get("parish") or [])
        parish_metrics = [
            row
            for row in parish_metrics
            if self._matches_parishes(row.get("parish"), parishes)
        ]
        filtered["parish"] = parish_metrics

        return filtered

    @staticmethod
    def _coerce_number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _recalculate_campaign_summary(
        self,
        summary: Mapping[str, Any] | None,
        rows: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        current = dict(summary or {})
        total_spend = sum(self._coerce_number(row.get("spend")) for row in rows)
        total_impressions = int(
            sum(self._coerce_number(row.get("impressions")) for row in rows)
        )
        total_clicks = int(sum(self._coerce_number(row.get("clicks")) for row in rows))
        total_conversions = int(
            sum(self._coerce_number(row.get("conversions")) for row in rows)
        )
        roas_values = [
            self._coerce_number(row.get("roas"))
            for row in rows
            if row.get("roas") is not None
        ]
        average_roas = (
            sum(roas_values) / len(roas_values) if roas_values else 0.0
        )

        current.update(
            {
                "totalSpend": total_spend,
                "totalImpressions": total_impressions,
                "totalClicks": total_clicks,
                "totalConversions": total_conversions,
                "averageRoas": average_roas,
            }
        )
        return current
