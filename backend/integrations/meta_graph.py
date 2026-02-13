from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings


class MetaGraphConfigurationError(RuntimeError):
    """Raised when Meta OAuth settings are incomplete."""


class MetaGraphClientError(RuntimeError):
    """Raised when Meta Graph API requests fail."""


@dataclass(slots=True)
class MetaPage:
    id: str
    name: str
    access_token: str
    category: str | None = None
    tasks: list[str] | None = None
    perms: list[str] | None = None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "tasks": self.tasks or [],
            "perms": self.perms or [],
        }


class MetaGraphClient:
    """HTTP client for the Meta Graph API OAuth + page listing workflow."""

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        graph_version: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = f"https://graph.facebook.com/{graph_version}"
        self._client = httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_settings(cls) -> "MetaGraphClient":
        app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        app_secret = (getattr(settings, "META_APP_SECRET", "") or "").strip()
        if not app_id or not app_secret:
            raise MetaGraphConfigurationError(
                "META_APP_ID and META_APP_SECRET must be configured for Meta OAuth."
            )
        graph_version = (getattr(settings, "META_GRAPH_API_VERSION", "v20.0") or "v20.0").strip()
        return cls(app_id=app_id, app_secret=app_secret, graph_version=graph_version)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MetaGraphClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - context manager contract
        self.close()

    def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        response = self._client.get(
            f"{self.base_url}/oauth/access_token",
            params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        payload = self._parse_response(response)
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise MetaGraphClientError("Meta OAuth token exchange succeeded without an access token.")
        return access_token

    def list_pages(self, *, user_access_token: str) -> list[MetaPage]:
        response = self._client.get(
            f"{self.base_url}/me/accounts",
            params={
                "fields": "id,name,access_token,category,tasks,perms",
                "access_token": user_access_token,
            },
        )
        payload = self._parse_response(response)
        rows = payload.get("data")
        if not isinstance(rows, list):
            return []
        pages: list[MetaPage] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            page_id = row.get("id")
            page_name = row.get("name")
            page_access_token = row.get("access_token")
            if not isinstance(page_id, str) or not isinstance(page_name, str):
                continue
            if not isinstance(page_access_token, str) or not page_access_token.strip():
                continue
            tasks = row.get("tasks")
            perms = row.get("perms")
            pages.append(
                MetaPage(
                    id=page_id,
                    name=page_name,
                    access_token=page_access_token,
                    category=row.get("category") if isinstance(row.get("category"), str) else None,
                    tasks=[task for task in tasks if isinstance(task, str)] if isinstance(tasks, list) else [],
                    perms=[perm for perm in perms if isinstance(perm, str)] if isinstance(perms, list) else [],
                )
            )
        return pages

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise MetaGraphClientError("Meta Graph API returned a non-JSON response.") from exc
        if not response.is_success:
            message = self._extract_error_message(payload)
            raise MetaGraphClientError(message or f"Meta Graph API returned HTTP {response.status_code}.")
        if not isinstance(payload, dict):
            raise MetaGraphClientError("Meta Graph API returned an unexpected response payload.")
        return payload

    @staticmethod
    def _extract_error_message(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            message = error_payload.get("message")
            if isinstance(message, str) and message.strip():
                return message
        detail = payload.get("error_description")
        if isinstance(detail, str) and detail.strip():
            return detail
        return None
