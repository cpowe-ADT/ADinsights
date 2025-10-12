from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx
from cryptography.fernet import Fernet

from .config import SettingsType, get_settings


class TokenEncryptor:
    def __init__(self, settings: SettingsType | None = None) -> None:
        self._settings = settings or get_settings()
        key = self._derive_key(self._settings.secret_key)
        self._fernet = Fernet(key)

    @staticmethod
    def _derive_key(secret: str) -> bytes:
        digest = secret.encode("utf-8").ljust(32, b"0")[:32]
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")


class OAuthProvider:
    def __init__(self, settings: SettingsType | None = None) -> None:
        self.settings = settings or get_settings()

    def build_authorization_url(self, platform: str, state: str, scopes: list[str]) -> str:
        base_urls: Dict[str, str] = {
            "meta": "https://www.facebook.com/v19.0/dialog/oauth",
            "google_ads": "https://accounts.google.com/o/oauth2/v2/auth",
        }
        client_ids: Dict[str, str] = {
            "meta": self.settings.meta_client_id,
            "google_ads": self.settings.google_ads_client_id,
        }
        if platform not in base_urls:
            raise ValueError(f"Unsupported platform: {platform}")

        redirect_uri = self._redirect_uri(platform)
        query_params = {
            "client_id": client_ids[platform],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
        }
        encoded_params = httpx.QueryParams(query_params)
        return f"{base_urls[platform]}?{encoded_params}"

    async def exchange_code_for_token(
        self,
        platform: str,
        code: str,
    ) -> dict[str, Any]:
        token_urls: Dict[str, str] = {
            "meta": "https://graph.facebook.com/v19.0/oauth/access_token",
            "google_ads": "https://oauth2.googleapis.com/token",
        }
        client_credentials: Dict[str, tuple[str, str]] = {
            "meta": (self.settings.meta_client_id, self.settings.meta_client_secret),
            "google_ads": (self.settings.google_ads_client_id, self.settings.google_ads_client_secret),
        }

        if platform not in token_urls:
            raise ValueError(f"Unsupported platform: {platform}")

        redirect_uri = self._redirect_uri(platform)
        client_id, client_secret = client_credentials[platform]

        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(token_urls[platform], data=payload)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            return data

    def _redirect_uri(self, platform: str) -> str:
        return f"{self.settings.oauth_redirect_base_url}/oauth/{platform}/callback"


def compute_expiry(expires_in: Optional[int]) -> Optional[datetime]:
    if expires_in is None:
        return None
    return datetime.utcnow() + timedelta(seconds=expires_in)


def generate_state() -> str:
    return base64.urlsafe_b64encode(os.urandom(24)).decode("utf-8")
