from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.http import HttpResponseBase
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from accounts.audit import log_audit_event
from accounts.permissions import HasPrivilege
from analytics.models import (
    AISummary,
    DashboardDefinition,
    ReportDefinition,
    ReportExportJob,
    TenantMetricsSnapshot,
)
from integrations.models import AirbyteConnection
from integrations.views import AlertRuleDefinitionViewSet

from .phase2_serializers import (
    AISummarySerializer,
    DashboardDefinitionSerializer,
    ReportDefinitionSerializer,
    ReportExportCreateSerializer,
    ReportExportJobSerializer,
)

logger = logging.getLogger(__name__)

SYNC_HEALTH_STALE_THRESHOLD = timedelta(hours=2)

DASHBOARD_TEMPLATE_LIBRARY = (
    {
        "id": DashboardDefinition.TEMPLATE_META_EXECUTIVE_OVERVIEW,
        "template_key": DashboardDefinition.TEMPLATE_META_EXECUTIVE_OVERVIEW,
        "name": "Meta executive overview",
        "type": "Executive overview",
        "tags": ["Meta Ads", "Executive", "KPI summary"],
        "description": "High-level Meta Ads performance with trend, pacing, and coverage context.",
        "route": f"/dashboards/create?template={DashboardDefinition.TEMPLATE_META_EXECUTIVE_OVERVIEW}",
    },
    {
        "id": DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
        "template_key": DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
        "name": "Meta campaign performance",
        "type": "Campaigns",
        "tags": ["Meta Ads", "Campaigns", "ROAS"],
        "description": "Campaign KPI strip, trend, table, and map state for Meta Ads.",
        "route": f"/dashboards/create?template={DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE}",
    },
    {
        "id": DashboardDefinition.TEMPLATE_META_CREATIVE_INSIGHTS,
        "template_key": DashboardDefinition.TEMPLATE_META_CREATIVE_INSIGHTS,
        "name": "Meta creative insights",
        "type": "Creatives",
        "tags": ["Meta Ads", "Creatives", "CTR"],
        "description": "Creative leaderboard and thumbnail-based performance review.",
        "route": f"/dashboards/create?template={DashboardDefinition.TEMPLATE_META_CREATIVE_INSIGHTS}",
    },
    {
        "id": DashboardDefinition.TEMPLATE_META_BUDGET_PACING,
        "template_key": DashboardDefinition.TEMPLATE_META_BUDGET_PACING,
        "name": "Meta budget pacing",
        "type": "Budget pacing",
        "tags": ["Meta Ads", "Budget", "Pacing"],
        "description": "Budget pacing view with projected spend and pacing risk indicators.",
        "route": f"/dashboards/create?template={DashboardDefinition.TEMPLATE_META_BUDGET_PACING}",
    },
    {
        "id": DashboardDefinition.TEMPLATE_META_PARISH_MAP,
        "template_key": DashboardDefinition.TEMPLATE_META_PARISH_MAP,
        "name": "Meta parish map",
        "type": "Parish map",
        "tags": ["Meta Ads", "Geo", "Map"],
        "description": "Geographic Meta Ads view that gracefully degrades when parish coverage is unavailable.",
        "route": f"/dashboards/create?template={DashboardDefinition.TEMPLATE_META_PARISH_MAP}",
    },
    {
        "id": DashboardDefinition.TEMPLATE_META_PAGE_INSIGHTS,
        "template_key": DashboardDefinition.TEMPLATE_META_PAGE_INSIGHTS,
        "name": "Meta page insights",
        "type": "Page insights",
        "tags": ["Meta", "Pages", "Insights"],
        "description": "Saved view for Facebook Page overview filters and trend configuration.",
        "route": "/dashboards/meta/pages",
    },
)

