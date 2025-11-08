"""API views for analytics metrics."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.http import StreamingHttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from adapters.base import MetricsAdapter
from adapters.demo import DemoAdapter
from adapters.fake import FakeAdapter
from adapters.warehouse import WarehouseAdapter

from .models import (
    Ad,
    AdSet,
    Campaign,
    RawPerformanceRecord,
    TenantMetricsSnapshot,
)
from .serializers import (
    AdSerializer,
    AdSetSerializer,
    AggregateSnapshotSerializer,
    CampaignSerializer,
    MetricRecordSerializer,
    MetricsQueryParamsSerializer,
    RawPerformanceRecordSerializer,
)

from accounts.audit import log_audit_event
from analytics.snapshots import (
    default_snapshot_metrics,
    fetch_snapshot_metrics,
    snapshot_metrics_to_serializer_payload,
)

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


class TenantScopedModelViewSet(viewsets.ModelViewSet):
    """Base viewset enforcing tenant scoped CRUD operations."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        tenant = getattr(self.request.user, "tenant", None)
        if tenant is None:
            return queryset.none()
        return queryset.filter(tenant=tenant)

    def perform_create(self, serializer):  # noqa: D401 - DRF signature
        tenant = getattr(self.request.user, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Unable to resolve tenant.")
        serializer.save(tenant=tenant)

    def perform_update(self, serializer):  # noqa: D401 - DRF signature
        tenant = getattr(self.request.user, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Unable to resolve tenant.")
        serializer.save(tenant=tenant)


class CampaignViewSet(TenantScopedModelViewSet):
    queryset = Campaign.objects.all().order_by("name", "external_id")
    serializer_class = CampaignSerializer


class AdSetViewSet(TenantScopedModelViewSet):
    queryset = (
        AdSet.objects.all()
        .select_related("campaign")
        .order_by("name", "external_id")
    )
    serializer_class = AdSetSerializer


class AdViewSet(TenantScopedModelViewSet):
    queryset = (
        Ad.objects.all()
        .select_related("adset", "adset__campaign")
        .order_by("name", "external_id")
    )
    serializer_class = AdSerializer


class RawPerformanceRecordViewSet(TenantScopedModelViewSet):
    queryset = (
        RawPerformanceRecord.objects.all()
        .select_related("campaign", "adset", "ad")
        .order_by("-date", "-ingested_at")
    )
    serializer_class = RawPerformanceRecordSerializer


def _build_registry() -> dict[str, MetricsAdapter]:
    """Return the enabled analytics adapters keyed by their slug."""

    registry: dict[str, MetricsAdapter] = {}
    if getattr(settings, "ENABLE_WAREHOUSE_ADAPTER", False):
        warehouse = WarehouseAdapter()
        registry[warehouse.key] = warehouse
    if getattr(settings, "ENABLE_DEMO_ADAPTER", False):
        demo = DemoAdapter()
        registry[demo.key] = demo
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
            cached_payload = dict(snapshot.payload)
            cached_payload["snapshot_generated_at"] = snapshot.generated_at.isoformat()
            return Response(cached_payload)

        payload = adapter.fetch_metrics(
            tenant_id=str(tenant_id),
            options=request.query_params,
        )
        combined, generated_at = _normalize_combined_payload(payload)
        TenantMetricsSnapshot.objects.update_or_create(
            tenant=tenant,
            source=source,
            defaults={
                "payload": combined,
                "generated_at": generated_at,
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


def _default_snapshot_payload(*, tenant_id: str) -> dict[str, Any]:
    metrics = default_snapshot_metrics(tenant_id=tenant_id)
    return snapshot_metrics_to_serializer_payload(metrics)


def _fetch_aggregate_snapshot(*, tenant_id: str) -> Mapping[str, Any] | None:
    metrics = fetch_snapshot_metrics(tenant_id=tenant_id)
    if metrics is None:
        return None
    return snapshot_metrics_to_serializer_payload(metrics)


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


def _resolve_snapshot_timestamp(candidate: Any) -> datetime:
    if isinstance(candidate, datetime):
        resolved = candidate
    elif isinstance(candidate, str):
        parsed = parse_datetime(candidate)
        resolved = parsed if parsed is not None else None
    else:
        resolved = None
    if resolved is None:
        resolved = timezone.now()
    if timezone.is_naive(resolved):  # pragma: no cover - depends on db backend
        resolved = timezone.make_aware(resolved)
    return resolved


def _normalize_combined_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], datetime]:
    normalized: dict[str, Any] = dict(payload)
    metrics = normalized.get("metrics")
    if isinstance(metrics, Mapping):
        normalized.setdefault("campaign", metrics.get("campaign_metrics"))
        normalized.setdefault("creative", metrics.get("creative_metrics") or [])
        normalized.setdefault("budget", metrics.get("budget_metrics") or [])
        normalized.setdefault("parish", metrics.get("parish_metrics") or [])

    generated_at = _resolve_snapshot_timestamp(
        normalized.get("snapshot_generated_at") or normalized.get("generated_at")
    )
    normalized["snapshot_generated_at"] = generated_at.isoformat()
    normalized.pop("generated_at", None)
    return normalized, generated_at
