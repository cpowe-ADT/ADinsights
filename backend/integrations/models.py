from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from croniter import croniter
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Tenant, TenantAwareManager, User
from core.crypto.dek_manager import get_dek_for_tenant
from core.crypto.fields import decrypt_value, encrypt_value


class PlatformCredential(models.Model):
    META = "META"
    GOOGLE = "GOOGLE"
    LINKEDIN = "LINKEDIN"
    TIKTOK = "TIKTOK"
    PROVIDER_CHOICES = [
        (META, "Meta"),
        (GOOGLE, "Google Ads"),
        (LINKEDIN, "LinkedIn"),
        (TIKTOK, "TikTok"),
    ]
    AUTH_MODE_USER_OAUTH = "user_oauth"
    AUTH_MODE_SYSTEM_USER = "system_user"
    AUTH_MODE_CHOICES = [
        (AUTH_MODE_USER_OAUTH, "User OAuth"),
        (AUTH_MODE_SYSTEM_USER, "System User"),
    ]

    TOKEN_STATUS_VALID = "valid"
    TOKEN_STATUS_EXPIRING = "expiring"
    TOKEN_STATUS_INVALID = "invalid"
    TOKEN_STATUS_REAUTH_REQUIRED = "reauth_required"
    TOKEN_STATUS_CHOICES = [
        (TOKEN_STATUS_VALID, "Valid"),
        (TOKEN_STATUS_EXPIRING, "Expiring"),
        (TOKEN_STATUS_INVALID, "Invalid"),
        (TOKEN_STATUS_REAUTH_REQUIRED, "Reauth Required"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="platform_credentials"
    )
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES)
    account_id = models.CharField(max_length=128)
    access_token_enc = models.BinaryField()
    access_token_nonce = models.BinaryField()
    access_token_tag = models.BinaryField()
    refresh_token_enc = models.BinaryField(null=True, blank=True)
    refresh_token_nonce = models.BinaryField(null=True, blank=True)
    refresh_token_tag = models.BinaryField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    auth_mode = models.CharField(
        max_length=16,
        choices=AUTH_MODE_CHOICES,
        default=AUTH_MODE_USER_OAUTH,
    )
    granted_scopes = models.JSONField(default=list, blank=True)
    declined_scopes = models.JSONField(default=list, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    last_refresh_attempt_at = models.DateTimeField(null=True, blank=True)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    token_status = models.CharField(
        max_length=16,
        choices=TOKEN_STATUS_CHOICES,
        default=TOKEN_STATUS_VALID,
    )
    token_status_reason = models.TextField(blank=True)
    dek_key_version = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    _raw_access_token: Optional[str] = None
    _raw_refresh_token: Optional[str] = None
    _refresh_token_cleared: bool = False

    class Meta:
        unique_together = ("tenant", "provider", "account_id")

    def mark_refresh_token_for_clear(self) -> None:
        self._refresh_token_cleared = True
        self._raw_refresh_token = None

    def set_raw_tokens(
        self, access_token: Optional[str], refresh_token: Optional[str]
    ) -> None:
        self._raw_access_token = access_token
        if refresh_token is not None:
            self._raw_refresh_token = refresh_token
            self._refresh_token_cleared = False
        elif self._refresh_token_cleared:
            self._raw_refresh_token = None
        else:
            self._raw_refresh_token = refresh_token

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            raise ValueError("Tenant must be set before saving PlatformCredential")
        refresh_cleared = getattr(self, "_refresh_token_cleared", False)
        should_process_tokens = (
            self._raw_access_token is not None
            or self._raw_refresh_token is not None
            or refresh_cleared
            or not self.dek_key_version
        )
        if should_process_tokens:
            key = version = None
            if (
                self._raw_access_token is not None
                or self._raw_refresh_token is not None
                or (not self.dek_key_version and not refresh_cleared)
            ):
                key, version = get_dek_for_tenant(self.tenant)
            if self._raw_access_token is not None and key is not None:
                encrypted = encrypt_value(self._raw_access_token, key)
                if encrypted:
                    self.access_token_enc = encrypted.ciphertext
                    self.access_token_nonce = encrypted.nonce
                    self.access_token_tag = encrypted.tag
            if self._raw_refresh_token is not None and key is not None:
                encrypted_refresh = encrypt_value(self._raw_refresh_token, key)
                if encrypted_refresh:
                    self.refresh_token_enc = encrypted_refresh.ciphertext
                    self.refresh_token_nonce = encrypted_refresh.nonce
                    self.refresh_token_tag = encrypted_refresh.tag
            elif refresh_cleared:
                self.refresh_token_enc = None
                self.refresh_token_nonce = None
                self.refresh_token_tag = None
            if version is not None:
                self.dek_key_version = version
        super().save(*args, **kwargs)
        self._raw_access_token = None
        self._raw_refresh_token = None
        self._refresh_token_cleared = False

    def decrypt_access_token(self) -> Optional[str]:
        key, _ = get_dek_for_tenant(self.tenant)
        return decrypt_value(
            self.access_token_enc,
            self.access_token_nonce,
            self.access_token_tag,
            key,
        )

    def decrypt_refresh_token(self) -> Optional[str]:
        if not self.refresh_token_enc:
            return None
        key, _ = get_dek_for_tenant(self.tenant)
        return decrypt_value(
            self.refresh_token_enc,
            self.refresh_token_nonce,
            self.refresh_token_tag,
            key,
        )

    def mark_rotated(
        self,
        version: str,
        ciphertext: bytes,
        nonce: bytes,
        tag: bytes,
        refresh_cipher: Optional[bytes] = None,
        refresh_nonce: Optional[bytes] = None,
        refresh_tag: Optional[bytes] = None,
    ) -> None:
        self.access_token_enc = ciphertext
        self.access_token_nonce = nonce
        self.access_token_tag = tag
        if refresh_cipher is not None:
            self.refresh_token_enc = refresh_cipher
            self.refresh_token_nonce = refresh_nonce
            self.refresh_token_tag = refresh_tag
        self.dek_key_version = version
        self.updated_at = timezone.now()
        super().save(
            update_fields=[
                "access_token_enc",
                "access_token_nonce",
                "access_token_tag",
                "refresh_token_enc",
                "refresh_token_nonce",
                "refresh_token_tag",
                "dek_key_version",
                "updated_at",
            ]
        )


class AirbyteConnection(models.Model):
    """Configuration and sync metadata for an Airbyte connection."""

    SCHEDULE_MANUAL = "manual"
    SCHEDULE_INTERVAL = "interval"
    SCHEDULE_CRON = "cron"
    SCHEDULE_CHOICES = [
        (SCHEDULE_MANUAL, "Manual"),
        (SCHEDULE_INTERVAL, "Interval"),
        (SCHEDULE_CRON, "Cron"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="airbyte_connections"
    )
    provider = models.CharField(
        max_length=16,
        choices=PlatformCredential.PROVIDER_CHOICES,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    connection_id = models.UUIDField()
    workspace_id = models.UUIDField(null=True, blank=True)
    schedule_type = models.CharField(
        max_length=16, choices=SCHEDULE_CHOICES, default=SCHEDULE_INTERVAL
    )
    interval_minutes = models.PositiveIntegerField(null=True, blank=True)
    cron_expression = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_job_id = models.CharField(max_length=64, blank=True)
    last_job_status = models.CharField(max_length=32, blank=True)
    last_job_created_at = models.DateTimeField(null=True, blank=True)
    last_job_updated_at = models.DateTimeField(null=True, blank=True)
    last_job_completed_at = models.DateTimeField(null=True, blank=True)
    last_job_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "connection_id")
        ordering = ["tenant", "name"]

    def should_trigger(self, now: datetime) -> bool:
        if not self.is_active:
            return False
        if self.schedule_type == self.SCHEDULE_MANUAL:
            return False
        if self.schedule_type == self.SCHEDULE_INTERVAL:
            if not self.interval_minutes:
                return False
            if self.last_synced_at is None:
                return True
            return self.last_synced_at + timedelta(minutes=self.interval_minutes) <= now
        if self.schedule_type == self.SCHEDULE_CRON:
            if not self.cron_expression:
                return False
            try:
                iterator = croniter(self.cron_expression, now)
                previous_run = iterator.get_prev(datetime)
            except (ValueError, TypeError):
                return False
            return self.last_synced_at is None or self.last_synced_at < previous_run
        return False

    SYNC_SUCCESS_STATUSES = {"succeeded", "success", "completed"}

    def record_sync(self, job_id: int | None, job_status: str, job_created_at: datetime) -> None:
        update = ConnectionSyncUpdate(
            connection=self,
            job_id=str(job_id) if job_id is not None else None,
            status=job_status or "",
            created_at=job_created_at,
            updated_at=job_created_at,
            completed_at=None,
            duration_seconds=None,
            records_synced=None,
            bytes_synced=None,
            api_cost=None,
            error=None,
        )
        AirbyteConnection.persist_sync_updates([update])

    @classmethod
    def persist_sync_updates(
        cls, updates: Iterable["ConnectionSyncUpdate"]
    ) -> list["AirbyteConnection"]:
        """Persist sync metadata for the provided connections atomically."""

        persisted: list[AirbyteConnection] = []
        seen: set[int] = set()
        now = timezone.now()

        for update in updates:
            connection = update.connection
            if not isinstance(connection, AirbyteConnection) or connection.pk is None:
                continue

            created_at = update.created_at or connection.last_job_created_at
            updated_at = update.updated_at or created_at
            completed_at = update.completed_at

            status_value = (update.status or "").strip()
            status_lower = status_value.lower()

            if completed_at is None and status_lower in cls.SYNC_SUCCESS_STATUSES and updated_at:
                completed_at = updated_at

            fields: dict[str, object] = {
                "last_job_id": update.job_id or "",
                "last_job_status": status_value,
                "last_job_created_at": created_at,
                "last_job_updated_at": updated_at,
                "last_job_completed_at": completed_at,
                "last_job_error": (update.error or ""),
                "updated_at": now,
            }

            last_synced_at = connection.last_synced_at
            if completed_at is not None:
                last_synced_at = completed_at
            elif status_lower in cls.SYNC_SUCCESS_STATUSES and updated_at:
                last_synced_at = updated_at
            if last_synced_at is not None:
                fields["last_synced_at"] = last_synced_at

            cls.all_objects.filter(pk=connection.pk).update(**fields)

            for field_name, value in fields.items():
                setattr(connection, field_name, value)

            if connection.pk not in seen:
                persisted.append(connection)
                seen.add(connection.pk)

        for connection in persisted:
            TenantAirbyteSyncStatus.update_for_connection(connection)

        return persisted


class TenantAirbyteSyncStatus(models.Model):
    """Aggregated Airbyte sync metadata per tenant."""

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="airbyte_sync_status"
    )
    last_connection = models.ForeignKey(
        "AirbyteConnection", null=True, blank=True, on_delete=models.SET_NULL, related_name="tenant_sync_statuses"
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_job_id = models.CharField(max_length=64, blank=True)
    last_job_status = models.CharField(max_length=32, blank=True)
    last_job_updated_at = models.DateTimeField(null=True, blank=True)
    last_job_completed_at = models.DateTimeField(null=True, blank=True)
    last_job_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "Tenant Airbyte sync status"
        verbose_name_plural = "Tenant Airbyte sync statuses"

    def record_connection(self, connection: "AirbyteConnection") -> None:
        self.last_connection = connection
        self.last_synced_at = connection.last_synced_at
        self.last_job_id = connection.last_job_id
        self.last_job_status = connection.last_job_status
        self.last_job_updated_at = connection.last_job_updated_at
        self.last_job_completed_at = connection.last_job_completed_at
        self.last_job_error = connection.last_job_error
        self.save(
            update_fields=[
                "last_connection",
                "last_synced_at",
                "last_job_id",
                "last_job_status",
                "last_job_updated_at",
                "last_job_completed_at",
                "last_job_error",
                "updated_at",
            ]
        )

    @classmethod
    def update_for_connection(cls, connection: "AirbyteConnection") -> "TenantAirbyteSyncStatus":
        status, created = cls.all_objects.get_or_create(tenant=connection.tenant)
        if created:
            status.last_connection = connection
            status.last_synced_at = connection.last_synced_at
            status.last_job_id = connection.last_job_id
            status.last_job_status = connection.last_job_status
            status.last_job_updated_at = connection.last_job_updated_at
            status.last_job_completed_at = connection.last_job_completed_at
            status.last_job_error = connection.last_job_error
            status.save(
                update_fields=[
                    "last_connection",
                    "last_synced_at",
                    "last_job_id",
                    "last_job_status",
                    "last_job_updated_at",
                    "last_job_completed_at",
                    "last_job_error",
                    "updated_at",
                ]
            )
            return status
        status.record_connection(connection)
        return status


class MetaAccountSyncState(models.Model):
    """Per-account Meta sync-state materialized for operations/status surfaces."""

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="meta_account_sync_states"
    )
    account_id = models.CharField(max_length=128)
    connection = models.ForeignKey(
        AirbyteConnection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="meta_account_sync_states",
    )
    last_job_id = models.CharField(max_length=64, blank=True)
    last_job_status = models.CharField(max_length=32, blank=True)
    last_job_error = models.TextField(blank=True)
    last_sync_started_at = models.DateTimeField(null=True, blank=True)
    last_sync_completed_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_window_start = models.DateField(null=True, blank=True)
    last_window_end = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "account_id")
        ordering = ("tenant", "account_id")


