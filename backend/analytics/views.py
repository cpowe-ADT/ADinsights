"""API views for analytics metrics."""

from __future__ import annotations

import csv
from typing import Any, Iterable, Sequence

from django.db import connection
from django.http import StreamingHttpResponse
from rest_framework import permissions, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .exporters import FakeMetricsExportAdapter
from .serializers import MetricRecordSerializer, MetricsQueryParamsSerializer


class MetricsPagination(PageNumberPagination):
    """Pagination class for metrics responses."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500


class MetricsViewSet(viewsets.ViewSet):
    """Expose aggregated campaign metrics."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MetricsPagination

    def list(self, request) -> Response:
        params_serializer = MetricsQueryParamsSerializer(data=request.query_params)
        params_serializer.is_valid(raise_exception=True)
        filters = params_serializer.validated_data

        tenant_id = getattr(request.user, "tenant_id", None)
        if tenant_id is None:
            return Response({"detail": "Unable to resolve tenant."}, status=403)

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
            "where tenant_id = %(tenant_id)s",
            "  and date_day >= %(start_date)s",
            "  and date_day <= %(end_date)s",
        ]
        query_params: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "start_date": filters["start_date"],
            "end_date": filters["end_date"],
        }

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
