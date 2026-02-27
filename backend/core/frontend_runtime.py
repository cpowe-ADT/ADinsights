"""Helpers for resolving frontend redirect URIs in localhost-aware dev flows."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpRequest

_LOCALHOST_HOSTS = {"localhost", "127.0.0.1"}


def origin_from_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_localhost_origin(origin: str | None) -> bool:
    if not origin:
        return False
    hostname = urlsplit(origin).hostname
    return bool(hostname and hostname.strip().lower() in _LOCALHOST_HOSTS)


def _normalize_localhost_origin(value: str | None) -> str | None:
    origin = origin_from_url(value)
    if not _is_localhost_origin(origin):
        return None
    return origin


def _extract_runtime_context_origin(
    *,
    request: HttpRequest | None = None,
    payload: Mapping[str, Any] | None = None,
) -> str | None:
    candidates: list[Any] = []
    if payload is not None:
        runtime_context = payload.get("runtime_context")
        if isinstance(runtime_context, Mapping):
            candidates.append(runtime_context.get("client_origin"))
        candidates.append(payload.get("client_origin"))
    if request is not None:
        candidates.append(request.GET.get("client_origin"))

    for candidate in candidates:
        if isinstance(candidate, str):
            normalized = _normalize_localhost_origin(candidate.strip())
            if normalized:
                return normalized
    return None


def resolve_frontend_redirect_uri(
    *,
    path: str,
    explicit_redirect_uri: str | None = None,
    request: HttpRequest | None = None,
    payload: Mapping[str, Any] | None = None,
    missing_message: str,
) -> str:
    """Resolve redirect URI with localhost-aware runtime context fallback."""

    request_origin = _normalize_localhost_origin(request.headers.get("Origin")) if request is not None else None
    runtime_origin = _extract_runtime_context_origin(request=request, payload=payload)
    referer_origin = _normalize_localhost_origin(request.headers.get("Referer")) if request is not None else None
    frontend_base_origin = origin_from_url((getattr(settings, "FRONTEND_BASE_URL", "") or "").strip())
    dynamic_origin = request_origin or runtime_origin or referer_origin

    explicit = (explicit_redirect_uri or "").strip()
    if explicit:
        explicit_origin = origin_from_url(explicit)
        if (
            _is_localhost_origin(explicit_origin)
            and dynamic_origin
            and dynamic_origin != explicit_origin
        ):
            explicit_path = urlsplit(explicit).path or f"/{path.lstrip('/')}"
            return f"{dynamic_origin.rstrip('/')}{explicit_path}"
        return explicit

    if dynamic_origin:
        return f"{dynamic_origin.rstrip('/')}/{path.lstrip('/')}"

    if frontend_base_origin:
        return f"{frontend_base_origin.rstrip('/')}/{path.lstrip('/')}"

    raise ValueError(missing_message)

