from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Dict, Protocol, Tuple

import boto3
import hashlib
from botocore.client import BaseClient
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
    ReadTimeoutError,
)


class KmsError(RuntimeError):
    """Wraps errors emitted from the configured KMS provider."""


class KmsConfigurationError(KmsError):
    """Raised when KMS settings are invalid or incomplete."""


class KmsUnavailableError(KmsError):
    """Raised when the configured KMS provider cannot be reached."""


class KmsClient(Protocol):
    def encrypt(self, plaintext: bytes) -> Tuple[str, bytes]: ...

    def decrypt(self, ciphertext: bytes, key_version: str) -> bytes: ...

    def rewrap(self, ciphertext: bytes, current_version: str) -> Tuple[str, bytes]: ...


@dataclass
class LocalKmsClient:
    """Ephemeral in-process KMS implementation for development/tests."""

    key_id: str
    _store: ClassVar[Dict[str, bytes]] = {}

    def encrypt(self, plaintext: bytes) -> Tuple[str, bytes]:
        version = _build_version(self.key_id, plaintext)
        self._store[version] = plaintext
        # ciphertext is identical to plaintext for local usage.
        return version, plaintext

    def decrypt(self, ciphertext: bytes, key_version: str) -> bytes:  # noqa: ARG002 - ciphertext unused
        try:
            return self._store[key_version]
        except KeyError as exc:  # pragma: no cover - defensive path
            raise KmsError(f"Unknown key version {key_version}") from exc

    def rewrap(self, ciphertext: bytes, current_version: str) -> Tuple[str, bytes]:  # noqa: ARG002 - ciphertext unused
        plaintext = self.decrypt(ciphertext, current_version)
        return self.encrypt(plaintext)


@dataclass
class AwsKmsClient:
    key_id: str
    region_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    _client: BaseClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        resolved_region = self.region_name or _infer_region_from_key_id(self.key_id)
        _validate_aws_key_id(self.key_id, resolved_region)

        client_kwargs = {}
        if resolved_region:
            client_kwargs["region_name"] = resolved_region
        if self.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = self.aws_secret_access_key
        if self.aws_session_token:
            client_kwargs["aws_session_token"] = self.aws_session_token
        try:
            self._client = boto3.client("kms", **client_kwargs)
        except NoRegionError as exc:
            raise KmsConfigurationError(
                "AWS region is required for KMS. Set AWS_REGION or use a KMS key ARN."
            ) from exc

    def encrypt(self, plaintext: bytes) -> Tuple[str, bytes]:
        try:
            response = self._client.encrypt(KeyId=self.key_id, Plaintext=plaintext)
        except (
            EndpointConnectionError,
            ConnectionClosedError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as exc:  # pragma: no cover - boto error path
            raise KmsUnavailableError("AWS KMS endpoint is unreachable") from exc
        except NoCredentialsError as exc:  # pragma: no cover - boto error path
            raise KmsConfigurationError("AWS credentials are not configured") from exc
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
        except (
            EndpointConnectionError,
            ConnectionClosedError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as exc:  # pragma: no cover - boto error path
            raise KmsUnavailableError("AWS KMS endpoint is unreachable") from exc
        except NoCredentialsError as exc:  # pragma: no cover - boto error path
            raise KmsConfigurationError("AWS credentials are not configured") from exc
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
        except (
            EndpointConnectionError,
            ConnectionClosedError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as exc:  # pragma: no cover - boto error path
            raise KmsUnavailableError("AWS KMS endpoint is unreachable") from exc
        except NoCredentialsError as exc:  # pragma: no cover - boto error path
            raise KmsConfigurationError("AWS credentials are not configured") from exc
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
    normalized_provider = provider.strip().lower()
    validate_kms_configuration(normalized_provider, key_id, region_name)
    if normalized_provider == "aws":
        return AwsKmsClient(
            key_id,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )
    if normalized_provider == "local":
        return LocalKmsClient(key_id)
    raise KmsConfigurationError(f"Unsupported KMS provider: {provider}")


def _extract_key_id(key_version: str) -> str:
    if "|" in key_version:
        return key_version.split("|", 1)[0]
    return key_version


def _build_version(key_id: str, ciphertext: bytes) -> str:
    digest = hashlib.sha256(ciphertext).hexdigest()[:16]
    return f"{key_id}|{digest}"


def _infer_region_from_key_id(key_id: str) -> str | None:
    arn_parts = _parse_kms_arn(key_id)
    if arn_parts:
        return arn_parts[0]
    return None


def _parse_kms_arn(key_id: str) -> tuple[str, str] | None:
    if not key_id.startswith("arn:aws:kms:"):
        return None
    parts = key_id.split(":")
    if len(parts) < 6:
        return None
    region = parts[3]
    account_id = parts[4]
    return region, account_id


def _validate_aws_key_id(key_id: str, region_name: str | None) -> None:
    if not key_id:
        raise KmsConfigurationError("KMS key ID is required for AWS KMS.")
    if "REGION" in key_id or "ACCOUNT" in key_id:
        raise KmsConfigurationError(
            "KMS_KEY_ID contains placeholder values; set a real AWS KMS key ARN or alias."
        )
    if key_id.endswith("00000000-0000-0000-0000-000000000000"):
        raise KmsConfigurationError(
            "KMS_KEY_ID appears to be a placeholder; set a real AWS KMS key ID."
        )
    arn_parts = _parse_kms_arn(key_id)
    if arn_parts and region_name and arn_parts[0] != region_name:
        raise KmsConfigurationError(
            f"KMS_KEY_ID region ({arn_parts[0]}) does not match AWS_REGION ({region_name})."
        )


def validate_kms_configuration(
    provider: str,
    key_id: str,
    region_name: str | None = None,
) -> None:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "aws":
        inferred_region = _infer_region_from_key_id(key_id)
        resolved_region = region_name or inferred_region
        _validate_aws_key_id(key_id, resolved_region)
        if not resolved_region:
            raise KmsConfigurationError(
                "AWS region is required for KMS. Set AWS_REGION or use a KMS key ARN."
            )
        return
    if normalized_provider == "local":
        if not key_id:
            raise KmsConfigurationError("KMS key ID is required for local KMS.")
        return
    raise KmsConfigurationError(f"Unsupported KMS provider: {provider}")
