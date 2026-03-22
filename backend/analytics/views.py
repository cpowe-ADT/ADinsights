"""API views for analytics metrics."""

from __future__ import annotations

import csv
import json
import logging
import subprocess
import sys
import time
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from django.conf import settings
from django.db import connection
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from adapters.base import MetricsAdapter
from adapters.demo import DemoAdapter, clear_demo_seed_cache, _demo_seed_dir
from adapters.fake import FakeAdapter
from adapters.upload import UploadAdapter
from adapters.warehouse import WarehouseAdapter, WarehouseSnapshotUnavailable

from accounts.permissions import HasPrivilege
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
    UploadMetricsRequestSerializer,
    UploadMetricsStatusSerializer,
)
from core.metrics import observe_combined_metrics_request
from core.observability import emit_observability_event

from accounts.audit import log_audit_event
from analytics.combined_metrics_service import (
    default_adapter_key,
    load_combined_metrics_payload,
    parse_cache_flag,
)
from analytics.snapshots import (
    default_snapshot_metrics,
    fetch_snapshot_metrics,
    snapshot_metrics_to_serializer_payload,
)
from analytics.uploads import (
    build_combined_payload,
    parse_budget_csv,
    parse_campaign_csv,
    parse_parish_csv,
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

_PARISH_GEOJSON_PATH = Path(settings.BASE_DIR) / "analytics" / "assets" / "jm_parishes.json"


@lru_cache(maxsize=1)
def _load_parish_geojson() -> dict[str, Any] | None:
    try:
        raw = _PARISH_GEOJSON_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(
            "parish.geometry.missing",
            extra={"path": str(_PARISH_GEOJSON_PATH)},
        )
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(
            "parish.geometry.invalid",
            extra={"path": str(_PARISH_GEOJSON_PATH)},
            exc_info=exc,
        )
        return None


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


def _build_registry(*, include_upload: bool = True) -> dict[str, MetricsAdapter]:
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
    if include_upload and getattr(settings, "ENABLE_UPLOAD_ADAPTER", False):
        upload = UploadAdapter()
        registry[upload.key] = upload
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
        registry = _build_registry(include_upload=False)
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

        try:
            payload = adapter.fetch_metrics(
                tenant_id=str(tenant_id),
                options=request.query_params,
            )
        except WarehouseSnapshotUnavailable as exc:
            return Response(
                {"detail": exc.detail},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(payload)


class CombinedMetricsView(APIView):
    """Return a unified metrics payload for dashboards."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401 - DRF signature
        started = time.perf_counter()
        source = request.query_params.get("source", "unknown")
        cache_outcome = "rejected"
        has_filters = False
        snapshot_written = False
        query_count = 0
        status_label = "rejected"

        registry = _build_registry()
        if not registry:
            cache_outcome = "no_registry"
            return Response(
                {"detail": "No analytics adapters are enabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        requested_source = request.query_params.get("source")
        if requested_source:
            source = requested_source
        elif "warehouse" in registry:
            source = default_adapter_key(registry)
        else:
            cache_outcome = "implicit_source_unavailable"
            return Response(
                {
                    "detail": (
                        "Explicit source is required when the warehouse adapter is unavailable."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        adapter = registry.get(source)
        if adapter is None:
            cache_outcome = "unknown_source"
            return Response(
                {"detail": f"Unknown adapter '{source}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant_id = getattr(request.user, "tenant_id", None)
        if tenant_id is None:
            cache_outcome = "missing_tenant"
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            result = load_combined_metrics_payload(
                tenant=request.user.tenant,
                tenant_id=str(tenant_id),
                source=source,
                adapter=adapter,
                query_params=request.query_params,
                ttl_seconds=getattr(settings, "METRICS_SNAPSHOT_TTL", 300),
                cache_enabled=parse_cache_flag(request.query_params.get("cache", "true")),
            )
            cache_outcome = result.cache_outcome
            has_filters = result.has_filters
            snapshot_written = result.snapshot_written
            query_count = result.query_count
            status_label = "success"
            return Response(result.payload)
        except WarehouseSnapshotUnavailable as exc:
            cache_outcome = "warehouse_unavailable"
            status_label = "warehouse_unavailable"
            return Response(
                {"detail": exc.detail},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            cache_outcome = "error"
            status_label = "error"
            raise
        finally:
            duration_seconds = max(time.perf_counter() - started, 0.0)
            metrics_context = {
                "source": source,
                "cache_outcome": cache_outcome,
                "has_filters": has_filters,
                "snapshot_written": snapshot_written,
                "query_count": query_count,
                "duration_ms": round(duration_seconds * 1000, 2),
                "status": status_label,
            }
            request._metrics_context = metrics_context
            raw_request = getattr(request, "_request", None)
            if raw_request is not None:
                raw_request._metrics_context = metrics_context
            observe_combined_metrics_request(
                source=source,
                cache_outcome=cache_outcome,
                status=status_label,
                duration_seconds=duration_seconds,
                query_count=query_count,
                snapshot_written=snapshot_written,
                has_filters=has_filters,
            )
            emit_observability_event(
                logger,
                "metrics.combined.request",
                source=source,
                cache_outcome=cache_outcome,
                status=status_label,
                has_filters=has_filters,
                snapshot_written=snapshot_written,
                query_count=query_count,
                duration_ms=round(duration_seconds * 1000, 2),
            )


class DemoSeedView(APIView):
    """Generate demo seed CSVs and refresh the demo adapter cache."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:  # noqa: D401 - DRF signature
        if not getattr(settings, "ENABLE_DEMO_GENERATION", False):
            return Response(
                {"detail": "Demo generation is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not (
            getattr(request.user, "is_staff", False)
            or getattr(request.user, "is_superuser", False)
        ):
            return Response(
                {"detail": "Demo generation requires staff access."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = request.data if isinstance(request.data, dict) else {}
        days = payload.get("days", 90)
        seed = payload.get("seed", 42)
        end_date_raw = payload.get("end_date")

        try:
            days = int(days)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid days value."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            seed = int(seed)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid seed value."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if days < 1 or days > 365:
            return Response(
                {"detail": "Days must be between 1 and 365."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        end_date = None
        if isinstance(end_date_raw, str):
            end_date = parse_date(end_date_raw)
        if end_date is None:
            end_date = timezone.now().date()

        out_dir = _demo_seed_dir()
        repo_root = Path(settings.BASE_DIR).parent
        script_candidates = [
            repo_root / "scripts" / "generate_demo_data.py",
            Path(settings.BASE_DIR) / "scripts" / "generate_demo_data.py",
        ]
        script_path = next((path for path in script_candidates if path.exists()), None)
        if script_path is None:
            return Response(
                {"detail": "Demo generator script is missing."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        out_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(script_path),
            "--out",
            str(out_dir),
            "--days",
            str(days),
            "--seed",
            str(seed),
            "--end-date",
            end_date.isoformat(),
        ]

        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error(
                "demo.seed.failed",
                extra={"stdout": result.stdout, "stderr": result.stderr},
            )
            return Response(
                {"detail": "Failed to generate demo data."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        clear_demo_seed_cache()
        return Response(
            {
                "detail": "Demo data generated.",
                "seed_dir": str(out_dir),
                "days": days,
                "seed": seed,
                "end_date": end_date.isoformat(),
            }
        )


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


class UploadMetricsView(GenericAPIView):
    """Accept CSV uploads and store a combined metrics snapshot."""

    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "job_run"
    parser_classes = [MultiPartParser]

    def get_serializer_class(self):  # noqa: D401 - DRF signature
        if getattr(self.request, "method", "GET") == "GET":
            return UploadMetricsStatusSerializer
        return UploadMetricsRequestSerializer

    def get(self, request) -> Response:  # noqa: D401 - DRF signature
        tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        snapshot = TenantMetricsSnapshot.latest_for(tenant=tenant, source="upload")
        if snapshot is None:
            return Response({"has_upload": False})

        payload = snapshot.payload
        response_payload = {
            "has_upload": True,
            "snapshot_generated_at": payload.get("snapshot_generated_at"),
            "counts": {
                "campaign_rows": len(payload.get("campaign", {}).get("rows", [])),
                "parish_rows": len(payload.get("parish", [])),
                "budget_rows": len(payload.get("budget", [])),
            },
        }
        serializer = UploadMetricsStatusSerializer(response_payload)
        return Response(serializer.data)

    def post(self, request) -> Response:  # noqa: D401 - DRF signature
        tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        campaign_file = request.FILES.get("campaign_csv")
        if campaign_file is None:
            return Response(
                {"detail": "campaign_csv file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign_result = parse_campaign_csv(campaign_file)
        parish_file = request.FILES.get("parish_csv")
        parish_result = parse_parish_csv(parish_file) if parish_file else None
        budget_file = request.FILES.get("budget_csv")
        budget_result = parse_budget_csv(budget_file) if budget_file else None

        errors = campaign_result.errors[:]
        warnings = campaign_result.warnings[:]
        if parish_result:
            errors.extend(parish_result.errors)
            warnings.extend(parish_result.warnings)
        if budget_result:
            errors.extend(budget_result.errors)
            warnings.extend(budget_result.warnings)

        if errors:
            return Response(
                {"detail": "CSV validation failed.", "errors": errors, "warnings": warnings},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = build_combined_payload(
            campaign_rows=campaign_result.rows,
            parish_rows=parish_result.rows if parish_result else [],
            budget_rows=budget_result.rows if budget_result else [],
            uploaded_at=timezone.now(),
        )

        TenantMetricsSnapshot.objects.update_or_create(
            tenant=tenant,
            source="upload",
            defaults={
                "payload": payload,
                "generated_at": timezone.now(),
            },
        )

        response_payload = {
            "has_upload": True,
            "snapshot_generated_at": payload.get("snapshot_generated_at"),
            "counts": {
                "campaign_rows": len(campaign_result.rows),
                "parish_rows": len(parish_result.rows) if parish_result else 0,
                "budget_rows": len(budget_result.rows) if budget_result else 0,
            },
            "warnings": warnings,
        }
        serializer = UploadMetricsStatusSerializer(response_payload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request) -> Response:  # noqa: D401 - DRF signature
        tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Unable to resolve tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        TenantMetricsSnapshot.objects.filter(tenant=tenant, source="upload").delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class _Echo:
    """Minimal buffer to adapt csv.writer for streaming responses."""

    def write(self, value: str) -> str:  # pragma: no cover - trivial adapter
        return value


class MetricsExportView(APIView):
    """Stream tenant metrics as a CSV attachment."""

    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "csv_export"

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


class ParishGeometryView(APIView):
    """Serve static parish GeoJSON used by the map view."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401 - DRF signature
        payload = _load_parish_geojson()
        if payload is None:
            return Response(
                {"detail": "Parish geometry is unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(payload)


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
