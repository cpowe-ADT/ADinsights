"""Minimal CORS middleware with environment-driven allowlists."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden


class CORSMiddleware:
    """Attach CORS headers for approved origins and handle preflight checks."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        origin = request.headers.get("Origin")
        allowed = self._is_allowed_origin(origin)
        is_preflight = (
            request.method == "OPTIONS"
            and origin is not None
            and "Access-Control-Request-Method" in request.headers
        )

        if is_preflight:
            if not allowed:
                return HttpResponseForbidden("CORS origin blocked.")
            response = HttpResponse(status=204)
            self._set_cors_headers(response, origin)
            requested_headers = request.headers.get("Access-Control-Request-Headers", "")
            if requested_headers:
                requested = [header.strip().lower() for header in requested_headers.split(",") if header.strip()]
                approved = [header for header in requested if header in settings.CORS_ALLOWED_HEADERS]
                response["Access-Control-Allow-Headers"] = ", ".join(approved or settings.CORS_ALLOWED_HEADERS)
            else:
                response["Access-Control-Allow-Headers"] = ", ".join(settings.CORS_ALLOWED_HEADERS)
            return response

        response = self.get_response(request)
        if allowed and origin:
            self._set_cors_headers(response, origin)
        return response

    def _is_allowed_origin(self, origin: str | None) -> bool:
        if origin is None:
            return False
        if settings.CORS_ALLOW_ALL_ORIGINS:
            return True
        return origin in settings.CORS_ALLOWED_ORIGINS

    @staticmethod
    def _append_vary(response: HttpResponse, value: str) -> None:
        existing = response.get("Vary")
        if not existing:
            response["Vary"] = value
            return
        values = [part.strip() for part in existing.split(",") if part.strip()]
        if value not in values:
            values.append(value)
            response["Vary"] = ", ".join(values)

    def _set_cors_headers(self, response: HttpResponse, origin: str) -> None:
        if settings.CORS_ALLOW_ALL_ORIGINS and not settings.CORS_ALLOW_CREDENTIALS:
            response["Access-Control-Allow-Origin"] = "*"
        else:
            response["Access-Control-Allow-Origin"] = origin
        if settings.CORS_ALLOW_CREDENTIALS:
            response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = ", ".join(settings.CORS_ALLOWED_METHODS)
        response["Access-Control-Max-Age"] = str(settings.CORS_PREFLIGHT_MAX_AGE)
        self._append_vary(response, "Origin")