DEFAULT_DASHBOARD_PRESETS = (
    {
        "name": "Executive overview (30 days)",
        "description": "System-created executive summary dashboard for the last 30 days.",
        "template_key": DashboardDefinition.TEMPLATE_META_EXECUTIVE_OVERVIEW,
        "default_metric": DashboardDefinition.METRIC_SPEND,
        "filters": {
            "dateRange": "30d",
            "accountId": "",
            "channels": [],
            "campaignQuery": "",
            "customRange": {"start": "", "end": ""},
        },
        "layout": {
            "routeKind": "campaigns",
            "widgets": ["kpis", "trend", "campaign_table", "budget_summary", "map"],
        },
    },
    {
        "name": "Campaign review (7 days)",
        "description": "System-created campaign review dashboard for the last 7 days.",
        "template_key": DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
        "default_metric": DashboardDefinition.METRIC_SPEND,
        "filters": {
            "dateRange": "7d",
            "accountId": "",
            "channels": [],
            "campaignQuery": "",
            "customRange": {"start": "", "end": ""},
        },
        "layout": {
            "routeKind": "campaigns",
            "widgets": ["kpis", "trend", "campaign_table", "map"],
        },
    },
    {
        "name": "Budget pacing (MTD)",
        "description": "System-created budget pacing dashboard for month-to-date monitoring.",
        "template_key": DashboardDefinition.TEMPLATE_META_BUDGET_PACING,
        "default_metric": DashboardDefinition.METRIC_CPA,
        "filters": {
            "dateRange": "mtd",
            "accountId": "",
            "channels": [],
            "campaignQuery": "",
            "customRange": {"start": "", "end": ""},
        },
        "layout": {
            "routeKind": "budget",
            "widgets": ["budget_summary", "budget_table", "coverage"],
        },
    },
)


def ensure_default_dashboard_presets(*, tenant) -> None:
    with transaction.atomic():
        active_dashboards = DashboardDefinition.objects.select_for_update().filter(
            tenant=tenant,
            is_active=True,
        )
        if active_dashboards.exists():
            return

        for preset in DEFAULT_DASHBOARD_PRESETS:
            DashboardDefinition.objects.get_or_create(
                tenant=tenant,
                name=preset["name"],
                template_key=preset["template_key"],
                defaults={
                    "description": preset["description"],
                    "filters": preset["filters"],
                    "layout": preset["layout"],
                    "default_metric": preset["default_metric"],
                    "is_active": True,
                    "created_by": None,
                    "updated_by": None,
                },
            )


class ReportDefinitionSchema(AutoSchema):
    """Ensure unique operationIds for mixed-method custom actions."""

    def get_operation_id(self, path, method):  # noqa: D401
        operation_id = super().get_operation_id(path, method)
        if getattr(self.view, "action", None) == "exports":
            return f"{operation_id}{method.title()}"
        return operation_id


class ReportDefinitionViewSet(viewsets.ModelViewSet):
    serializer_class = ReportDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "dashboard_edit"
    schema = ReportDefinitionSchema()

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return ReportDefinition.objects.none()
        return ReportDefinition.objects.filter(tenant_id=user.tenant_id).order_by("-updated_at")

    def perform_create(self, serializer):
        actor = self.request.user if self.request.user.is_authenticated else None
        report = serializer.save(
            tenant=self.request.user.tenant,
            created_by=actor,
            updated_by=actor,
        )
        log_audit_event(
            tenant=report.tenant,
            user=actor,
            action="report_created",
            resource_type="report_definition",
            resource_id=report.id,
            metadata={"fields": sorted(serializer.validated_data.keys()), "redacted": True},
        )

    def perform_update(self, serializer):
        actor = self.request.user if self.request.user.is_authenticated else None
        report = serializer.save(updated_by=actor)
        log_audit_event(
            tenant=report.tenant,
            user=actor,
            action="report_updated",
            resource_type="report_definition",
            resource_id=report.id,
            metadata={"fields": sorted(serializer.validated_data.keys()), "redacted": True},
        )

    def perform_destroy(self, instance):
        actor = self.request.user if self.request.user.is_authenticated else None
        tenant = instance.tenant
        report_id = instance.id
        super().perform_destroy(instance)
        log_audit_event(
            tenant=tenant,
            user=actor,
            action="report_deleted",
            resource_type="report_definition",
            resource_id=report_id,
            metadata={"fields": [], "redacted": True},
        )

    @action(detail=True, methods=["get"], url_path="exports")
    def exports(self, request, pk=None):
        report = self.get_object()

        jobs = report.export_jobs.filter(tenant_id=report.tenant_id).order_by("-created_at")
        return Response(ReportExportJobSerializer(jobs, many=True).data)

    @exports.mapping.post
    def create_export(self, request, pk=None):
        report = self.get_object()
        actor = request.user if request.user.is_authenticated else None

        payload = ReportExportCreateSerializer(data=request.data or {})
        payload.is_valid(raise_exception=True)
        export_job = ReportExportJob.objects.create(
            tenant=report.tenant,
            report=report,
            requested_by=actor,
            export_format=payload.validated_data["export_format"],
            status=ReportExportJob.STATUS_QUEUED,
        )

        log_audit_event(
            tenant=report.tenant,
            user=actor,
            action="report_export_requested",
            resource_type="report_export_job",
            resource_id=export_job.id,
            metadata={
                "redacted": True,
                "fields": ["export_format"],
                "report_id": str(report.id),
            },
        )

        try:
            from analytics.tasks import run_report_export_job

            run_report_export_job.delay(str(export_job.id))
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Failed to enqueue report export", exc_info=exc)
            export_job.status = ReportExportJob.STATUS_FAILED
            export_job.error_message = str(exc)
            export_job.completed_at = timezone.now()
            export_job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])

        return Response(ReportExportJobSerializer(export_job).data, status=status.HTTP_201_CREATED)


