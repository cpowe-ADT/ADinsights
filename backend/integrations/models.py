from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

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

    class Meta:
        unique_together = ("tenant", "provider", "account_id")

    def set_raw_tokens(
        self, access_token: Optional[str], refresh_token: Optional[str]
    ) -> None:
        self._raw_access_token = access_token
        self._raw_refresh_token = refresh_token

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            raise ValueError("Tenant must be set before saving PlatformCredential")
        if (
            self._raw_access_token is not None
            or self._raw_refresh_token is not None
            or not self.dek_key_version
        ):
            key, version = get_dek_for_tenant(self.tenant)
            if self._raw_access_token is not None:
                encrypted = encrypt_value(self._raw_access_token, key)
                if encrypted:
                    self.access_token_enc = encrypted.ciphertext
                    self.access_token_nonce = encrypted.nonce
                    self.access_token_tag = encrypted.tag
            if self._raw_refresh_token is not None:
                encrypted_refresh = encrypt_value(self._raw_refresh_token, key)
                if encrypted_refresh:
                    self.refresh_token_enc = encrypted_refresh.ciphertext
                    self.refresh_token_nonce = encrypted_refresh.nonce
                    self.refresh_token_tag = encrypted_refresh.tag
            self.dek_key_version = version
        super().save(*args, **kwargs)
        self._raw_access_token = None
        self._raw_refresh_token = None

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

    def record_sync(self, job_id: int | None, job_status: str, job_created_at: datetime) -> None:
        self.last_synced_at = job_created_at
        self.last_job_created_at = job_created_at
        self.last_job_id = str(job_id) if job_id is not None else ""
        self.last_job_status = job_status or ""
        self.save(
            update_fields=[
                "last_synced_at",
                "last_job_created_at",
                "last_job_id",
                "last_job_status",
                "updated_at",
            ]
        )


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
        self.save(
            update_fields=[
                "last_connection",
                "last_synced_at",
                "last_job_id",
                "last_job_status",
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
            status.save(
                update_fields=[
                    "last_connection",
                    "last_synced_at",
                    "last_job_id",
                    "last_job_status",
                    "updated_at",
                ]
            )
            return status
        status.record_connection(connection)
        return status
