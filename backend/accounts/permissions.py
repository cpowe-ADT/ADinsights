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
            self.message = "User is not authenticated."
            return False
        if getattr(user, "is_superuser", False):
            return True
        tenant_id = getattr(user, "tenant_id", None)
        if tenant_id is None:
            self.message = "User is authenticated but has no active tenant context."
            return False
        return True

    def has_object_permission(self, request, view, obj):  # noqa: D401 - DRF API
        """Restrict object access to the user's tenant."""

        user = request.user
        if getattr(user, "is_superuser", False):
            return True

        tenant_id = getattr(user, "tenant_id", None)
        if tenant_id is None:
            self.message = "User has no active tenant context."
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
            self.message = "Object has no identifiable tenant context."
            return False

        if str(obj_tenant_id) != str(tenant_id):
            self.message = f"Tenant mismatch: User({tenant_id}) cannot access Object({obj_tenant_id})."
            return False

        return True


class IsTenantAdmin(permissions.BasePermission):
    message = "You must be a tenant admin to perform this action."

    def has_permission(self, request, view):  # noqa: D401 - DRF API
        """Grant access to tenant administrators or superusers."""

        user = request.user
        if not IsTenantUser().has_permission(request, view):
            return False
        if getattr(user, "is_superuser", False):
            return True

        admin_roles = {
            Role.ADMIN,
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.AGENCY_OWNER,
            Role.AGENCY_ADMIN,
            Role.CLIENT_TEAM_LEAD,
        }
        has_role = user.user_roles.filter(
            tenant_id=user.tenant_id, role__name__in=admin_roles
        ).exists()
        
        if not has_role:
             self.message = "User does not hold an administrator role for this tenant."
             return False
        return True


class IsAnalyst(permissions.BasePermission):
    """Grant access to analysts, admins, or superusers."""

    message = "You must have at least analyst-level privileges."

    def has_permission(self, request, view):
        user = request.user
        if not IsTenantUser().has_permission(request, view):
            return False
        if getattr(user, "is_superuser", False):
            return True

        analyst_roles = {
            Role.ANALYST,
            Role.AGENCY_TEAM_LEAD,
            Role.AGENCY_SENIOR_ANALYST,
            Role.AGENCY_ANALYST,
            Role.CLIENT_SENIOR_LEAD,
            Role.CLIENT_JUNIOR,
            # Admins also count as analysts
            Role.ADMIN,
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.AGENCY_OWNER,
            Role.AGENCY_ADMIN,
            Role.CLIENT_TEAM_LEAD,
        }
        has_role = user.user_roles.filter(
            tenant_id=user.tenant_id, role__name__in=analyst_roles
        ).exists()

        if not has_role:
            self.message = "User does not hold an analyst role for this tenant."
            return False
        return True


class IsViewer(permissions.BasePermission):
    """Grant access to anyone with a valid tenant role (Read-only by convention)."""

    def has_permission(self, request, view):
        return IsTenantUser().has_permission(request, view)


class HasPrivilege(permissions.BasePermission):
    """Fine-grained capability enforcement based on role catalog.

    This permission class expects the view to define `required_privilege`
    mapping to one of the action verbs in the UAC spec.
    """

    # Role capability mappings based on docs/security/uac-spec.md section 4.
    # Each list represents roles that HAVE the permission.
    CAPABILITIES = {
        "create_tenant": {Role.SUPER_ADMIN, Role.SM_ADMIN, Role.AGENCY_ADMIN, Role.ADMIN},
        "tenant_settings": {
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.CLIENT_TEAM_LEAD,
            Role.ADMIN,
        },
        "workspace_manage": {
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.AGENCY_ADMIN,
            Role.CLIENT_TEAM_LEAD,
            Role.ADMIN,
        },
        "dashboard_edit": {
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.AGENCY_ADMIN,
            Role.AGENCY_SENIOR_ANALYST,
            Role.CLIENT_TEAM_LEAD,
            Role.CLIENT_SENIOR_LEAD,
            Role.ADMIN,
            Role.ANALYST,
        },
        "publish": {
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.AGENCY_TEAM_LEAD,
            Role.CLIENT_TEAM_LEAD,
            Role.ADMIN,
        },
        "budget_edit": {
            Role.SUPER_ADMIN,
            Role.CLIENT_TEAM_LEAD,
            Role.ADMIN,
        },
        "connector_rotation": {
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.AGENCY_ADMIN,
            Role.CLIENT_TEAM_LEAD,
            Role.ADMIN,
        },
        "job_run": {
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.AGENCY_ADMIN,
            Role.AGENCY_SENIOR_ANALYST,
            Role.CLIENT_TEAM_LEAD,
            Role.CLIENT_SENIOR_LEAD,
            Role.ADMIN,
            Role.ANALYST,
        },
        "csv_export": {
            Role.SUPER_ADMIN,
            Role.ADMIN,
            # Others depend on entitlement flags, handled in view logic
        },
        "audit_export": {
            Role.SUPER_ADMIN,
            Role.SM_ADMIN,
            Role.CLIENT_TEAM_LEAD,
            Role.ADMIN,
        },
    }

    def has_permission(self, request, view):
        user = request.user
        if not IsTenantUser().has_permission(request, view):
            return False
        if getattr(user, "is_superuser", False):
            return True

        privilege = getattr(view, "required_privilege", None)
        if not privilege:
            # If no privilege is specified, we default to allowing if they are a tenant user.
            # Specific view logic or other permissions should handle it.
            return True

        allowed_roles = self.CAPABILITIES.get(privilege, set())
        has_role = user.user_roles.filter(
            tenant_id=user.tenant_id, role__name__in=allowed_roles
        ).exists()

        if not has_role:
            self.message = f"User is missing the required privilege: '{privilege}'."
            return False
        return True
