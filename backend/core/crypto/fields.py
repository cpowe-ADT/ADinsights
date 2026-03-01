from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class EncryptedValue:
    ciphertext: bytes
    nonce: bytes
    tag: bytes


BinaryLike = Union[bytes, bytearray, memoryview]


def _to_bytes(value: BinaryLike) -> bytes:
    if isinstance(value, memoryview):
        return value.tobytes()
    return bytes(value)


def encrypt_value(value: Optional[str], key: bytes) -> Optional[EncryptedValue]:
    if value in (None, ""):
        return None
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    encrypted = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    return EncryptedValue(ciphertext=encrypted[:-16], nonce=nonce, tag=encrypted[-16:])


def decrypt_value(
    ciphertext: BinaryLike, nonce: BinaryLike, tag: BinaryLike, key: bytes
) -> Optional[str]:
    aesgcm = AESGCM(key)
    nonce_bytes = _to_bytes(nonce)
    ciphertext_bytes = _to_bytes(ciphertext)
    tag_bytes = _to_bytes(tag)
    decrypted = aesgcm.decrypt(nonce_bytes, ciphertext_bytes + tag_bytes, None)
    return decrypted.decode("utf-8")