class MetaConnection(models.Model):
    """Tenant/user-scoped Meta OAuth session used for Page/Post Insights."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="meta_connections"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="meta_connections"
    )
    app_scoped_user_id = models.CharField(max_length=128, blank=True)
    token_enc = models.BinaryField()
    token_nonce = models.BinaryField()
    token_tag = models.BinaryField()
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    dek_key_version = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    _raw_token: Optional[str] = None

    class Meta:
        unique_together = ("tenant", "user", "app_scoped_user_id")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="meta_conn_tenant_active"),
        ]

    def set_raw_token(self, value: str | None) -> None:
        self._raw_token = value

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            raise ValueError("Tenant must be set before saving MetaConnection")
        if self._raw_token is not None or not self.dek_key_version:
            key, version = get_dek_for_tenant(self.tenant)
            if self._raw_token is not None:
                encrypted = encrypt_value(self._raw_token, key)
                if encrypted:
                    self.token_enc = encrypted.ciphertext
                    self.token_nonce = encrypted.nonce
                    self.token_tag = encrypted.tag
            self.dek_key_version = version
        super().save(*args, **kwargs)
        self._raw_token = None

    def decrypt_token(self) -> Optional[str]:
        key, _ = get_dek_for_tenant(self.tenant)
        return decrypt_value(self.token_enc, self.token_nonce, self.token_tag, key)


class MetaPage(models.Model):
    """Page selected for Insights ingestion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="meta_pages"
    )
    connection = models.ForeignKey(
        MetaConnection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pages",
    )
    page_id = models.CharField(max_length=128)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255, blank=True)
    page_token_enc = models.BinaryField()
    page_token_nonce = models.BinaryField()
    page_token_tag = models.BinaryField()
    page_token_expires_at = models.DateTimeField(null=True, blank=True)
    can_analyze = models.BooleanField(default=False)
    tasks = models.JSONField(default=list, blank=True)
    perms = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_posts_synced_at = models.DateTimeField(null=True, blank=True)
    dek_key_version = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    _raw_page_token: Optional[str] = None

    class Meta:
        unique_together = ("tenant", "page_id")
        indexes = [
            models.Index(fields=["tenant", "is_default"], name="meta_page_tenant_default"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(is_default=True),
                name="meta_page_single_default_per_tenant",
            )
        ]

    def set_raw_page_token(self, value: str | None) -> None:
        self._raw_page_token = value

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            raise ValueError("Tenant must be set before saving MetaPage")
        if self._raw_page_token is not None or not self.dek_key_version:
            key, version = get_dek_for_tenant(self.tenant)
            if self._raw_page_token is not None:
                encrypted = encrypt_value(self._raw_page_token, key)
                if encrypted:
                    self.page_token_enc = encrypted.ciphertext
                    self.page_token_nonce = encrypted.nonce
                    self.page_token_tag = encrypted.tag
            self.dek_key_version = version
        super().save(*args, **kwargs)
        self._raw_page_token = None

    def decrypt_page_token(self) -> Optional[str]:
        key, _ = get_dek_for_tenant(self.tenant)
        return decrypt_value(
            self.page_token_enc,
            self.page_token_nonce,
            self.page_token_tag,
            key,
        )


