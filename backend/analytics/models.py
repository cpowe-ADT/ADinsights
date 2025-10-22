"""Analytics domain models."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from accounts.models import Tenant, TenantAwareManager


class Campaign(models.Model):
    """Normalized advertising campaign metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="analytics_campaigns"
    )
    external_id = models.CharField(max_length=128)
    name = models.CharField(max_length=255)
    platform = models.CharField(max_length=32)
    account_external_id = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=32, blank=True)
    objective = models.CharField(max_length=64, blank=True)
    currency = models.CharField(max_length=16, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_time = models.DateTimeField(null=True, blank=True)
    updated_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("name", "external_id")
        indexes = [
            models.Index(fields=["tenant", "external_id"], name="analytics_campaign_ext"),
        ]
        unique_together = ("tenant", "external_id")

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"Campaign<{self.tenant_id}:{self.external_id}>"


class AdSet(models.Model):
    """Normalized ad set metadata scoped to a tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="analytics_adsets"
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="adsets"
    )
    external_id = models.CharField(max_length=128)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, blank=True)
    bid_strategy = models.CharField(max_length=64, blank=True)
    daily_budget = models.DecimalField(
        max_digits=20, decimal_places=6, default=Decimal("0"), blank=True
    )
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    targeting = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("name", "external_id")
        indexes = [
            models.Index(fields=["tenant", "external_id"], name="analytics_adset_ext"),
        ]
        unique_together = ("tenant", "external_id")

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"AdSet<{self.tenant_id}:{self.external_id}>"


class Ad(models.Model):
    """Normalized ad creative metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="analytics_ads"
    )
    adset = models.ForeignKey(AdSet, on_delete=models.CASCADE, related_name="ads")
    external_id = models.CharField(max_length=128)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, blank=True)
    creative = models.JSONField(default=dict, blank=True)
    preview_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("name", "external_id")
        indexes = [
            models.Index(fields=["tenant", "external_id"], name="analytics_ad_ext"),
        ]
        unique_together = ("tenant", "external_id")

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"Ad<{self.tenant_id}:{self.external_id}>"


class RawPerformanceRecord(models.Model):
    """Raw performance metrics ingested from ad platforms."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="analytics_performance_records"
    )
    external_id = models.CharField(max_length=128)
    date = models.DateField()
    source = models.CharField(max_length=32)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="performance_records"
    )
    adset = models.ForeignKey(
        AdSet, on_delete=models.SET_NULL, null=True, blank=True, related_name="performance_records"
    )
    ad = models.ForeignKey(
        Ad, on_delete=models.SET_NULL, null=True, blank=True, related_name="performance_records"
    )
    impressions = models.PositiveBigIntegerField(default=0)
    clicks = models.PositiveBigIntegerField(default=0)
    spend = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    currency = models.CharField(max_length=16, blank=True)
    conversions = models.IntegerField(default=0)
    raw_payload = models.JSONField(default=dict, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-date", "-ingested_at")
        indexes = [
            models.Index(fields=["tenant", "external_id"], name="analytics_perf_ext"),
            models.Index(fields=["tenant", "date"], name="analytics_perf_date"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"RawPerformance<{self.tenant_id}:{self.external_id}:{self.date}>"


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
