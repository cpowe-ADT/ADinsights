"""Analytics domain models."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Tenant, TenantAwareManager


class Campaign(models.Model):
    """Normalized advertising campaign metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="analytics_campaigns"
    )
    ad_account = models.ForeignKey(
        "AdAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
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
            models.Index(fields=["tenant", "ad_account"], name="analytics_campaign_account"),
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
    ad_account = models.ForeignKey(
        "AdAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performance_records",
    )
    external_id = models.CharField(max_length=128)
    date = models.DateField()
    level = models.CharField(max_length=16, default="ad")
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
    reach = models.PositiveBigIntegerField(default=0)
    clicks = models.PositiveBigIntegerField(default=0)
    spend = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cpc = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cpm = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    currency = models.CharField(max_length=16, blank=True)
    conversions = models.IntegerField(default=0)
    actions = models.JSONField(default=list, blank=True)
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
            models.Index(fields=["tenant", "ad_account", "date"], name="analytics_perf_acct_date"),
            models.Index(fields=["tenant", "level", "date"], name="analytics_perf_level_date"),
        ]
        unique_together = ("tenant", "source", "external_id", "date", "level")

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"RawPerformance<{self.tenant_id}:{self.external_id}:{self.date}>"


class AdAccount(models.Model):
    """Tenant-scoped Meta ad account metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="analytics_ad_accounts"
    )
    external_id = models.CharField(max_length=128)
    account_id = models.CharField(max_length=128, blank=True)
    name = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=32, blank=True)
    business_name = models.CharField(max_length=255, blank=True)
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
            models.Index(fields=["tenant", "external_id"], name="analytics_adacct_ext"),
            models.Index(fields=["tenant", "account_id"], name="analytics_adacct_account"),
        ]
        unique_together = ("tenant", "external_id")

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"AdAccount<{self.tenant_id}:{self.external_id}>"


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


class GoogleAdsSavedView(models.Model):
    """Persisted filter/view presets for Google Ads reporting surfaces."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_saved_views"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    filters = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    is_shared = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_google_ads_saved_views",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_google_ads_saved_views",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-updated_at", "name")
        indexes = [
            models.Index(fields=["tenant", "is_shared"], name="gads_saved_view_tenant_shared"),
        ]


class GoogleAdsExportJob(models.Model):
    """Track Google Ads dashboard export requests and generated artifacts."""

    FORMAT_CSV = "csv"
    FORMAT_PDF = "pdf"
    FORMAT_CHOICES = [
        (FORMAT_CSV, "CSV"),
        (FORMAT_PDF, "PDF"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_export_jobs"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="google_ads_export_jobs",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    export_format = models.CharField(max_length=8, choices=FORMAT_CHOICES, default=FORMAT_CSV)
    filters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    artifact_path = models.CharField(max_length=512, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "status"], name="gads_export_tenant_status"),
        ]


class ReportDefinition(models.Model):
    """Tenant-scoped report definition used by reporting UIs and exports."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="report_definitions"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    filters = models.JSONField(default=dict, blank=True)
    layout = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_report_definitions",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_report_definitions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-updated_at", "name")
        indexes = [
            models.Index(fields=["tenant", "name"], name="analytics_report_tenant_name"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"ReportDefinition<{self.tenant_id}:{self.name}>"


class ReportExportJob(models.Model):
    """Track report export requests and async completion metadata."""

    FORMAT_CSV = "csv"
    FORMAT_PDF = "pdf"
    FORMAT_PNG = "png"
    FORMAT_CHOICES = [
        (FORMAT_CSV, "CSV"),
        (FORMAT_PDF, "PDF"),
        (FORMAT_PNG, "PNG"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="report_export_jobs"
    )
    report = models.ForeignKey(
        ReportDefinition, on_delete=models.CASCADE, related_name="export_jobs"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_report_export_jobs",
    )
    export_format = models.CharField(max_length=8, choices=FORMAT_CHOICES, default=FORMAT_CSV)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    artifact_path = models.CharField(max_length=512, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "status"], name="analytics_export_tenant_status"),
            models.Index(fields=["tenant", "report"], name="analytics_export_tenant_report"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"ReportExportJob<{self.tenant_id}:{self.report_id}:{self.status}>"


class AISummary(models.Model):
    """Persist generated AI daily summaries for UI listing/detail."""

    STATUS_GENERATED = "generated"
    STATUS_FALLBACK = "fallback"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_GENERATED, "Generated"),
        (STATUS_FALLBACK, "Fallback"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="ai_summaries"
    )
    title = models.CharField(max_length=255)
    summary = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=64, default="daily_summary")
    model_name = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_GENERATED)
    generated_at = models.DateTimeField(default=timezone.now)
    task_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-generated_at", "-created_at")
        indexes = [
            models.Index(fields=["tenant", "generated_at"], name="analytics_summary_tenant_ts"),
            models.Index(fields=["tenant", "source"], name="analytics_summary_tenant_src"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"AISummary<{self.tenant_id}:{self.generated_at.isoformat()}>"
