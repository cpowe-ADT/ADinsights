from __future__ import annotations

import boto3
import pytest

try:  # pragma: no cover - import guard for optional dependency
    from moto import mock_aws
except ImportError:  # pragma: no cover - skip tests when moto missing
    pytest.skip("moto is required for KMS tests", allow_module_level=True)
pytest.importorskip("moto")

# ruff: noqa: E402 - moto must be imported after pytest.importorskip
from moto import mock_aws

from core.crypto.kms import AwsKmsClient


@mock_aws
def test_aws_kms_client_round_trip():
    kms = boto3.client("kms", region_name="us-east-1")
    key_arn = kms.create_key()["KeyMetadata"]["Arn"]

    client = AwsKmsClient(key_id=key_arn, region_name="us-east-1")

    version, ciphertext = client.encrypt(b"secret-bytes")
    assert version.startswith(key_arn)

    plaintext = client.decrypt(ciphertext, version)
    assert plaintext == b"secret-bytes"

    new_version, new_ciphertext = client.rewrap(ciphertext, version)
    assert new_version != version
    assert client.decrypt(new_ciphertext, new_version) == b"secret-bytes"
