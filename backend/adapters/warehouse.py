"""Adapter that serves metrics sourced from the analytics warehouse."""

from __future__ import annotations

from typing import Any, Mapping

from django.utils import timezone

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
    ) -> Mapping[str, Any]:  # noqa: ARG002 - options reserved for filter hooks
        snapshot = TenantMetricsSnapshot.objects.filter(
            tenant_id=tenant_id,
            source=self.key,
        ).order_by("-generated_at", "-created_at").first()

        if snapshot and snapshot.payload:
            payload = dict(snapshot.payload)
            payload.setdefault("snapshot_generated_at", snapshot.generated_at.isoformat())
            return payload

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
