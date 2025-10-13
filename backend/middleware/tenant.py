"""Middleware for propagating the tenant ID from headers to the request object."""

from __future__ import annotations

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class TenantHeaderMiddleware(MiddlewareMixin):
    """Populate ``request.tenant_id`` from the ``X-Tenant-Id`` header when enabled."""

    header_name = "HTTP_X_TENANT_ID"

    def process_request(self, request):  # noqa: D401 - Django middleware API
        """Attach the tenant identifier to the request when feature-flagged."""

        if not getattr(settings, "ENABLE_TENANCY", False):
            return None

        tenant_id = request.META.get(self.header_name)
        # Always set the attribute so downstream code can rely on its presence.
        setattr(request, "tenant_id", tenant_id)
        return None
