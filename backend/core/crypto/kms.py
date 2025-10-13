from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Tuple

import boto3
import hashlib
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError


class KmsError(RuntimeError):
    """Wraps errors emitted from the configured KMS provider."""


class KmsClient(Protocol):
    def encrypt(self, plaintext: bytes) -> Tuple[str, bytes]: ...

    def decrypt(self, ciphertext: bytes, key_version: str) -> bytes: ...

    def rewrap(self, ciphertext: bytes, current_version: str) -> Tuple[str, bytes]: ...


@dataclass
class AwsKmsClient:
    key_id: str
    region_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    _client: BaseClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        client_kwargs = {}
        if self.region_name:
            client_kwargs["region_name"] = self.region_name
        if self.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = self.aws_secret_access_key
        if self.aws_session_token:
            client_kwargs["aws_session_token"] = self.aws_session_token
        self._client = boto3.client("kms", **client_kwargs)

    def encrypt(self, plaintext: bytes) -> Tuple[str, bytes]:
        try:
            response = self._client.encrypt(KeyId=self.key_id, Plaintext=plaintext)
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - boto error path
            raise KmsError("Failed to encrypt with AWS KMS") from exc
        ciphertext = response["CiphertextBlob"]
        key_id = response["KeyId"]
        return _build_version(key_id, ciphertext), ciphertext

    def decrypt(self, ciphertext: bytes, key_version: str) -> bytes:
        try:
            response = self._client.decrypt(
                CiphertextBlob=ciphertext,
                KeyId=_extract_key_id(key_version),
            )
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - boto error path
            raise KmsError("Failed to decrypt with AWS KMS") from exc
        return response["Plaintext"]

    def rewrap(self, ciphertext: bytes, current_version: str) -> Tuple[str, bytes]:
        try:
            response = self._client.re_encrypt(
                CiphertextBlob=ciphertext,
                SourceKeyId=_extract_key_id(current_version),
                DestinationKeyId=self.key_id,
            )
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - boto error path
            raise KmsError("Failed to re-encrypt with AWS KMS") from exc
        ciphertext_blob = response["CiphertextBlob"]
        key_id = response["KeyId"]
        return _build_version(key_id, ciphertext_blob), ciphertext_blob


def get_kms_client(
    provider: str,
    key_id: str,
    *,
    region_name: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
) -> KmsClient:
    if provider == "aws":
        return AwsKmsClient(
            key_id,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )
    raise ValueError(f"Unsupported KMS provider: {provider}")


def _extract_key_id(key_version: str) -> str:
    if "|" in key_version:
        return key_version.split("|", 1)[0]
    return key_version


def _build_version(key_id: str, ciphertext: bytes) -> str:
    digest = hashlib.sha256(ciphertext).hexdigest()[:16]
    return f"{key_id}|{digest}"
