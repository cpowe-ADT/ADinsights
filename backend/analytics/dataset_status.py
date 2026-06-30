from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import timezone

from adapters.base import MetricsAdapter
from adapters.demo import DemoAdapter
from adapters.fake import FakeAdapter
from adapters.meta_direct import MetaDirectAdapter
from adapters.upload import UploadAdapter
from adapters.warehouse import (
    WAREHOUSE_SNAPSHOT_STATUS_DETAIL_KEY,
    WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
    WAREHOUSE_SNAPSHOT_STATUS_KEY,
    WarehouseAdapter,
)
from analytics.models import TenantMetricsSnapshot


def build_adapter_registry(*, include_upload: bool = True) -> dict[str, MetricsAdapter]:
    registry: dict[str, MetricsAdapter] = {}
    if getattr(settings, "ENABLE_WAREHOUSE_ADAPTER", False):
        warehouse = WarehouseAdapter()
        registry[warehouse.key] = warehouse
    if getattr(settings, "ENABLE_META_DIRECT_ADAPTER", False):
        meta_direct = MetaDirectAdapter()
        registry[meta_direct.key] = meta_direct
    if getattr(settings, "ENABLE_DEMO_ADAPTER", False):
        demo = DemoAdapter()
        registry[demo.key] = demo
    if getattr(settings, "ENABLE_FAKE_ADAPTER", False):
        fake = FakeAdapter()
        registry[fake.key] = fake
    if include_upload and getattr(settings, "ENABLE_UPLOAD_ADAPTER", False):
        upload = UploadAdapter()
        registry[upload.key] = upload
    return registry


def build_dataset_status_payload(*, tenant) -> dict[str, Any]:
    registry = build_adapter_registry()
    warehouse_adapter_enabled = "warehouse" in registry
    demo_source = "demo" if "demo" in registry else "fake" if "fake" in registry else None
    demo_tenants = []
    if demo_source == "demo":
        demo_metadata = registry["demo"].metadata()
        demo_tenants = (demo_metadata.get("options") or {}).get("demo_tenants") or []

    live_reason = "adapter_disabled"
    live_enabled = False
    snapshot_generated_at = None
    live_detail = None

    if warehouse_adapter_enabled:
        snapshot = TenantMetricsSnapshot.latest_for(tenant=tenant, source="warehouse")
        if snapshot is None or not snapshot.payload:
            live_reason = "missing_snapshot"
        else:
            snapshot_generated_at = snapshot.generated_at.isoformat()
            detail = snapshot.payload.get(WAREHOUSE_SNAPSHOT_STATUS_DETAIL_KEY)
            live_detail = detail if isinstance(detail, str) and detail.strip() else None
            stale_ttl_seconds = max(
                int(getattr(settings, "METRICS_SNAPSHOT_STALE_TTL_SECONDS", 3600) or 3600),
                1,
            )
            if (timezone.now() - snapshot.generated_at).total_seconds() > stale_ttl_seconds:
                live_reason = "stale_snapshot"
            else:
                snapshot_status = snapshot.payload.get(WAREHOUSE_SNAPSHOT_STATUS_KEY)
                if snapshot_status and snapshot_status != WAREHOUSE_SNAPSHOT_STATUS_FETCHED:
                    live_reason = "default_snapshot"
                else:
                    live_reason = "ready"
                    live_enabled = True

    return {
        "live": {
            "enabled": live_enabled,
            "reason": live_reason,
            "snapshot_generated_at": snapshot_generated_at,
            "detail": live_detail,
        },
        "demo": {
            "enabled": demo_source is not None,
            "source": demo_source,
            "tenant_count": len(demo_tenants),
        },
        "warehouse_adapter_enabled": warehouse_adapter_enabled,
    }
