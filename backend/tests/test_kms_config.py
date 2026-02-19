from __future__ import annotations

import pytest

from core.crypto.kms import (
    KmsConfigurationError,
    LocalKmsClient,
    _infer_region_from_key_id,
    _validate_aws_key_id,
    validate_kms_configuration,
)


def test_infer_region_from_kms_arn() -> None:
    arn = "arn:aws:kms:us-east-1:123456789012:key/abcd-1234"
    assert _infer_region_from_key_id(arn) == "us-east-1"


def test_validate_aws_key_id_rejects_placeholders() -> None:
    placeholder = "arn:aws:kms:REGION:ACCOUNT:key/00000000-0000-0000-0000-000000000000"
    with pytest.raises(KmsConfigurationError):
        _validate_aws_key_id(placeholder, "us-east-1")


def test_validate_aws_key_id_rejects_region_mismatch() -> None:
    arn = "arn:aws:kms:us-east-1:123456789012:key/abcd-1234"
    with pytest.raises(KmsConfigurationError):
        _validate_aws_key_id(arn, "us-west-2")


def test_validate_kms_configuration_accepts_alias_with_region() -> None:
    validate_kms_configuration("aws", "alias/adinsights-prod", "us-east-1")


def test_validate_kms_configuration_requires_region_for_non_arn() -> None:
    with pytest.raises(KmsConfigurationError):
        validate_kms_configuration("aws", "alias/adinsights-prod", None)


def test_local_kms_recovers_after_process_restart() -> None:
    LocalKmsClient._store.clear()
    client = LocalKmsClient("local-dev-kms")

    version, ciphertext = client.encrypt(b"tenant-dek")
    LocalKmsClient._store.clear()

    assert client.decrypt(ciphertext, version) == b"tenant-dek"
