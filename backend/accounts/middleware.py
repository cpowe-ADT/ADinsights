from __future__ import annotations

from typing import Optional

from django.utils.deprecation import MiddlewareMixin

from .tenant_context import (
    clear_current_tenant,
    reset_connection_tenant,
    set_connection_tenant,
    set_current_tenant_id,
)


class TenantMiddleware(MiddlewareMixin):
    """Middleware that propagates tenant information to the DB connection."""

    def process_request(self, request):
        tenant_id = self._resolve_tenant_id(request)
        set_current_tenant_id(tenant_id)
        set_connection_tenant(tenant_id)

    def process_response(self, request, response):
        clear_current_tenant()
        reset_connection_tenant()
        return response

    def _resolve_tenant_id(self, request) -> Optional[str]:
        if hasattr(request, "user") and getattr(
            request.user, "is_authenticated", False
        ):
            tenant_id = getattr(request.user, "tenant_id", None)
            if tenant_id:
                return str(tenant_id)
        header_tenant = request.META.get("HTTP_X_TENANT_ID")
        return header_tenant
