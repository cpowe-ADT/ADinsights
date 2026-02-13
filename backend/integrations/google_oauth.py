from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx


class GoogleOAuthConfigurationError(RuntimeError):
    """Raised when Google OAuth settings are incomplete."""


class GoogleOAuthClientError(RuntimeError):
    """Raised when Google OAuth endpoints return an error."""


@dataclass(frozen=True)
class GoogleOAuthToken:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    token_type: str | None
    scope: str | None


@dataclass
class GoogleOAuthClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    timeout: float = 20.0

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    @classmethod
    def from_settings(cls, settings) -> "GoogleOAuthClient":
        client_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or "").strip()
        redirect_uri = (getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or "").strip()
        if not client_id or not client_secret or not redirect_uri:
            raise GoogleOAuthConfigurationError(
                "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and "
                "GOOGLE_OAUTH_REDIRECT_URI must be configured."
            )
        return cls(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

    def build_authorize_url(self, *, state: str, scopes: list[str]) -> str:
        if not scopes:
            raise GoogleOAuthConfigurationError("Google OAuth scopes are not configured.")
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
            }
        )
        return f"{self.AUTHORIZE_URL}?{query}"

    def exchange_code(self, *, code: str) -> GoogleOAuthToken:
        payload = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            response = httpx.post(
                self.TOKEN_URL,
                data=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            message = ""
            if exc.response is not None:
                try:
                    data = exc.response.json()
                except ValueError:
                    data = {}
                message = data.get("error_description") or data.get("error") or exc.response.text
            raise GoogleOAuthClientError(message or "Google OAuth token exchange failed.") from exc

        token_data = response.json()
        access_token = (token_data.get("access_token") or "").strip()
        if not access_token:
            raise GoogleOAuthClientError("Google OAuth token exchange returned no access token.")

        refresh_token = token_data.get("refresh_token")
        if isinstance(refresh_token, str):
            refresh_token = refresh_token.strip() or None
        else:
            refresh_token = None

        expires_in_raw = token_data.get("expires_in")
        try:
            expires_in = int(expires_in_raw) if expires_in_raw is not None else None
        except (TypeError, ValueError):
            expires_in = None

        token_type = token_data.get("token_type")
        scope = token_data.get("scope")
        return GoogleOAuthToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
            scope=scope,
        )

