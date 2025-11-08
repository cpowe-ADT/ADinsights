"""Helpers for managing tenant data-encryption keys."""

from __future__ import annotations

import logging
import os

from django.conf import settings
from accounts.models import Tenant, TenantKey
from accounts.tenant_context import tenant_context

from .fields import decrypt_value, encrypt_value
from .kms import KmsError, get_kms_client


logger = logging.getLogger(__name__)


def _kms():
    return get_kms_client(
        settings.KMS_PROVIDER,
        settings.KMS_KEY_ID,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        aws_session_token=settings.AWS_SESSION_TOKEN,
    )


def get_dek_for_tenant(tenant: Tenant) -> tuple[bytes, str]:
    kms_client = _kms()
    tenant_key = TenantKey.all_objects.filter(tenant=tenant).first()
    try:
        if not tenant_key:
            plaintext = os.urandom(32)
            version, ciphertext = kms_client.encrypt(plaintext)
            tenant_key = TenantKey.all_objects.create(
                tenant=tenant,
                dek_ciphertext=ciphertext,
                dek_key_version=version,
            )
            return plaintext, version
        plaintext = kms_client.decrypt(
            tenant_key.dek_ciphertext, tenant_key.dek_key_version
        )
        return plaintext, tenant_key.dek_key_version
    except KmsError:
        logger.exception(
            "Failed to retrieve DEK for tenant %s due to KMS error", tenant.id
        )
        raise


def rotate_all_tenant_deks() -> int:
    from integrations.models import PlatformCredential

    kms_client = _kms()
    rotated = 0
    for tenant_key in TenantKey.all_objects.select_related("tenant"):
        tenant_id = str(tenant_key.tenant_id)
        try:
            with tenant_context(tenant_id):
                old_key = kms_client.decrypt(
                    tenant_key.dek_ciphertext, tenant_key.dek_key_version
                )
                new_key = os.urandom(32)
                version, ciphertext = kms_client.encrypt(new_key)

                for credential in PlatformCredential.all_objects.filter(
                    tenant=tenant_key.tenant
                ):
                    access_plain = decrypt_value(
                        credential.access_token_enc,
                        credential.access_token_nonce,
                        credential.access_token_tag,
                        old_key,
                    )
                    refresh_plain = None
                    if credential.refresh_token_enc:
                        refresh_plain = decrypt_value(
                            credential.refresh_token_enc,
                            credential.refresh_token_nonce,
                            credential.refresh_token_tag,
                            old_key,
                        )
                    if access_plain:
                        encrypted = encrypt_value(access_plain, new_key)
                        if encrypted:
                            credential.access_token_enc = encrypted.ciphertext
                            credential.access_token_nonce = encrypted.nonce
                            credential.access_token_tag = encrypted.tag
                    if refresh_plain:
                        encrypted_refresh = encrypt_value(refresh_plain, new_key)
                        if encrypted_refresh:
                            credential.refresh_token_enc = encrypted_refresh.ciphertext
                            credential.refresh_token_nonce = encrypted_refresh.nonce
                            credential.refresh_token_tag = encrypted_refresh.tag
                    credential.dek_key_version = version
                    credential.save(
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

                tenant_key.dek_ciphertext = ciphertext
                tenant_key.dek_key_version = version
                tenant_key.save(
                    update_fields=["dek_ciphertext", "dek_key_version", "updated_at"]
                )
                rotated += 1
        except KmsError as error:
            logger.exception(
                "Skipping DEK rotation for tenant %s due to KMS error: %s",
                tenant_key.tenant_id,
                error,
            )
            continue
    return rotated
