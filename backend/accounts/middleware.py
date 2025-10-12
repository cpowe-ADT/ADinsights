from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.db import connection
from django.utils.deprecation import MiddlewareMixin

from .tenant_context import clear_current_tenant, set_current_tenant_id


class TenantMiddleware(MiddlewareMixin):
    """Middleware that propagates tenant information to the DB connection."""

    def process_request(self, request):
        tenant_id = self._resolve_tenant_id(request)
        set_current_tenant_id(tenant_id)
        self._set_connection_tenant(tenant_id)

    def process_response(self, request, response):
        clear_current_tenant()
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("RESET app.tenant_id")
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

    def _set_connection_tenant(self, tenant_id: Optional[str]) -> None:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                if tenant_id:
                    cursor.execute("SET app.tenant_id = %s", [tenant_id])
                else:
                    cursor.execute("SET app.tenant_id = DEFAULT")
        else:
            setattr(connection, settings.TENANT_SETTING_KEY, tenant_id)
