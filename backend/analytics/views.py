"""API views for analytics metrics."""

from __future__ import annotations

import csv
import logging
from functools import lru_cache
from typing import Any, Iterable, Sequence

from django.conf import settings
from django.db import connection
from django.http import StreamingHttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from adapters.base import MetricsAdapter
from adapters.fake import FakeAdapter

from .exporters import FakeMetricsExportAdapter
from .serializers import MetricRecordSerializer, MetricsQueryParamsSerializer

logger = logging.getLogger(__name__)
def _build_registry() -> dict[str, MetricsAdapter]:
    """Return the enabled analytics adapters keyed by their slug."""

    registry: dict[str, MetricsAdapter] = {}
    if getattr(settings, "ENABLE_FAKE_ADAPTER", False):
        fake = FakeAdapter()
        registry[fake.key] = fake
    return registry


@lru_cache(maxsize=1)
def _campaign_view_has_tenant_column() -> bool:
    """Return True when vw_campaign_daily exposes a tenant_id column."""

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute("PRAGMA table_info('vw_campaign_daily')")
            columns = {row[1] for row in cursor.fetchall()}
            return "tenant_id" in columns

        cursor.execute(
            """
            select 1
            from information_schema.columns
            where table_schema = current_schema()
              and table_name = 'vw_campaign_daily'
              and column_name = 'tenant_id'
            """
        )
        return cursor.fetchone() is not None


class AdapterListView(APIView):
    """Expose the catalog of enabled adapters."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401 - DRF signature
        registry = _build_registry()
        payload = [adapter.metadata() for adapter in registry.values()]
        return Response(payload)


class MetricsView(APIView):
    """Dispatch metrics requests to the configured adapter."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401 - DRF signature
        registry = _build_registry()
        if not registry:
            return Response(
                {"detail": "No analytics adapters are enabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        default_key = "fake" if "fake" in registry else next(iter(registry))
        source = request.query_params.get("source", default_key)
        adapter = registry.get(source)
        if adapter is None:
            return Response(
                {"detail": f"Unknown adapter '{source}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant_id = getattr(request.user, "tenant_id", None)
        if tenant_id is None:
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = adapter.fetch_metrics(
            tenant_id=str(tenant_id),
            options=request.query_params,
        )
        return Response(payload)


class MetricsViewSet(viewsets.ViewSet):
    """Serve tabular campaign metrics sourced from the warehouse."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PageNumberPagination

    def list(self, request) -> Response:  # noqa: D401 - DRF signature
        serializer = MetricsQueryParamsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        tenant_id = getattr(request.user, "tenant_id", None)
        if tenant_id is None:
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        sql = [
            "select",
            "    date_day as date,",
            "    source_platform as platform,",
            "    campaign_name as campaign,",
            "    parish_name as parish,",
            "    impressions,",
            "    clicks,",
            "    spend,",
            "    conversions,",
            "    roas",
            "from vw_campaign_daily",
            "where date_day >= %(start_date)s",
            "  and date_day <= %(end_date)s",
        ]

        query_params: dict[str, Any] = {
            "start_date": filters["start_date"],
            "end_date": filters["end_date"],
        }

        if _campaign_view_has_tenant_column():
            sql.insert(-1, "  and tenant_id = %(tenant_id)s")
            query_params["tenant_id"] = str(tenant_id)
        else:
            logger.debug(
                "vw_campaign_daily missing tenant column; relying on RLS",
                extra={"tenant_id": str(tenant_id)},
            )

        parish = filters.get("parish")
        if parish:
            sql.append("  and parish_name = %(parish)s")
            query_params["parish"] = parish

        sql.append("order by date desc")
        sql_query = "\n".join(sql)

        with connection.cursor() as cursor:
            cursor.execute(sql_query, query_params)
            rows = self._dictfetchall(cursor)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)
        serializer = MetricRecordSerializer(page if page is not None else rows, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @staticmethod
    def _dictfetchall(cursor) -> list[dict[str, Any]]:
        columns: Sequence[str] = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class _Echo:
    """Minimal buffer to adapt csv.writer for streaming responses."""

    def write(self, value: str) -> str:  # pragma: no cover - trivial adapter
        return value


class MetricsExportView(APIView):
    """Stream tenant metrics as a CSV attachment."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001
        adapter = FakeMetricsExportAdapter()
        headers = adapter.get_headers()
        rows = adapter.iter_rows()

        response = StreamingHttpResponse(
            self._iter_csv_rows(headers, rows), content_type="text/csv"
        )
        response["Content-Disposition"] = 'attachment; filename="metrics.csv"'
        return response

    @staticmethod
    def _iter_csv_rows(headers: Sequence[str], rows: Iterable[Sequence[Any]]):
        pseudo_buffer = _Echo()
        writer = csv.writer(pseudo_buffer)
        yield writer.writerow(headers)
        for row in rows:
            yield writer.writerow(row)
