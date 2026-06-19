"""Role permissions for Content Operations workflows."""

from __future__ import annotations

from collections.abc import Iterable

from rest_framework import permissions

from accounts.models import Role


CONTENT_OPS_EDIT_ROLES = {
    Role.SUPER_ADMIN,
    Role.SM_ADMIN,
    Role.AGENCY_OWNER,
    Role.AGENCY_ADMIN,
    Role.AGENCY_TEAM_LEAD,
    Role.AGENCY_SENIOR_ANALYST,
    Role.AGENCY_ANALYST,
    Role.CLIENT_TEAM_LEAD,
    Role.CLIENT_SENIOR_LEAD,
    Role.ADMIN,
    Role.ANALYST,
}

CONTENT_OPS_INTERNAL_APPROVER_ROLES = {
    Role.SUPER_ADMIN,
    Role.SM_ADMIN,
    Role.AGENCY_OWNER,
    Role.AGENCY_ADMIN,
    Role.AGENCY_TEAM_LEAD,
    Role.AGENCY_SENIOR_ANALYST,
    Role.ADMIN,
}

CONTENT_OPS_CLIENT_APPROVER_ROLES = {
    Role.SUPER_ADMIN,
    Role.CLIENT_TEAM_LEAD,
    Role.CLIENT_SENIOR_LEAD,
    Role.ADMIN,
}

CONTENT_OPS_PUBLISH_ROLES = {
    Role.SUPER_ADMIN,
    Role.SM_ADMIN,
    Role.AGENCY_TEAM_LEAD,
    Role.CLIENT_TEAM_LEAD,
    Role.ADMIN,
}

CONTENT_OPS_ADMIN_ROLES = {
    Role.SUPER_ADMIN,
    Role.SM_ADMIN,
    Role.AGENCY_OWNER,
    Role.AGENCY_ADMIN,
    Role.CLIENT_TEAM_LEAD,
    Role.ADMIN,
}


class ContentOpsPermission(permissions.BasePermission):
    """Tenant-authenticated read access with role-gated workflow writes."""

    message = "User does not have permission for this Content Operations action."

    def has_permission(self, request, view):  # noqa: D401 - DRF permission API
        user = request.user
        if not user or not user.is_authenticated:
            self.message = "User is not authenticated."
            return False
        if getattr(user, "is_superuser", False):
            return True
        if getattr(user, "tenant_id", None) is None:
            self.message = "User has no active tenant context."
            return False
        if request.method in permissions.SAFE_METHODS:
            return True

        required_roles = getattr(view, "get_content_ops_required_roles", None)
        if callable(required_roles):
            roles = required_roles()
        else:
            roles = CONTENT_OPS_EDIT_ROLES
        if not roles:
            return True
        if _user_has_any_role(user, roles):
            return True
        self.message = "User role cannot perform this Content Operations action."
        return False


def _user_has_any_role(user, roles: Iterable[str]) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    tenant_id = getattr(user, "tenant_id", None)
    if tenant_id is None:
        return False
    return user.user_roles.filter(tenant_id=tenant_id, role__name__in=set(roles)).exists()
