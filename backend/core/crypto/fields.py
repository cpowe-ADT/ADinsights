from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class EncryptedValue:
    ciphertext: bytes
    nonce: bytes
    tag: bytes


def encrypt_value(value: Optional[str], key: bytes) -> Optional[EncryptedValue]:
    if value in (None, ""):
        return None
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    encrypted = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    return EncryptedValue(ciphertext=encrypted[:-16], nonce=nonce, tag=encrypted[-16:])


def decrypt_value(
    ciphertext: bytes, nonce: bytes, tag: bytes, key: bytes
) -> Optional[str]:
    aesgcm = AESGCM(key)
    decrypted = aesgcm.decrypt(nonce, ciphertext + tag, None)
    return decrypted.decode("utf-8")
