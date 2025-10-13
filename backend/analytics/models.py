"""Analytics domain models."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

from accounts.models import Tenant, TenantAwareManager


class TenantMetricsSnapshot(models.Model):
    """Cached analytics payload for a tenant and adapter source."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="metrics_snapshots"
    )
    source = models.CharField(max_length=64, default="combined")
    payload = models.JSONField(default=dict)
    generated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "source")
        ordering = ("-generated_at", "-created_at")

    def is_fresh(self, ttl_seconds: int) -> bool:
        return (timezone.now() - self.generated_at) <= timedelta(seconds=ttl_seconds)

    @classmethod
    def latest_for(cls, tenant: Tenant, source: str) -> "TenantMetricsSnapshot | None":
        return (
            cls.objects
            .filter(tenant=tenant, source=source)
            .order_by("-generated_at", "-created_at")
            .first()
        )

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"TenantMetricsSnapshot<{self.tenant_id}:{self.source}>"
