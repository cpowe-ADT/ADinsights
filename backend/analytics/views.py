"""API views for analytics metrics."""

from __future__ import annotations

import csv
import json
import logging
from datetime import timedelta
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.http import StreamingHttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from adapters.base import MetricsAdapter
from adapters.fake import FakeAdapter
from adapters.warehouse import WarehouseAdapter

from .models import TenantMetricsSnapshot
from .serializers import (
    AggregateSnapshotSerializer,
    MetricRecordSerializer,
    MetricsQueryParamsSerializer,
)

from accounts.audit import log_audit_event

logger = logging.getLogger(__name__)


METRIC_EXPORT_HEADERS = [
    "date",
    "platform",
    "campaign",
    "parish",
    "impressions",
    "clicks",
    "spend",
    "conversions",
    "roas",
]
def _build_registry() -> dict[str, MetricsAdapter]:
    """Return the enabled analytics adapters keyed by their slug."""

    registry: dict[str, MetricsAdapter] = {}
    if getattr(settings, "ENABLE_WAREHOUSE_ADAPTER", False):
        warehouse = WarehouseAdapter()
        registry[warehouse.key] = warehouse
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

        if "warehouse" in registry:
            default_key = "warehouse"
        elif "fake" in registry:
            default_key = "fake"
        else:
            default_key = next(iter(registry))
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


class CombinedMetricsView(APIView):
    """Return a unified metrics payload for dashboards."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401 - DRF signature
        registry = _build_registry()
        if not registry:
            return Response(
                {"detail": "No analytics adapters are enabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if "warehouse" in registry:
            default_key = "warehouse"
        elif "fake" in registry:
            default_key = "fake"
        else:
            default_key = next(iter(registry))
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

        ttl_seconds = getattr(settings, "METRICS_SNAPSHOT_TTL", 300)
        cache_enabled = request.query_params.get("cache", "true").lower() != "false"
        tenant = request.user.tenant
        snapshot = (
            TenantMetricsSnapshot.latest_for(tenant=tenant, source=source)
            if cache_enabled
            else None
        )
        if snapshot and snapshot.is_fresh(ttl_seconds):
            return Response(snapshot.payload)

        payload = adapter.fetch_metrics(
            tenant_id=str(tenant_id),
            options=request.query_params,
        )

        combined = {
            "campaign": payload.get("campaign"),
            "creative": payload.get("creative"),
            "budget": payload.get("budget"),
            "parish": payload.get("parish"),
        }
        TenantMetricsSnapshot.all_objects.update_or_create(
            tenant=tenant,
            source=source,
            defaults={
                "payload": combined,
                "generated_at": timezone.now(),
            },
        )
        return Response(combined)


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

        rows = _fetch_metric_rows(tenant_id=str(tenant_id), filters=filters)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)
        serializer = MetricRecordSerializer(page if page is not None else rows, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

class _Echo:
    """Minimal buffer to adapt csv.writer for streaming responses."""

    def write(self, value: str) -> str:  # pragma: no cover - trivial adapter
        return value


class MetricsExportView(APIView):
    """Stream tenant metrics as a CSV attachment."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001
        query_params = request.query_params.copy()
        now = timezone.now().date()
        if "end_date" not in query_params:
            query_params = query_params.copy()
            query_params["end_date"] = now.isoformat()
        if "start_date" not in query_params:
            query_params = query_params.copy()
            query_params["start_date"] = (now - timedelta(days=30)).isoformat()

        serializer = MetricsQueryParamsSerializer(data=query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        tenant_id = getattr(request.user, "tenant_id", None)
        if tenant_id is None:
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        rows = _fetch_metric_rows(tenant_id=str(tenant_id), filters=filters)
        data = MetricRecordSerializer(rows, many=True).data

        response = StreamingHttpResponse(
            self._iter_csv_rows(METRIC_EXPORT_HEADERS, data), content_type="text/csv"
        )
        response["Content-Disposition"] = 'attachment; filename="metrics.csv"'
        return response

    @staticmethod
    def _iter_csv_rows(headers: Sequence[str], rows: Iterable[dict[str, Any]]):
        pseudo_buffer = _Echo()
        writer = csv.writer(pseudo_buffer)
        yield writer.writerow(headers)
        for row in rows:
            yield writer.writerow([row.get(header) for header in headers])


def _coerce_json_payload(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return json.loads(value)
    return value


def _default_campaign_metrics() -> dict[str, Any]:
    return {
        "summary": {
            "currency": None,
            "totalSpend": 0.0,
            "totalImpressions": 0,
            "totalClicks": 0,
            "totalConversions": 0,
            "averageRoas": 0.0,
        },
        "trend": [],
        "rows": [],
    }


def _default_snapshot_payload(*, tenant_id: str) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "generated_at": timezone.now(),
        "metrics": {
            "campaign_metrics": _default_campaign_metrics(),
            "creative_metrics": [],
            "budget_metrics": [],
            "parish_metrics": [],
        },
    }


def _fetch_aggregate_snapshot(*, tenant_id: str) -> Mapping[str, Any] | None:
    sql = """
        select
            tenant_id,
            generated_at,
            campaign_metrics,
            creative_metrics,
            budget_metrics,
            parish_metrics
        from vw_dashboard_aggregate_snapshot
        where tenant_id = %(tenant_id)s
        order by generated_at desc
        limit 1
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {"tenant_id": tenant_id})
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        record = dict(zip(columns, row))

    metrics = {
        "campaign_metrics": _coerce_json_payload(record.get("campaign_metrics"))
        or _default_campaign_metrics(),
        "creative_metrics": _coerce_json_payload(record.get("creative_metrics")) or [],
        "budget_metrics": _coerce_json_payload(record.get("budget_metrics")) or [],
        "parish_metrics": _coerce_json_payload(record.get("parish_metrics")) or [],
    }

    payload: dict[str, Any] = {
        "tenant_id": record.get("tenant_id", tenant_id),
        "generated_at": record.get("generated_at", timezone.now()),
        "metrics": metrics,
    }
    return payload


class AggregateSnapshotView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401 - DRF signature
        tenant_id = getattr(request.user, "tenant_id", None)
        tenant = getattr(request.user, "tenant", None)
        if tenant_id is None or tenant is None:
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant_id_str = str(tenant_id)
        snapshot = _fetch_aggregate_snapshot(tenant_id=tenant_id_str)
        if snapshot is None:
            snapshot = _default_snapshot_payload(tenant_id=tenant_id_str)

        serializer = AggregateSnapshotSerializer(snapshot)

        log_audit_event(
            tenant=tenant,
            user=request.user,
            action="aggregate_snapshot_viewed",
            resource_type="dashboard",
            resource_id=tenant_id_str,
            metadata={
                "path": request.path,
                "tenant_id": tenant_id_str,
            },
        )

        return Response(serializer.data)


def _fetch_metric_rows(*, tenant_id: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
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
        query_params["tenant_id"] = tenant_id
    else:
        logger.debug(
            "vw_campaign_daily missing tenant column; relying on RLS",
            extra={"tenant_id": tenant_id},
        )

    parish = filters.get("parish")
    if parish:
        sql.append("  and parish_name = %(parish)s")
        query_params["parish"] = parish

    sql.append("order by date desc")
    sql_query = "\n".join(sql)

    with connection.cursor() as cursor:
        cursor.execute(sql_query, query_params)
        columns: Sequence[str] = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
