from __future__ import annotations

import uuid
from typing import Optional

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
