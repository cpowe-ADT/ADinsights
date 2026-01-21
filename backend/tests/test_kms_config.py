from __future__ import annotations

import pytest

from core.crypto.kms import KmsConfigurationError, _infer_region_from_key_id, _validate_aws_key_id


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
