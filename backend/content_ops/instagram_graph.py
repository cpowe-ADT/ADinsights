"""Instagram Graph publisher for Content Operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

from integrations.models import MetaPage

from .models import PublishingIdentity
from .publisher import (
    InstagramMediaContainerPayload,
    InstagramMediaContainerResult,
    InstagramMediaContainerStatusResult,
    InstagramMediaPublishResult,
    InstagramPublishError,
    PROVIDER_NOT_CONFIGURED,
    PROVIDER_RETRYABLE_ERROR,
    PROVIDER_TERMINAL_ERROR,
)

_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_META_ERROR_CODES = {1, 2, 4, 17, 32, 613, 80001}


@dataclass(frozen=True)
class InstagramGraphContainerResponse:
    container_id: str


@dataclass(frozen=True)
class InstagramGraphContainerStatusResponse:
    status_code: str
    status: str = ""


@dataclass(frozen=True)
class InstagramGraphMediaPublishResponse:
    media_id: str
    permalink: str = ""


class InstagramGraphClient:
    def __init__(self, *, graph_version: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = f"https://graph.facebook.com/{graph_version}"
        self._client = httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_settings(cls) -> "InstagramGraphClient":
        graph_version = (
            getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0"
        ).strip()
        timeout_seconds = float(getattr(settings, "META_GRAPH_TIMEOUT_SECONDS", 10.0) or 10.0)
        return cls(graph_version=graph_version, timeout_seconds=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "InstagramGraphClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        self.close()

    def create_media_container(
        self,
        *,
        ig_user_id: str,
        media_url: str,
        caption: str,
        media_type: str,
        access_token: str,
    ) -> InstagramGraphContainerResponse:
        body = _container_body(
            media_url=media_url,
            caption=caption,
            media_type=media_type,
        )
        try:
            response = self._client.post(
                f"{self.base_url}/{ig_user_id}/media",
                data=body,
                headers=_auth_headers(access_token),
            )
        except httpx.HTTPError as exc:
            raise _provider_error(retryable=True, operation="create") from exc

        payload = _safe_json(response)
        if not response.is_success:
            raise _provider_error(
                retryable=_is_retryable(response.status_code, payload),
                operation="create",
            )
        container_id = payload.get("id") if isinstance(payload, dict) else ""
        if not isinstance(container_id, str) or not container_id.strip():
            raise _provider_error(retryable=False, operation="create")
        return InstagramGraphContainerResponse(container_id=container_id.strip())

    def get_media_container_status(
        self,
        *,
        container_id: str,
        access_token: str,
    ) -> InstagramGraphContainerStatusResponse:
        try:
            response = self._client.get(
                f"{self.base_url}/{container_id}",
                params={"fields": "status_code,status"},
                headers=_auth_headers(access_token),
            )
        except httpx.HTTPError as exc:
            raise _provider_error(retryable=True, operation="status") from exc

        payload = _safe_json(response)
        if not response.is_success:
            raise _provider_error(
                retryable=_is_retryable(response.status_code, payload),
                operation="status",
            )
        status_code = payload.get("status_code") if isinstance(payload, dict) else ""
        status = payload.get("status") if isinstance(payload, dict) else ""
        if not isinstance(status_code, str) or not status_code.strip():
            raise _provider_error(retryable=False, operation="status")
        return InstagramGraphContainerStatusResponse(
            status_code=status_code.strip(),
            status=status.strip() if isinstance(status, str) else "",
        )

    def publish_media_container(
        self,
        *,
        ig_user_id: str,
        container_id: str,
        access_token: str,
    ) -> InstagramGraphMediaPublishResponse:
        try:
            response = self._client.post(
                f"{self.base_url}/{ig_user_id}/media_publish",
                data={"creation_id": container_id},
                headers=_auth_headers(access_token),
            )
        except httpx.HTTPError as exc:
            raise _provider_error(retryable=True, operation="publish") from exc

        payload = _safe_json(response)
        if not response.is_success:
            raise _provider_error(
                retryable=_is_retryable(response.status_code, payload),
                operation="publish",
            )
        media_id = payload.get("id") if isinstance(payload, dict) else ""
        if not isinstance(media_id, str) or not media_id.strip():
            raise _provider_error(retryable=False, operation="publish")
        return InstagramGraphMediaPublishResponse(media_id=media_id.strip())


class InstagramGraphPublisher:
    def __init__(self, *, graph_client=None, enabled: bool | None = None) -> None:
        self.graph_client = graph_client
        self.enabled = (
            bool(getattr(settings, "CONTENT_OPS_META_INSTAGRAM_BETA", False))
            if enabled is None
            else enabled
        )

    @classmethod
    def from_settings(cls) -> "InstagramGraphPublisher":
        return cls()

    def create_media_container(
        self,
        payload: InstagramMediaContainerPayload,
    ) -> InstagramMediaContainerResult:
        access_token = self._resolve_access_token(
            tenant_id=payload.tenant_id,
            publishing_identity_id=payload.publishing_identity_id,
            meta_page_id=payload.meta_page_id,
            ig_user_id=payload.ig_user_id,
        )
        if self.graph_client is not None:
            response = self.graph_client.create_media_container(
                ig_user_id=payload.ig_user_id,
                media_url=payload.media_url,
                caption=payload.caption,
                media_type=payload.media_type,
                access_token=access_token,
            )
        else:
            with InstagramGraphClient.from_settings() as client:
                response = client.create_media_container(
                    ig_user_id=payload.ig_user_id,
                    media_url=payload.media_url,
                    caption=payload.caption,
                    media_type=payload.media_type,
                    access_token=access_token,
                )
        return InstagramMediaContainerResult(container_id=response.container_id)

    def get_media_container_status(
        self,
        *,
        tenant_id: str = "",
        publishing_identity_id: str = "",
        meta_page_id: str = "",
        ig_user_id: str,
        container_id: str,
    ) -> InstagramMediaContainerStatusResult:
        access_token = self._resolve_access_token(
            tenant_id=tenant_id,
            publishing_identity_id=publishing_identity_id,
            meta_page_id=meta_page_id,
            ig_user_id=ig_user_id,
        )
        if self.graph_client is not None:
            response = self.graph_client.get_media_container_status(
                container_id=container_id,
                access_token=access_token,
            )
        else:
            with InstagramGraphClient.from_settings() as client:
                response = client.get_media_container_status(
                    container_id=container_id,
                    access_token=access_token,
                )
        return InstagramMediaContainerStatusResult(
            status_code=response.status_code,
            status=response.status,
        )

    def publish_media_container(
        self,
        *,
        tenant_id: str = "",
        publishing_identity_id: str = "",
        meta_page_id: str = "",
        ig_user_id: str,
        container_id: str,
    ) -> InstagramMediaPublishResult:
        access_token = self._resolve_access_token(
            tenant_id=tenant_id,
            publishing_identity_id=publishing_identity_id,
            meta_page_id=meta_page_id,
            ig_user_id=ig_user_id,
        )
        if self.graph_client is not None:
            response = self.graph_client.publish_media_container(
                ig_user_id=ig_user_id,
                container_id=container_id,
                access_token=access_token,
            )
        else:
            with InstagramGraphClient.from_settings() as client:
                response = client.publish_media_container(
                    ig_user_id=ig_user_id,
                    container_id=container_id,
                    access_token=access_token,
                )
        return InstagramMediaPublishResult(
            meta_media_id=response.media_id,
            permalink=response.permalink,
        )

    def _resolve_access_token(
        self,
        *,
        tenant_id: str,
        publishing_identity_id: str,
        meta_page_id: str,
        ig_user_id: str,
    ) -> str:
        if not self.enabled:
            raise InstagramPublishError(
                code=PROVIDER_NOT_CONFIGURED,
                detail_safe="Instagram publisher is not configured.",
                retryable=False,
            )

        page_id = str(meta_page_id or "").strip()
        if not page_id and publishing_identity_id:
            identity = PublishingIdentity.all_objects.filter(
                tenant_id=tenant_id,
                id=publishing_identity_id,
                platform=PublishingIdentity.PLATFORM_INSTAGRAM,
                ig_user_id=ig_user_id,
            ).first()
            page_id = str(identity.meta_page_id or "").strip() if identity else ""
        if not page_id:
            raise _provider_error(retryable=False, operation="token")

        meta_page = (
            MetaPage.all_objects.select_related("connection")
            .filter(tenant_id=tenant_id, page_id=page_id)
            .first()
        )
        if meta_page is None:
            raise _provider_error(retryable=False, operation="token")

        token = (
            meta_page.connection.decrypt_token()
            if meta_page.connection_id and meta_page.connection and meta_page.connection.is_active
            else None
        )
        if not isinstance(token, str) or not token.strip():
            token = meta_page.decrypt_page_token()
        if not isinstance(token, str) or not token.strip():
            raise _provider_error(retryable=False, operation="token")
        return token.strip()


def _container_body(
    *,
    media_url: str,
    caption: str,
    media_type: str,
) -> dict[str, str]:
    body = {"caption": caption}
    normalized_media_type = str(media_type or "").lower()
    if normalized_media_type.startswith("video/"):
        body["video_url"] = media_url
        body["media_type"] = "VIDEO"
    else:
        body["image_url"] = media_url
    return body


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_retryable(status_code: int, payload: dict[str, Any]) -> bool:
    if status_code in _RETRYABLE_HTTP_STATUS:
        return True
    error_payload = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error_payload, dict):
        return False
    if bool(error_payload.get("is_transient")):
        return True
    try:
        code = int(error_payload.get("code"))
    except (TypeError, ValueError):
        return False
    return code in _RETRYABLE_META_ERROR_CODES


def _provider_error(*, retryable: bool, operation: str) -> InstagramPublishError:  # noqa: ARG001
    return InstagramPublishError(
        code=PROVIDER_RETRYABLE_ERROR if retryable else PROVIDER_TERMINAL_ERROR,
        detail_safe=(
            "Instagram publishing failed with a retryable provider error."
            if retryable
            else "Instagram publishing failed with a provider error."
        ),
        retryable=retryable,
    )


__all__ = [
    "InstagramGraphClient",
    "InstagramGraphContainerResponse",
    "InstagramGraphContainerStatusResponse",
    "InstagramGraphMediaPublishResponse",
    "InstagramGraphPublisher",
]