class MetaMetricRegistry(models.Model):
    LEVEL_PAGE = "PAGE"
    LEVEL_POST = "POST"
    LEVEL_CHOICES = [
        (LEVEL_PAGE, "Page"),
        (LEVEL_POST, "Post"),
    ]

    STATUS_ACTIVE = "ACTIVE"
    STATUS_DEPRECATED = "DEPRECATED"
    STATUS_INVALID = "INVALID"
    STATUS_UNKNOWN = "UNKNOWN"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_DEPRECATED, "Deprecated"),
        (STATUS_INVALID, "Invalid"),
        (STATUS_UNKNOWN, "Unknown"),
    ]

    metric_key = models.CharField(max_length=191)
    level = models.CharField(max_length=8, choices=LEVEL_CHOICES)
    supported_periods = models.JSONField(default=list, blank=True)
    supports_breakdowns = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    replacement_metric_key = models.CharField(max_length=191, blank=True)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("metric_key", "level")
        indexes = [
            models.Index(fields=["level", "status"], name="meta_metric_level_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"{self.level}:{self.metric_key}"


class MetaMetricSupportStatus(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="meta_metric_support_statuses"
    )
    page = models.ForeignKey(
        MetaPage,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="metric_support_statuses",
    )
    level = models.CharField(max_length=8, choices=MetaMetricRegistry.LEVEL_CHOICES)
    metric_key = models.CharField(max_length=191)
    supported = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "page", "level", "metric_key")
        indexes = [
            models.Index(fields=["page", "level", "supported"], name="meta_support_page_level_sup"),
            models.Index(fields=["tenant", "level"], name="meta_support_tenant_level"),
        ]


class MetaInsightPoint(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="meta_insight_points"
    )
    page = models.ForeignKey(
        MetaPage, on_delete=models.CASCADE, related_name="insight_points"
    )
    metric_key = models.CharField(max_length=191)
    period = models.CharField(max_length=32)
    end_time = models.DateTimeField()
    value_num = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)
    breakdown_key = models.CharField(max_length=191, null=True, blank=True)
    breakdown_key_normalized = models.CharField(max_length=191, default="")
    breakdown_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tenant",
                    "page",
                    "metric_key",
                    "period",
                    "end_time",
                    "breakdown_key_normalized",
                ],
                name="meta_page_insight_point_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["page", "metric_key", "period", "end_time"],
                name="meta_page_metric_period_time",
            )
        ]


