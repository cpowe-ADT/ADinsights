from __future__ import annotations

from rest_framework import permissions

from .models import Role


class IsTenantAdmin(permissions.BasePermission):
    message = "You must be a tenant admin to perform this action."

    def has_permission(self, request, view):  # noqa: D401 - DRF API
        """Grant access to tenant administrators or superusers."""

        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        if not getattr(user, "tenant_id", None):
            return False
        return user.user_roles.filter(
            tenant_id=user.tenant_id, role__name=Role.ADMIN
        ).exists()
