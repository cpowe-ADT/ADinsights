"""Saved report layouts API — tenant/owner-scoped CRUD for the report builder.

Mirrors the ``GoogleAdsSavedView`` surface: a thin ``ModelViewSet`` over
:class:`~analytics.models.SavedReportLayout`. Querysets are always filtered to
the requesting user's tenant; within a tenant a user sees their own layouts plus
any flagged ``is_shared``. Admins see every layout in their tenant.

Tenant isolation is enforced twice over: the per-request ``SET app.tenant_id``
RLS guard plus the explicit ``tenant_id`` filter here. ``perform_create`` always
stamps the tenant from the authenticated user, never from request data, so a
client cannot write into another tenant.
"""

from __future__ import annotations

from django.db.models import Q
from rest_framework import permissions, serializers, viewsets

from accounts.models import Role

from .models import SavedReportLayout


def _is_admin(user) -> bool:  # noqa: ANN001 - DRF passes the auth user
    """True when ``user`` is a superuser or holds the ADMIN role in its tenant."""
    if getattr(user, "is_superuser", False):
        return True
    tenant_id = getattr(user, "tenant_id", None)
    if tenant_id is None:
        return False
    return user.user_roles.filter(tenant_id=tenant_id, role__name=Role.ADMIN).exists()


class SavedReportLayoutSerializer(serializers.ModelSerializer):
    """Serialize a saved layout. ``config`` round-trips the grid JSON verbatim."""

    class Meta:
        model = SavedReportLayout
        fields = [
            "id",
            "name",
            "description",
            "config",
            "is_shared",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SavedReportLayoutViewSet(viewsets.ModelViewSet):
    """Tenant/owner-scoped CRUD for report builder layouts."""

    serializer_class = SavedReportLayoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = SavedReportLayout.objects.filter(tenant_id=user.tenant_id)
        if _is_admin(user):
            return queryset.order_by("-updated_at", "name")
        return queryset.filter(
            Q(is_shared=True) | Q(created_by_id=user.id)
        ).order_by("-updated_at", "name")

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(tenant_id=user.tenant_id, created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
