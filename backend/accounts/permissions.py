from __future__ import annotations

from rest_framework import permissions

from .models import Role, Tenant


class IsTenantUser(permissions.BasePermission):
    """Require authentication to a specific tenant unless superuser."""

    message = "Authentication with a tenant-scoped account is required."

    def has_permission(self, request, view):  # noqa: D401 - DRF API
        """Allow authenticated users that belong to a tenant."""

        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        tenant_id = getattr(user, "tenant_id", None)
        return tenant_id is not None

    def has_object_permission(self, request, view, obj):  # noqa: D401 - DRF API
        """Restrict object access to the user's tenant."""

        user = request.user
        if getattr(user, "is_superuser", False):
            return True

        tenant_id = getattr(user, "tenant_id", None)
        if tenant_id is None:
            return False

        obj_tenant_id = getattr(obj, "tenant_id", None)
        if obj_tenant_id is None:
            tenant = getattr(obj, "tenant", None)
            if tenant is not None:
                obj_tenant_id = getattr(tenant, "id", None)

        if obj_tenant_id is None and isinstance(obj, Tenant):
            obj_tenant_id = getattr(obj, "id", None)

        if obj_tenant_id is None and hasattr(obj, "user"):
            related_user = getattr(obj, "user")
            if related_user is not None:
                obj_tenant_id = getattr(related_user, "tenant_id", None)

        if obj_tenant_id is None:
            return False

        return str(obj_tenant_id) == str(tenant_id)


class IsTenantAdmin(permissions.BasePermission):
    message = "You must be a tenant admin to perform this action."

    def has_permission(self, request, view):  # noqa: D401 - DRF API
        """Grant access to tenant administrators or superusers."""

        user = request.user
        if not IsTenantUser().has_permission(request, view):
            return False
        if getattr(user, "is_superuser", False):
            return True
        return user.user_roles.filter(
            tenant_id=user.tenant_id, role__name=Role.ADMIN
        ).exists()