class DashboardDefinitionSchema(AutoSchema):
    """Ensure unique operationIds for duplicate dashboard actions."""

    def get_operation_id(self, path, method):  # noqa: D401
        operation_id = super().get_operation_id(path, method)
        if getattr(self.view, "action", None) == "duplicate":
            return f"{operation_id}{method.title()}"
        return operation_id


class DashboardDefinitionViewSet(viewsets.ModelViewSet):
    serializer_class = DashboardDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "dashboard_edit"
    schema = DashboardDefinitionSchema()

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return DashboardDefinition.objects.none()
        return DashboardDefinition.objects.filter(tenant_id=user.tenant_id).order_by(
            "-updated_at", "name"
        )

    def perform_create(self, serializer):
        actor = self.request.user if self.request.user.is_authenticated else None
        dashboard = serializer.save(
            tenant=self.request.user.tenant,
            created_by=actor,
            updated_by=actor,
        )
        log_audit_event(
            tenant=dashboard.tenant,
            user=actor,
            action="dashboard_definition_created",
            resource_type="dashboard_definition",
            resource_id=dashboard.id,
            metadata={"fields": sorted(serializer.validated_data.keys()), "redacted": True},
        )

    def perform_update(self, serializer):
        actor = self.request.user if self.request.user.is_authenticated else None
        dashboard = serializer.save(updated_by=actor)
        log_audit_event(
            tenant=dashboard.tenant,
            user=actor,
            action="dashboard_definition_updated",
            resource_type="dashboard_definition",
            resource_id=dashboard.id,
            metadata={"fields": sorted(serializer.validated_data.keys()), "redacted": True},
        )

    def perform_destroy(self, instance):
        actor = self.request.user if self.request.user.is_authenticated else None
        tenant = instance.tenant
        dashboard_id = instance.id
        super().perform_destroy(instance)
        log_audit_event(
            tenant=tenant,
            user=actor,
            action="dashboard_definition_deleted",
            resource_type="dashboard_definition",
            resource_id=dashboard_id,
            metadata={"fields": [], "redacted": True},
        )

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        dashboard = self.get_object()
        actor = request.user if request.user.is_authenticated else None
        clone = DashboardDefinition.objects.create(
            tenant=dashboard.tenant,
            name=f"{dashboard.name} Copy",
            description=dashboard.description,
            template_key=dashboard.template_key,
            filters=dashboard.filters,
            layout=dashboard.layout,
            default_metric=dashboard.default_metric,
            is_active=dashboard.is_active,
            created_by=actor,
            updated_by=actor,
        )
        log_audit_event(
            tenant=clone.tenant,
            user=actor,
            action="dashboard_definition_duplicated",
            resource_type="dashboard_definition",
            resource_id=clone.id,
            metadata={"redacted": True, "source_id": str(dashboard.id)},
        )
        return Response(
            DashboardDefinitionSerializer(clone, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class AlertsViewSet(AlertRuleDefinitionViewSet):
    """Expose tenant alert rule management at /api/alerts/."""

    schema = AutoSchema(operation_id_base="TenantAlertRuleDefinition")


class AISummaryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AISummarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return AISummary.objects.none()
        queryset = AISummary.objects.filter(tenant_id=user.tenant_id).order_by("-generated_at")
        source = self.request.query_params.get("source")
        if source:
            queryset = queryset.filter(source=source)
        return queryset

    @action(detail=False, methods=["post"], url_path="refresh")
    def refresh(self, request):
        actor = request.user if request.user.is_authenticated else None
        tenant = request.user.tenant
        try:
            from analytics.tasks import generate_ai_summary_for_tenant

            result = generate_ai_summary_for_tenant(tenant_id=str(tenant.id), task_id="manual-refresh")
            summary_id = result.get("summary_id")
            refreshed = None
            if summary_id:
                refreshed = AISummary.objects.filter(id=summary_id, tenant_id=tenant.id).first()
        except Exception as exc:
            logger.exception("Failed to refresh AI summary", exc_info=exc)
            return Response({"detail": f"Failed to refresh summary: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        log_audit_event(
            tenant=tenant,
            user=actor,
            action="summary_refreshed",
            resource_type="ai_summary",
            resource_id=refreshed.id if refreshed else "manual",
            metadata={"redacted": True, "fields": ["source"]},
        )

        if refreshed is None:
            return Response({"detail": "Summary refresh completed with no record."})
        return Response(AISummarySerializer(refreshed).data, status=status.HTTP_201_CREATED)


class SyncHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        tenant_id = request.user.tenant_id
        now = timezone.now()
        rows: list[dict[str, Any]] = []

        connections = AirbyteConnection.objects.filter(tenant_id=tenant_id).order_by("name")
        for connection in connections:
            state = "fresh"
            if not connection.is_active:
                state = "inactive"
            elif connection.last_synced_at is None:
                state = "missing"
            else:
                age = now - connection.last_synced_at
                if age > SYNC_HEALTH_STALE_THRESHOLD:
                    state = "stale"
            job_status = (connection.last_job_status or "").lower()
            if job_status in {"failed", "error", "errored", "cancelled", "canceled"}:
                state = "failed"

            rows.append(
                {
                    "id": str(connection.id),
                    "name": connection.name,
                    "provider": connection.provider,
                    "schedule_type": connection.schedule_type,
                    "is_active": connection.is_active,
                    "state": state,
                    "last_synced_at": connection.last_synced_at.isoformat() if connection.last_synced_at else None,
                    "last_job_status": connection.last_job_status,
                    "last_job_error": connection.last_job_error or None,
                }
            )

        counts = {
            "total": len(rows),
            "fresh": sum(1 for row in rows if row["state"] == "fresh"),
            "stale": sum(1 for row in rows if row["state"] == "stale"),
            "failed": sum(1 for row in rows if row["state"] == "failed"),
            "missing": sum(1 for row in rows if row["state"] == "missing"),
            "inactive": sum(1 for row in rows if row["state"] == "inactive"),
        }

        return Response(
            {
                "generated_at": now.isoformat(),
                "stale_after_minutes": int(SYNC_HEALTH_STALE_THRESHOLD.total_seconds() / 60),
                "counts": counts,
                "rows": rows,
            }
        )


class HealthOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        from core import views as core_views

        checks = [
            ("api", core_views.health),
            ("airbyte", core_views.airbyte_health),
            ("dbt", core_views.dbt_health),
            ("timezone", core_views.timezone_view),
        ]

        cards: list[dict[str, Any]] = []
        for key, view_fn in checks:
            raw = view_fn(request)
            payload = self._payload_from_response(raw)
            status_code = getattr(raw, "status_code", 500)
            cards.append(
                {
                    "key": key,
                    "http_status": status_code,
                    "status": payload.get("status", "ok" if status_code < 400 else "error"),
                    "detail": payload.get("detail"),
                    "payload": payload,
                }
            )

        overall = "ok"
        if any(card["http_status"] >= 500 for card in cards):
            overall = "error"
        elif any(card["http_status"] >= 400 for card in cards):
            overall = "degraded"

        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "overall_status": overall,
                "cards": cards,
            }
        )

    def _payload_from_response(self, response: HttpResponseBase) -> dict[str, Any]:
        try:
            if hasattr(response, "content") and response.content:
                return json.loads(response.content.decode("utf-8"))
        except (ValueError, TypeError, UnicodeDecodeError):
            return {}
        return {}


class ExportDownloadView(APIView):
    permission_classes = [IsAuthenticated]
    schema = AutoSchema(operation_id_base="ReportExportDownload")

    def get(self, request, export_job_id: str) -> FileResponse | Response:  # noqa: D401
        job = get_object_or_404(
            ReportExportJob.objects.filter(tenant_id=request.user.tenant_id),
            id=export_job_id,
        )
        if job.status != ReportExportJob.STATUS_COMPLETED or not job.artifact_path:
            return Response(
                {"detail": "Export is not ready."},
                status=status.HTTP_409_CONFLICT,
            )
        if not job.artifact_path.startswith("/exports/"):
            return Response(
                {"detail": "Export artifact path is invalid."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        base_dir = Path(__file__).resolve().parents[2] / "integrations" / "exporter" / "out"
        artifact_rel = job.artifact_path.lstrip("/")
        artifact_path = (base_dir / artifact_rel).resolve()
        if not str(artifact_path).startswith(str(base_dir.resolve())):
            return Response(
                {"detail": "Export artifact path is unsafe."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not artifact_path.exists():
            return Response(
                {"detail": "Export artifact file was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        content_type, _ = mimetypes.guess_type(str(artifact_path))
        content_type = content_type or "application/octet-stream"

        response = FileResponse(artifact_path.open("rb"), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{artifact_path.name}"'
        return response


class DashboardLibraryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        tenant = request.user.tenant
        tenant_id = tenant.id
        ensure_default_dashboard_presets(tenant=tenant)
        generated_at = (
            TenantMetricsSnapshot.objects.filter(tenant_id=tenant_id, source="warehouse")
            .order_by("-generated_at")
            .values_list("generated_at", flat=True)
            .first()
        )
        updated_at = (generated_at or timezone.now()).date().isoformat()

        saved_dashboards = DashboardDefinition.objects.filter(
            tenant_id=tenant_id, is_active=True
        ).order_by("-updated_at")

        system_templates = [
            {
                **template,
                "kind": "system_template",
                "owner": "System",
                "updatedAt": updated_at,
            }
            for template in DASHBOARD_TEMPLATE_LIBRARY
        ]

        items = []
        for dashboard in saved_dashboards[:50]:
            owner = "Team"
            if dashboard.updated_by and dashboard.updated_by.email:
                owner = dashboard.updated_by.email
            elif dashboard.created_by and dashboard.created_by.email:
                owner = dashboard.created_by.email
            items.append(
                {
                    "id": str(dashboard.id),
                    "kind": "saved_dashboard",
                    "template_key": dashboard.template_key,
                    "name": dashboard.name,
                    "type": dict(DashboardDefinition.TEMPLATE_CHOICES).get(
                        dashboard.template_key, "Saved dashboard"
                    ),
                    "owner": owner,
                    "updatedAt": dashboard.updated_at.date().isoformat(),
                    "tags": [dashboard.default_metric.upper()],
                    "description": dashboard.description or "Saved dashboard configuration.",
                    "route": f"/dashboards/saved/{dashboard.id}",
                    "defaultMetric": dashboard.default_metric,
                    "isActive": dashboard.is_active,
                }
            )

        return Response(
            {
                "generatedAt": timezone.now().isoformat(),
                "systemTemplates": system_templates,
                "savedDashboards": items,
            }
        )


class RecentDashboardsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        tenant_id = request.user.tenant_id
        try:
            limit = int(request.query_params.get("limit", 3))
        except (ValueError, TypeError):
            limit = 3

        dashboards = DashboardDefinition.objects.filter(
            tenant_id=tenant_id, is_active=True
        ).order_by("-updated_at")[:limit]

        items = []
        for dashboard in dashboards:
            owner = "Team"
            if dashboard.updated_by and dashboard.updated_by.email:
                owner = dashboard.updated_by.email
            elif dashboard.created_by and dashboard.created_by.email:
                owner = dashboard.created_by.email

            items.append(
                {
                    "id": str(dashboard.id),
                    "name": dashboard.name,
                    "owner": owner,
                    "last_viewed_at": dashboard.updated_at.isoformat(),
                    "last_viewed_label": f"Updated {dashboard.updated_at.strftime('%b %d, %H:%M')}",
                    "route": f"/dashboards/saved/{dashboard.id}",
                }
            )

        return Response(items)
