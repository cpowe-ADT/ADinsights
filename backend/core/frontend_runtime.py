"""Helpers for resolving frontend runtime origins and redirect URLs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpRequest

LOCALHOST_ORIGIN_HOSTS = {"localhost", "127.0.0.1"}


def origin_from_url(value: str | None) -> str | None:
    """Return ``scheme://netloc`` when ``value`` is a valid absolute URL."""

    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _hostname_from_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    parsed = urlsplit(origin)
    if not parsed.hostname:
        return None
    return parsed.hostname.strip().lower()


def _request_host_and_port(request: HttpRequest | None) -> tuple[str | None, int | None]:
    if request is None:
        return None, None
    try:
        host = request.get_host().strip()
    except Exception:  # pragma: no cover - defensive host parsing
        return None, None

    if not host:
        return None, None
    parsed = urlsplit(f"//{host}")
    return host, parsed.port


def _is_localhost_origin(origin: str | None) -> bool:
    hostname = _hostname_from_origin(origin)
    return bool(hostname and hostname in LOCALHOST_ORIGIN_HOSTS)


@dataclass(frozen=True)
class FrontendOriginResolution:
    resolved_origin: str | None
    source: str
    request_origin: str | None
    runtime_context_origin: str | None
    request_referer_origin: str | None
    request_host: str | None
    request_port: int | None
    frontend_base_url_origin: str | None


def _normalize_localhost_origin(value: str | None) -> str | None:
    origin = origin_from_url(value)
    if not _is_localhost_origin(origin):
        return None
    return origin


def extract_runtime_client_origin(
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


def resolve_frontend_origin(
    *,
    request: HttpRequest | None = None,
    runtime_context_origin: str | None = None,
) -> FrontendOriginResolution:
    """Resolve the frontend origin from request headers with safe localhost-only dynamics."""

    request_origin = _normalize_localhost_origin(request.headers.get("Origin")) if request is not None else None
    runtime_origin = _normalize_localhost_origin(runtime_context_origin)
    request_referer_origin = (
        _normalize_localhost_origin(request.headers.get("Referer")) if request is not None else None
    )
    frontend_base_url_origin = origin_from_url(
        (getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
    )
    request_host, request_port = _request_host_and_port(request)

    if request_origin:
        return FrontendOriginResolution(
            resolved_origin=request_origin,
            source="request_origin",
            request_origin=request_origin,
            runtime_context_origin=runtime_origin,
            request_referer_origin=request_referer_origin,
            request_host=request_host,
            request_port=request_port,
            frontend_base_url_origin=frontend_base_url_origin,
        )

    if runtime_origin:
        return FrontendOriginResolution(
            resolved_origin=runtime_origin,
            source="runtime_context_origin",
            request_origin=request_origin,
            runtime_context_origin=runtime_origin,
            request_referer_origin=request_referer_origin,
            request_host=request_host,
            request_port=request_port,
            frontend_base_url_origin=frontend_base_url_origin,
        )

    if request_referer_origin:
        return FrontendOriginResolution(
            resolved_origin=request_referer_origin,
            source="request_referer",
            request_origin=request_origin,
            runtime_context_origin=runtime_origin,
            request_referer_origin=request_referer_origin,
            request_host=request_host,
            request_port=request_port,
            frontend_base_url_origin=frontend_base_url_origin,
        )

    if frontend_base_url_origin:
        return FrontendOriginResolution(
            resolved_origin=frontend_base_url_origin,
            source="frontend_base_url",
            request_origin=request_origin,
            runtime_context_origin=runtime_origin,
            request_referer_origin=request_referer_origin,
            request_host=request_host,
            request_port=request_port,
            frontend_base_url_origin=frontend_base_url_origin,
        )

    return FrontendOriginResolution(
        resolved_origin=None,
        source="unresolved",
        request_origin=request_origin,
        runtime_context_origin=runtime_origin,
        request_referer_origin=request_referer_origin,
        request_host=request_host,
        request_port=request_port,
        frontend_base_url_origin=frontend_base_url_origin,
    )


def resolve_frontend_redirect_uri(
    *,
    path: str,
    explicit_redirect_uri: str | None = None,
    request: HttpRequest | None = None,
    runtime_context_origin: str | None = None,
    missing_message: str,
) -> tuple[str, FrontendOriginResolution, str]:
    """Resolve redirect URI with precedence: explicit config -> request localhost -> env."""

    explicit = (explicit_redirect_uri or "").strip()
    resolution = resolve_frontend_origin(
        request=request,
        runtime_context_origin=runtime_context_origin,
    )
    explicit_origin = origin_from_url(explicit)
    if explicit:
        explicit_parsed = urlsplit(explicit)
        if (
            _is_localhost_origin(explicit_origin)
            and resolution.source in {"request_origin", "runtime_context_origin", "request_referer"}
            and resolution.resolved_origin
            and resolution.resolved_origin != explicit_origin
        ):
            explicit_path = explicit_parsed.path or f"/{path.lstrip('/')}"
            return (
                f"{resolution.resolved_origin.rstrip('/')}{explicit_path}",
                resolution,
                "explicit_localhost_redirect_overridden",
            )
        return explicit, resolution, "explicit_redirect_uri"

    if not resolution.resolved_origin:
        raise ValueError(missing_message)

    normalized_path = f"/{path.lstrip('/')}"
    return (
        f"{resolution.resolved_origin.rstrip('/')}{normalized_path}",
        resolution,
        resolution.source,
    )


def extract_dataset_source(
    *,
    request: HttpRequest | None = None,
    payload: Mapping[str, Any] | None = None,
) -> str | None:
    """Extract dataset source markers from query/body payloads for observability."""

    candidates: list[Any] = []
    if payload is not None:
        candidates.append(payload.get("dataset_source"))
        candidates.append(payload.get("source"))
        runtime_context = payload.get("runtime_context")
        if isinstance(runtime_context, Mapping):
            candidates.append(runtime_context.get("dataset_source"))

    if request is not None:
        candidates.append(request.GET.get("dataset_source"))
        candidates.append(request.GET.get("source"))

    for candidate in candidates:
        if isinstance(candidate, str):
            normalized = candidate.strip()
            if normalized:
                return normalized
    return None


def build_runtime_context(
    *,
    redirect_uri: str,
    redirect_source: str,
    resolution: FrontendOriginResolution,
    dataset_source: str | None = None,
) -> dict[str, Any]:
    """Build a structured runtime context payload for setup diagnostics."""

    return {
        "redirect_uri": redirect_uri,
        "redirect_source": redirect_source,
        "request_origin": resolution.request_origin,
        "runtime_context_origin": resolution.runtime_context_origin,
        "request_referer_origin": resolution.request_referer_origin,
        "request_host": resolution.request_host,
        "request_port": resolution.request_port,
        "resolved_frontend_origin": resolution.resolved_origin,
        "frontend_base_url_origin": resolution.frontend_base_url_origin,
        "dev_active_profile": os.environ.get("DEV_ACTIVE_PROFILE"),
        "dev_backend_url": os.environ.get("DEV_BACKEND_URL"),
        "dev_frontend_url": os.environ.get("DEV_FRONTEND_URL"),
        "dataset_source": dataset_source,
    }
