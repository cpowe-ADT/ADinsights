from __future__ import annotations

from typing import Any

from django.db import models
from rest_framework import filters
from rest_framework.request import Request

from accounts.tenant_context import get_current_tenant_id


class ScopeFilterBackend(filters.BaseFilterBackend):
    """Filter QuerySets based on tenant and optional workspace scoping.

    This backend ensures that all requests are isolated to the currently active
    tenant. It also supports workspace-level isolation for models that define
    a `workspace_id` field.

    Superusers bypass these filters for administrative or support purposes.
    """

    def filter_queryset(
        self, request: Request, queryset: models.QuerySet[Any], view: Any
    ) -> models.QuerySet[Any]:
        user = request.user
        if not user or not user.is_authenticated:
            return queryset.none()

        # 1. Superusers bypass tenant/workspace filters.
        if getattr(user, "is_superuser", False):
            return queryset

        # 2. Enforce Tenant isolation.
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            # Fallback to the user's default tenant if context isn't set.
            tenant_id = getattr(user, "tenant_id", None)

        if not tenant_id:
            return queryset.none()

        model_fields = [f.name for f in queryset.model._meta.get_fields()]
        
        if "tenant_id" in model_fields:
            queryset = queryset.filter(tenant_id=tenant_id)
        elif "tenant" in model_fields:
            queryset = queryset.filter(tenant_id=tenant_id)

        # 3. Optional Workspace isolation.
        # If the model has workspace_id and the request specifies one, filter by it.
        # This allows users to drill down into a specific brand/region slice.
        if "workspace_id" in model_fields:
            workspace_id = request.query_params.get("workspace_id")
            if workspace_id:
                queryset = queryset.filter(workspace_id=workspace_id)

        return queryset
