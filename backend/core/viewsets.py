from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from rest_framework import mixins, permissions, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.audit import log_audit_event
from analytics.models import TenantMetricsSnapshot
from integrations.models import AirbyteJobTelemetry, TenantAirbyteSyncStatus

from .serializers import (
    AirbyteJobTelemetrySerializer,
    TenantAirbyteSyncStatusSerializer,
)


class AirbyteTelemetryPagination(PageNumberPagination):
    """Consistent pagination for Airbyte telemetry listings."""

    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 100


class AirbyteTelemetryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Expose paginated Airbyte telemetry scoped to the requesting tenant."""

    serializer_class = AirbyteJobTelemetrySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = AirbyteTelemetryPagination

    def get_queryset(self) -> QuerySet[AirbyteJobTelemetry]:  # type: ignore[override]
        user = self.request.user
        if not user or not getattr(user, "is_authenticated", False):
            return AirbyteJobTelemetry.objects.none()
        return (
            AirbyteJobTelemetry.objects.filter(tenant_id=user.tenant_id)
            .select_related("connection")
            .order_by("-started_at", "-created_at")
        )

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
        else:
            serializer = self.get_serializer(queryset, many=True)
            response = Response(serializer.data)
            if isinstance(response.data, list):
                raw_results = response.data
                response.data = {
                    "count": len(raw_results),
                    "next": None,
                    "previous": None,
                    "results": raw_results,
                }

        sync_status = self._get_sync_status(request)
        response.data["sync_status"] = (
            TenantAirbyteSyncStatusSerializer(sync_status).data
            if sync_status
            else None
        )
        snapshot_ts = self._latest_snapshot_timestamp(request)
        if snapshot_ts is not None:
            response.data["snapshot_generated_at"] = snapshot_ts

        self._log_fetch(request, response)
        return response

    def _get_sync_status(self, request: Request) -> TenantAirbyteSyncStatus | None:
        user = request.user
        tenant_id = getattr(user, "tenant_id", None)
        if tenant_id is None:
            return None
        return (
            TenantAirbyteSyncStatus.objects.select_related("last_connection")
            .filter(tenant_id=tenant_id)
            .first()
        )

    def _latest_snapshot_timestamp(self, request: Request) -> str | None:
        tenant_id = getattr(request.user, "tenant_id", None)
        if tenant_id is None:
            return None
        snapshot = (
            TenantMetricsSnapshot.objects.filter(tenant_id=tenant_id, source="warehouse")
            .order_by("-generated_at")
            .first()
        )
        if snapshot is None:
            return None
        return snapshot.generated_at.isoformat()

    def _log_fetch(self, request: Request, response: Response) -> None:
        user = request.user
        tenant = getattr(user, "tenant", None)
        if tenant is None:
            return

        paginator = getattr(self, "paginator", None)
        page_number: int | None = None
        page_size: int | None = None
        page_obj = getattr(paginator, "page", None) if paginator else None
        if page_obj is not None:
            page_number = getattr(page_obj, "number", None)
            django_paginator = getattr(page_obj, "paginator", None)
            if django_paginator is not None:
                page_size = getattr(django_paginator, "per_page", None)
        if page_number is None or page_size is None:
            # Fallback to query params if paginator state is unavailable
            page_param = request.query_params.get(
                getattr(self.pagination_class, "page_query_param", "page"),
                "1",
            )
            size_param = request.query_params.get(
                getattr(self.pagination_class, "page_size_query_param", "page_size"),
                None,
            )
            try:
                page_number = int(page_param)
            except (TypeError, ValueError):
                page_number = None
            try:
                page_size = int(size_param) if size_param is not None else page_size
            except (TypeError, ValueError):
                page_size = page_size
        if page_size is None:
            page_size = getattr(self.pagination_class, "page_size", None)

        log_audit_event(
            tenant=tenant,
            user=user if getattr(user, "is_authenticated", False) else None,
            action="airbyte_telemetry_viewed",
            resource_type="airbyte_telemetry",
            resource_id="list",
            metadata={
                "page": page_number,
                "page_size": page_size,
                "result_count": response.data.get("count"),
            },
        )
