from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass
from typing import Protocol, Tuple


class KmsClient(Protocol):
    def encrypt(self, plaintext: bytes) -> Tuple[str, bytes]: ...

    def decrypt(self, ciphertext: bytes, key_version: str) -> bytes: ...

    def rewrap(self, ciphertext: bytes, current_version: str) -> Tuple[str, bytes]: ...


@dataclass
class AwsKmsClient:
    key_id: str

    def encrypt(self, plaintext: bytes) -> Tuple[str, bytes]:
        version = f"local-{secrets.token_hex(4)}"
        return version, base64.b64encode(plaintext)

    def decrypt(self, ciphertext: bytes, key_version: str) -> bytes:  # noqa: ARG002
        return base64.b64decode(ciphertext)

    def rewrap(
        self, ciphertext: bytes, current_version: str
    ) -> Tuple[str, bytes]:  # noqa: ARG002
        plaintext = self.decrypt(ciphertext, current_version)
        return self.encrypt(plaintext)


def get_kms_client(provider: str, key_id: str) -> KmsClient:
    if provider == "aws":
        return AwsKmsClient(key_id)
    raise ValueError(f"Unsupported KMS provider: {provider}")
