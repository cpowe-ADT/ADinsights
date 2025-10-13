from __future__ import annotations

from unittest.mock import Mock

import os

import pytest

from accounts.models import Tenant, TenantKey
from core.crypto.dek_manager import rotate_all_tenant_deks
from core.crypto.fields import decrypt_value, encrypt_value
from core.crypto.kms import KmsError
from integrations.models import PlatformCredential


def _patch_urandom(monkeypatch: pytest.MonkeyPatch, keys: list[bytes]) -> None:
    original = os.urandom

    def fake_urandom(length: int) -> bytes:
        if length == 32 and keys:
            return keys.pop(0)
        return original(length)

    monkeypatch.setattr("core.crypto.dek_manager.os.urandom", fake_urandom)


def _create_credential(tenant: Tenant, key: bytes, version: str) -> PlatformCredential:
    encrypted = encrypt_value("access-token", key)
    assert encrypted is not None
    refresh_encrypted = encrypt_value("refresh-token", key)
    assert refresh_encrypted is not None
    return PlatformCredential.all_objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="acct",
        access_token_enc=encrypted.ciphertext,
        access_token_nonce=encrypted.nonce,
        access_token_tag=encrypted.tag,
        refresh_token_enc=refresh_encrypted.ciphertext,
        refresh_token_nonce=refresh_encrypted.nonce,
        refresh_token_tag=refresh_encrypted.tag,
        dek_key_version=version,
    )


def test_rotate_all_tenant_deks_updates_records(db, monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = Tenant.objects.create(name="Tenant A")
    tenant_key = TenantKey.all_objects.create(
        tenant=tenant,
        dek_ciphertext=b"oldcipher",
        dek_key_version="old-version",
    )
    old_key = b"\x01" * 32
    credential = _create_credential(tenant, old_key, "old-version")

    kms_client = Mock()
    kms_client.decrypt.return_value = old_key
    kms_client.encrypt.return_value = ("new-version", b"newcipher")
    monkeypatch.setattr("core.crypto.dek_manager._kms", lambda: kms_client)
    _patch_urandom(monkeypatch, [b"\x02" * 32])

    rotated = rotate_all_tenant_deks()

    assert rotated == 1
    tenant_key.refresh_from_db()
    assert tenant_key.dek_key_version == "new-version"
    assert tenant_key.dek_ciphertext == b"newcipher"

    credential.refresh_from_db()
    assert credential.dek_key_version == "new-version"
    assert (
        decrypt_value(
            credential.access_token_enc,
            credential.access_token_nonce,
            credential.access_token_tag,
            b"\x02" * 32,
        )
        == "access-token"
    )
    assert (
        decrypt_value(
            credential.refresh_token_enc,
            credential.refresh_token_nonce,
            credential.refresh_token_tag,
            b"\x02" * 32,
        )
        == "refresh-token"
    )
    kms_client.encrypt.assert_called_once()
    kms_client.decrypt.assert_called_once()


def test_rotate_all_tenant_deks_skips_failed_tenant(db, monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_error = Tenant.objects.create(name="Tenant Error")
    tenant_ok = Tenant.objects.create(name="Tenant OK")

    tenant_key_error = TenantKey.all_objects.create(
        tenant=tenant_error,
        dek_ciphertext=b"errorcipher",
        dek_key_version="error-version",
    )
    tenant_key_ok = TenantKey.all_objects.create(
        tenant=tenant_ok,
        dek_ciphertext=b"okcipher",
        dek_key_version="ok-version",
    )

    old_key = b"\x01" * 32
    _create_credential(tenant_error, old_key, "error-version")
    _create_credential(tenant_ok, old_key, "ok-version")

    kms_client = Mock()
    kms_client.decrypt.side_effect = [KmsError("boom"), old_key]
    kms_client.encrypt.return_value = ("rotated", b"rotatedcipher")
    monkeypatch.setattr("core.crypto.dek_manager._kms", lambda: kms_client)
    _patch_urandom(monkeypatch, [b"\x03" * 32])

    rotated = rotate_all_tenant_deks()

    assert rotated == 1

    tenant_key_error.refresh_from_db()
    assert tenant_key_error.dek_key_version == "error-version"
    assert tenant_key_error.dek_ciphertext == b"errorcipher"

    tenant_key_ok.refresh_from_db()
    assert tenant_key_ok.dek_key_version == "rotated"
    assert tenant_key_ok.dek_ciphertext == b"rotatedcipher"

    kms_client.encrypt.assert_called_once()
    assert kms_client.decrypt.call_count == 2
