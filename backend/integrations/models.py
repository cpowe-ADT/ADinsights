from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from croniter import croniter
from django.db import models
from django.utils import timezone

from accounts.models import Tenant, TenantAwareManager
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