class MetaPost(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="meta_posts"
    )
    page = models.ForeignKey(
        MetaPage, on_delete=models.CASCADE, related_name="posts"
    )
    post_id = models.CharField(max_length=191)
    media_type = models.CharField(max_length=64, blank=True)
    message = models.TextField(blank=True)
    permalink_url = models.URLField(max_length=500, blank=True)
    created_time = models.DateTimeField(null=True, blank=True)
    updated_time = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "page", "post_id")
        indexes = [
            models.Index(fields=["page", "created_time"], name="meta_post_page_created"),
        ]


class MetaPostInsightPoint(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="meta_post_insight_points"
    )
    post = models.ForeignKey(
        MetaPost, on_delete=models.CASCADE, related_name="insight_points"
    )
    metric_key = models.CharField(max_length=191)
    period = models.CharField(max_length=32)
    end_time = models.DateTimeField()
    value_num = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)
    breakdown_key = models.CharField(max_length=191, null=True, blank=True)
    breakdown_key_normalized = models.CharField(max_length=191, default="")
    breakdown_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tenant",
                    "post",
                    "metric_key",
                    "period",
                    "end_time",
                    "breakdown_key_normalized",
                ],
                name="meta_post_insight_point_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["post", "metric_key", "period", "end_time"],
                name="meta_post_metric_period_time",
            )
        ]


