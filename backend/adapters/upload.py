"""Adapter for CSV-uploaded metrics stored per tenant."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from analytics.models import TenantMetricsSnapshot
from rest_framework.exceptions import NotFound

from .base import AdapterInterface, MetricsAdapter, get_default_interfaces

logger = logging.getLogger(__name__)


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
        _opts = options or {}
        client_scope_requested = bool(_opts.get("client_scope_requested"))
        scoped_meta = list(_opts.get("client_scoped_meta_ad_account_ids") or [])
        scoped_google = list(_opts.get("client_scoped_google_customer_ids") or [])

        snapshot = (
            TenantMetricsSnapshot.objects
            .filter(tenant_id=tenant_id, source=self.key)
            .order_by("-generated_at", "-created_at")
            .first()
        )
        if snapshot:
            payload = dict(snapshot.payload)
            if client_scope_requested:
                if not scoped_meta and not scoped_google:
                    return _upload_empty_payload(payload)
                # Best-effort: filter by adAccountId if present; fall back to platform string.
                allowed_account_ids: set[str] = set(scoped_meta) | set(scoped_google)
                payload = _filter_upload_payload(
                    payload, allowed_account_ids, scoped_meta, scoped_google
                )
            return payload
        raise NotFound("No uploaded metrics found.")


def _filter_upload_payload(
    payload: dict[str, Any],
    allowed_account_ids: set[str],
    scoped_meta: list[str],
    scoped_google: list[str],
) -> dict[str, Any]:
    """Best-effort row filter for upload payloads.

    Priority: adAccountId field -> platform string.
    Rows with no adAccountId AND no platform field are kept (cannot narrow).
    """
    result = dict(payload)
    campaign = dict(result.get("campaign") or {})
    rows = list(campaign.get("rows") or [])
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        account_id = row.get("adAccountId") or row.get("ad_account_id")
        if account_id:
            if str(account_id) in allowed_account_ids:
                filtered_rows.append(row)
            continue
        # Fallback: platform string.
        platform = (row.get("platform") or "").lower()
        if not platform:
            filtered_rows.append(row)  # cannot narrow, keep
            continue
        meta_aliases = {
            "meta", "meta_ads", "meta ads", "facebook", "instagram",
            "audience_network", "messenger",
        }
        google_aliases = {"google", "google_ads", "google ads"}
        if scoped_meta and platform in meta_aliases:
            filtered_rows.append(row)
        elif scoped_google and platform in google_aliases:
            filtered_rows.append(row)
    campaign["rows"] = filtered_rows
    result["campaign"] = campaign
    return result


def _upload_empty_payload(template: dict[str, Any]) -> dict[str, Any]:
    """Return a zero-filled payload shaped like the upload snapshot."""
    empty = dict(template)
    campaign = dict(template.get("campaign") or {})
    summary = dict(campaign.get("summary") or {})
    for k in ("totalSpend", "totalImpressions", "totalClicks", "totalConversions", "averageRoas"):
        if k in summary:
            summary[k] = 0
    campaign["summary"] = summary
    campaign["trend"] = []
    campaign["rows"] = []
    empty["campaign"] = campaign
    for key in ("creative", "budget", "parish"):
        if key in empty:
            empty[key] = []
    return empty
