"""Facebook Page Graph publisher for Content Operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

from integrations.models import MetaPage

from .publisher import (
    FacebookPagePublishError,
    FacebookPagePublishPayload,
    FacebookPagePublishResult,
    PROVIDER_NOT_CONFIGURED,
    PROVIDER_RETRYABLE_ERROR,
    PROVIDER_TERMINAL_ERROR,
)

_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_META_ERROR_CODES = {1, 2, 4, 17, 32, 613, 80001}


@dataclass(frozen=True)
class FacebookGraphPagePostResponse:
    post_id: str
    permalink: str = ""


class FacebookGraphPageClient:
    def __init__(self, *, graph_version: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = f"https://graph.facebook.com/{graph_version}"
        self._client = httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_settings(cls) -> "FacebookGraphPageClient":
        graph_version = (
            getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0"
        ).strip()
        timeout_seconds = float(getattr(settings, "META_GRAPH_TIMEOUT_SECONDS", 10.0) or 10.0)
        return cls(graph_version=graph_version, timeout_seconds=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FacebookGraphPageClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        self.close()

    def publish_page_feed(
        self,
        *,
        page_id: str,
        message: str,
        page_token: str,
    ) -> FacebookGraphPagePostResponse:
        try:
            response = self._client.post(
                f"{self.base_url}/{page_id}/feed",
                data={
                    "message": message,
                    "published": "true",
                    "access_token": page_token,
                },
            )
        except httpx.HTTPError as exc:
            raise _provider_error(retryable=True) from exc

        payload = _safe_json(response)
        if not response.is_success:
            raise _provider_error(retryable=_is_retryable(response.status_code, payload))

        post_id = payload.get("id") if isinstance(payload, dict) else ""
        if not isinstance(post_id, str) or not post_id.strip():
            raise _provider_error(retryable=False)
        return FacebookGraphPagePostResponse(post_id=post_id.strip())

    def publish_page_photo(
        self,
        *,
        page_id: str,
        caption: str,
        media_url: str,
        page_token: str,
    ) -> FacebookGraphPagePostResponse:
        try:
            response = self._client.post(
                f"{self.base_url}/{page_id}/photos",
                data={
                    "url": media_url,
                    "caption": caption,
                    "published": "true",
                    "access_token": page_token,
                },
            )
        except httpx.HTTPError as exc:
            raise _provider_error(retryable=True) from exc

        payload = _safe_json(response)
        if not response.is_success:
            raise _provider_error(retryable=_is_retryable(response.status_code, payload))

        # ``/photos`` returns {"id": <photo_id>, "post_id": <page_post_id>}; the
        # page post id is the durable object we record and report metrics against.
        post_id = ""
        if isinstance(payload, dict):
            post_id = str(payload.get("post_id") or payload.get("id") or "").strip()
        if not post_id:
            raise _provider_error(retryable=False)
        return FacebookGraphPagePostResponse(post_id=post_id)


class FacebookGraphPagePublisher:
    def __init__(self, *, graph_client=None, enabled: bool | None = None) -> None:
        self.graph_client = graph_client
        self.enabled = (
            bool(getattr(settings, "CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING", False))
            if enabled is None
            else enabled
        )

    @classmethod
    def from_settings(cls) -> "FacebookGraphPagePublisher":
        return cls()

    def publish(self, payload: FacebookPagePublishPayload) -> FacebookPagePublishResult:
        if not self.enabled:
            raise FacebookPagePublishError(
                code=PROVIDER_NOT_CONFIGURED,
                detail_safe="Facebook Page publisher is not configured.",
                retryable=False,
            )
        meta_page = MetaPage.all_objects.filter(
            tenant_id=payload.tenant_id,
            page_id=payload.meta_page_id,
        ).first()
        if meta_page is None:
            raise _provider_error(retryable=False)
        page_token = meta_page.decrypt_page_token()
        if not isinstance(page_token, str) or not page_token.strip():
            raise _provider_error(retryable=False)

        if self.graph_client is not None:
            response = self._dispatch(self.graph_client, payload, page_token.strip())
        else:
            with FacebookGraphPageClient.from_settings() as client:
                response = self._dispatch(client, payload, page_token.strip())
        return FacebookPagePublishResult(
            meta_post_id=response.post_id,
            permalink=response.permalink,
        )

    @staticmethod
    def _dispatch(
        client: "FacebookGraphPageClient",
        payload: FacebookPagePublishPayload,
        page_token: str,
    ) -> FacebookGraphPagePostResponse:
        if payload.media_url:
            return client.publish_page_photo(
                page_id=payload.meta_page_id,
                caption=payload.caption,
                media_url=payload.media_url,
                page_token=page_token,
            )
        return client.publish_page_feed(
            page_id=payload.meta_page_id,
            message=payload.caption,
            page_token=page_token,
        )


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


def _provider_error(*, retryable: bool) -> FacebookPagePublishError:
    return FacebookPagePublishError(
        code=PROVIDER_RETRYABLE_ERROR if retryable else PROVIDER_TERMINAL_ERROR,
        detail_safe=(
            "Facebook Page publishing failed with a retryable provider error."
            if retryable
            else "Facebook Page publishing failed with a provider error."
        ),
        retryable=retryable,
    )


__all__ = [
    "FacebookGraphPageClient",
    "FacebookGraphPagePostResponse",
    "FacebookGraphPagePublisher",
]