class GoogleAdsSdkCampaignDaily(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_campaign_daily"
    )
    customer_id = models.CharField(max_length=32)
    campaign_id = models.CharField(max_length=64)
    campaign_name = models.CharField(max_length=255, blank=True)
    campaign_status = models.CharField(max_length=32, blank=True)
    advertising_channel_type = models.CharField(max_length=32, blank=True)
    date_day = models.DateField()
    currency_code = models.CharField(max_length=16, blank=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    conversions_value = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cost_micros = models.BigIntegerField(default=0)
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "customer_id", "campaign_id", "date_day")
        indexes = [
            models.Index(fields=["tenant", "date_day"], name="gads_sdk_campaign_day"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_campaign_customer"),
        ]


class GoogleAdsSdkAdGroupAdDaily(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_ad_group_ad_daily"
    )
    customer_id = models.CharField(max_length=32)
    campaign_id = models.CharField(max_length=64)
    ad_group_id = models.CharField(max_length=64)
    ad_id = models.CharField(max_length=64)
    campaign_name = models.CharField(max_length=255, blank=True)
    ad_name = models.CharField(max_length=255, blank=True)
    ad_status = models.CharField(max_length=32, blank=True)
    policy_approval_status = models.CharField(max_length=32, blank=True)
    policy_review_status = models.CharField(max_length=32, blank=True)
    date_day = models.DateField()
    currency_code = models.CharField(max_length=16, blank=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    conversions_value = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cost_micros = models.BigIntegerField(default=0)
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = (
            "tenant",
            "customer_id",
            "campaign_id",
            "ad_group_id",
            "ad_id",
            "date_day",
        )
        indexes = [
            models.Index(fields=["tenant", "date_day"], name="gads_sdk_ad_day"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_ad_customer"),
        ]


class GoogleAdsSdkGeographicDaily(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_geographic_daily"
    )
    customer_id = models.CharField(max_length=32)
    campaign_id = models.CharField(max_length=64)
    date_day = models.DateField()
    geo_target_country = models.CharField(max_length=128, blank=True)
    geo_target_region = models.CharField(max_length=128, blank=True)
    geo_target_city = models.CharField(max_length=128, blank=True)
    currency_code = models.CharField(max_length=16, blank=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    conversions_value = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cost_micros = models.BigIntegerField(default=0)
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = (
            "tenant",
            "customer_id",
            "campaign_id",
            "date_day",
            "geo_target_country",
            "geo_target_region",
            "geo_target_city",
        )
        indexes = [
            models.Index(fields=["tenant", "date_day"], name="gads_sdk_geo_day"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_geo_customer"),
        ]


class GoogleAdsSdkKeywordDaily(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_keyword_daily"
    )
    customer_id = models.CharField(max_length=32)
    campaign_id = models.CharField(max_length=64)
    ad_group_id = models.CharField(max_length=64)
    criterion_id = models.CharField(max_length=64)
    keyword_text = models.CharField(max_length=255, blank=True)
    match_type = models.CharField(max_length=32, blank=True)
    criterion_status = models.CharField(max_length=32, blank=True)
    quality_score = models.IntegerField(null=True, blank=True)
    ad_relevance = models.CharField(max_length=32, blank=True)
    expected_ctr = models.CharField(max_length=32, blank=True)
    landing_page_experience = models.CharField(max_length=32, blank=True)
    date_day = models.DateField()
    currency_code = models.CharField(max_length=16, blank=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    conversions_value = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cost_micros = models.BigIntegerField(default=0)
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = (
            "tenant",
            "customer_id",
            "campaign_id",
            "ad_group_id",
            "criterion_id",
            "date_day",
        )
        indexes = [
            models.Index(fields=["tenant", "date_day"], name="gads_sdk_keyword_day"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_keyword_customer"),
        ]


class GoogleAdsSdkSearchTermDaily(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_search_term_daily"
    )
    customer_id = models.CharField(max_length=32)
    campaign_id = models.CharField(max_length=64)
    ad_group_id = models.CharField(max_length=64)
    criterion_id = models.CharField(max_length=64, blank=True)
    search_term = models.CharField(max_length=255)
    date_day = models.DateField()
    currency_code = models.CharField(max_length=16, blank=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    conversions_value = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cost_micros = models.BigIntegerField(default=0)
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = (
            "tenant",
            "customer_id",
            "campaign_id",
            "ad_group_id",
            "search_term",
            "date_day",
        )
        indexes = [
            models.Index(fields=["tenant", "date_day"], name="gads_sdk_search_term_day"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_search_term_customer"),
        ]


class GoogleAdsSdkAssetGroupDaily(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_asset_group_daily"
    )
    customer_id = models.CharField(max_length=32)
    campaign_id = models.CharField(max_length=64)
    asset_group_id = models.CharField(max_length=64)
    asset_group_name = models.CharField(max_length=255, blank=True)
    asset_group_status = models.CharField(max_length=32, blank=True)
    date_day = models.DateField()
    currency_code = models.CharField(max_length=16, blank=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    conversions_value = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cost_micros = models.BigIntegerField(default=0)
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = (
            "tenant",
            "customer_id",
            "campaign_id",
            "asset_group_id",
            "date_day",
        )
        indexes = [
            models.Index(fields=["tenant", "date_day"], name="gads_sdk_asset_group_day"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_asset_group_customer"),
        ]


class GoogleAdsSdkConversionActionDaily(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_conversion_action_daily"
    )
    customer_id = models.CharField(max_length=32)
    conversion_action_id = models.CharField(max_length=64)
    conversion_action_name = models.CharField(max_length=255, blank=True)
    conversion_action_type = models.CharField(max_length=64, blank=True)
    date_day = models.DateField()
    conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    all_conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    conversions_value = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = (
            "tenant",
            "customer_id",
            "conversion_action_id",
            "date_day",
        )
        indexes = [
            models.Index(fields=["tenant", "date_day"], name="gads_sdk_conv_action_day"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_conv_action_customer"),
        ]


class GoogleAdsSdkChangeEvent(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_change_events"
    )
    customer_id = models.CharField(max_length=32)
    event_fingerprint = models.CharField(max_length=64)
    change_date_time = models.DateTimeField()
    user_email = models.CharField(max_length=255, blank=True)
    client_type = models.CharField(max_length=64, blank=True)
    change_resource_type = models.CharField(max_length=64, blank=True)
    resource_change_operation = models.CharField(max_length=64, blank=True)
    campaign_id = models.CharField(max_length=64, blank=True)
    ad_group_id = models.CharField(max_length=64, blank=True)
    ad_id = models.CharField(max_length=64, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    source_request_id = models.CharField(max_length=128, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "customer_id", "event_fingerprint")
        indexes = [
            models.Index(fields=["tenant", "change_date_time"], name="gads_sdk_change_event_ts"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_change_event_customer"),
        ]


class GoogleAdsSdkRecommendation(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sdk_recommendations"
    )
    customer_id = models.CharField(max_length=32)
    recommendation_type = models.CharField(max_length=64)
    resource_name = models.CharField(max_length=255)
    campaign_id = models.CharField(max_length=64, blank=True)
    ad_group_id = models.CharField(max_length=64, blank=True)
    dismissed = models.BooleanField(default=False)
    impact_metadata = models.JSONField(default=dict, blank=True)
    source_request_id = models.CharField(max_length=128, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "customer_id", "recommendation_type", "resource_name")
        indexes = [
            models.Index(fields=["tenant", "dismissed"], name="gads_sdk_reco_tenant_dismissed"),
            models.Index(fields=["tenant", "customer_id"], name="gads_sdk_reco_tenant_customer"),
        ]


class GoogleAdsAccountMapping(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_account_mappings"
    )
    manager_customer_id = models.CharField(max_length=32, blank=True)
    customer_id = models.CharField(max_length=32)
    customer_name = models.CharField(max_length=255, blank=True)
    currency_code = models.CharField(max_length=16, blank=True)
    time_zone = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=64, blank=True)
    is_manager = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "customer_id")
        indexes = [
            models.Index(fields=["tenant", "customer_id"], name="gads_acct_map_tenant_customer"),
        ]


class GoogleAdsAccountAssignment(models.Model):
    ACCESS_ANALYST = "analyst"
    ACCESS_ACCOUNT_MANAGER = "account_manager"
    ACCESS_CLIENT_READ_ONLY = "client_read_only"
    ACCESS_CHOICES = [
        (ACCESS_ANALYST, "Analyst"),
        (ACCESS_ACCOUNT_MANAGER, "Account Manager"),
        (ACCESS_CLIENT_READ_ONLY, "Client Read Only"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_account_assignments"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="google_ads_account_assignments"
    )
    customer_id = models.CharField(max_length=32)
    access_level = models.CharField(max_length=32, choices=ACCESS_CHOICES, default=ACCESS_ANALYST)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "user", "customer_id")
        indexes = [
            models.Index(fields=["tenant", "user"], name="gads_acct_assign_tenant_user"),
            models.Index(fields=["tenant", "customer_id"], name="gads_assign_tenant_cust"),
        ]


class GoogleAdsSyncState(models.Model):
    ENGINE_SDK = "sdk"
    ENGINE_AIRBYTE = "airbyte"
    ENGINE_CHOICES = [
        (ENGINE_SDK, "SDK"),
        (ENGINE_AIRBYTE, "Airbyte"),
    ]

    PARITY_UNKNOWN = "unknown"
    PARITY_PASS = "pass"
    PARITY_FAIL = "fail"
    PARITY_CHOICES = [
        (PARITY_UNKNOWN, "Unknown"),
        (PARITY_PASS, "Pass"),
        (PARITY_FAIL, "Fail"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_sync_states"
    )
    account_id = models.CharField(max_length=64)
    desired_engine = models.CharField(
        max_length=16, choices=ENGINE_CHOICES, default=ENGINE_SDK
    )
    effective_engine = models.CharField(
        max_length=16, choices=ENGINE_CHOICES, default=ENGINE_SDK
    )
    fallback_active = models.BooleanField(default=False)
    parity_state = models.CharField(
        max_length=16, choices=PARITY_CHOICES, default=PARITY_UNKNOWN
    )
    last_parity_passed_at = models.DateTimeField(null=True, blank=True)
    consecutive_sdk_failures = models.PositiveIntegerField(default=0)
    consecutive_parity_failures = models.PositiveIntegerField(default=0)
    last_sync_attempt_at = models.DateTimeField(null=True, blank=True)
    last_sync_success_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)
    rollback_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "account_id")
        indexes = [
            models.Index(fields=["tenant", "effective_engine"], name="gads_sync_tenant_engine"),
            models.Index(fields=["tenant", "parity_state"], name="gads_sync_tenant_parity"),
        ]


class GoogleAdsParityRun(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="google_ads_parity_runs"
    )
    account_id = models.CharField(max_length=64)
    window_start = models.DateField()
    window_end = models.DateField()
    sdk_spend = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    sdk_clicks = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    sdk_conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    baseline_spend = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    baseline_clicks = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    baseline_conversions = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    spend_delta_pct = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    clicks_delta_pct = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    conversions_delta_pct = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    passed = models.BooleanField(default=False)
    reasons = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "account_id", "window_start", "window_end")
        indexes = [
            models.Index(fields=["tenant", "created_at"], name="gads_parity_tenant_created"),
            models.Index(fields=["tenant", "passed"], name="gads_parity_tenant_passed"),
        ]


class APIErrorLog(models.Model):
    """Structured upstream API failures for remediation workflows."""

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="api_error_logs"
    )
    provider = models.CharField(
        max_length=16,
        choices=PlatformCredential.PROVIDER_CHOICES,
        default=PlatformCredential.META,
    )
    endpoint = models.CharField(max_length=255, blank=True)
    account_id = models.CharField(max_length=128, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    error_subcode = models.CharField(max_length=64, blank=True)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=128, blank=True)
    is_retryable = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "provider", "created_at"], name="apierr_tenant_provider_ts"),
            models.Index(fields=["tenant", "account_id"], name="apierr_tenant_account"),
        ]


@dataclass(frozen=True)
class ConnectionSyncUpdate:
    """Persisted Airbyte sync metadata for a specific connection."""

    connection: "AirbyteConnection"
    job_id: str | None
    status: str | None
    created_at: datetime
    updated_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None
    records_synced: int | None
    bytes_synced: int | None
    api_cost: Decimal | None
    error: str | None


class AirbyteJobTelemetry(models.Model):
    """Snapshot of metrics returned by an Airbyte sync attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="airbyte_job_telemetry"
    )
    connection = models.ForeignKey(
        AirbyteConnection, on_delete=models.CASCADE, related_name="job_telemetry"
    )
    job_id = models.CharField(max_length=64)
    status = models.CharField(max_length=32)
    started_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    records_synced = models.BigIntegerField(null=True, blank=True)
    bytes_synced = models.BigIntegerField(null=True, blank=True)
    api_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-started_at", "-created_at")
        unique_together = ("connection", "job_id")

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"AirbyteJobTelemetry<{self.connection_id}:{self.job_id}>"


class CampaignBudget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="campaign_budgets"
    )
    name = models.CharField(max_length=255)
    monthly_target = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "name")
        ordering = ("name",)

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"CampaignBudget<{self.name}>"


class AlertRuleDefinition(models.Model):
    OPERATOR_GREATER_THAN = "gt"
    OPERATOR_GREATER_THAN_EQUAL = "gte"
    OPERATOR_LESS_THAN = "lt"
    OPERATOR_LESS_THAN_EQUAL = "lte"
    COMPARISON_CHOICES = [
        (OPERATOR_GREATER_THAN, "greater_than"),
        (OPERATOR_GREATER_THAN_EQUAL, "greater_than_equal"),
        (OPERATOR_LESS_THAN, "less_than"),
        (OPERATOR_LESS_THAN_EQUAL, "less_than_equal"),
    ]

    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, "low"),
        (SEVERITY_MEDIUM, "medium"),
        (SEVERITY_HIGH, "high"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="alert_rule_definitions"
    )
    name = models.CharField(max_length=255)
    metric = models.CharField(max_length=64)
    comparison_operator = models.CharField(
        max_length=3, choices=COMPARISON_CHOICES, default=OPERATOR_GREATER_THAN
    )
    threshold = models.DecimalField(max_digits=12, decimal_places=2)
    lookback_hours = models.PositiveIntegerField(default=24)
    severity = models.CharField(
        max_length=6, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "name")
        ordering = ("name",)

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"AlertRuleDefinition<{self.name}>"
