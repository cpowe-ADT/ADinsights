"""Adapter for CSV-uploaded metrics stored per tenant."""

from __future__ import annotations

from typing import Any, Mapping

from analytics.models import TenantMetricsSnapshot
from rest_framework.exceptions import NotFound

from .base import AdapterInterface, MetricsAdapter, get_default_interfaces


class UploadAdapter(MetricsAdapter):
    """Serve metrics uploaded via CSV."""

    key = "upload"
    name = "CSV Upload"
    description = "Metrics uploaded manually via CSV."
    interfaces: tuple[AdapterInterface, ...] = get_default_interfaces()

    def fetch_metrics(
        self,
        *,
        tenant_id: str,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        snapshot = (
            TenantMetricsSnapshot.objects
            .filter(tenant_id=tenant_id, source=self.key)
            .order_by("-generated_at", "-created_at")
            .first()
        )
        if snapshot:
            return snapshot.payload
        raise NotFound("No uploaded metrics found.")
