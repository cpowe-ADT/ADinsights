from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from django.http import HttpResponseBase
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.audit import log_audit_event
from analytics.models import AISummary, ReportDefinition, ReportExportJob, TenantMetricsSnapshot
from integrations.models import AirbyteConnection
from integrations.views import AlertRuleDefinitionViewSet

from .phase2_serializers import (
    AISummarySerializer,
    ReportDefinitionSerializer,
    ReportExportCreateSerializer,
    ReportExportJobSerializer,
)

logger = logging.getLogger(__name__)

SYNC_HEALTH_STALE_THRESHOLD = timedelta(hours=2)


class ReportDefinitionViewSet(viewsets.ModelViewSet):
    serializer_class = ReportDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated]

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

    @action(detail=True, methods=["get", "post"], url_path="exports")
    def exports(self, request, pk=None):
        report = self.get_object()
        actor = request.user if request.user.is_authenticated else None

        if request.method.lower() == "get":
            jobs = report.export_jobs.filter(tenant_id=report.tenant_id).order_by("-created_at")
            return Response(ReportExportJobSerializer(jobs, many=True).data)

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


class AlertsViewSet(AlertRuleDefinitionViewSet):
    """Expose tenant alert rule management at /api/alerts/."""


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


class DashboardLibraryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        tenant_id = request.user.tenant_id
        generated_at = (
            TenantMetricsSnapshot.objects.filter(tenant_id=tenant_id, source="warehouse")
            .order_by("-generated_at")
            .values_list("generated_at", flat=True)
            .first()
        )
        updated_at = (generated_at or timezone.now()).date().isoformat()

        reports = ReportDefinition.objects.filter(tenant_id=tenant_id, is_active=True).order_by("-updated_at")

        items = [
            {
                "id": "dash-campaigns-core",
                "name": "Campaign performance overview",
                "type": "Campaigns",
                "owner": "System",
                "updatedAt": updated_at,
                "tags": ["ROAS", "Spend", "Conversions"],
                "description": "Daily campaign KPIs with trend and map context.",
                "route": "/dashboards/campaigns",
            },
            {
                "id": "dash-creatives-top",
                "name": "Creative leaderboard",
                "type": "Creatives",
                "owner": "System",
                "updatedAt": updated_at,
                "tags": ["CTR", "Clicks", "Thumbnails"],
                "description": "Top creative performance with preview thumbnails.",
                "route": "/dashboards/creatives",
            },
            {
                "id": "dash-budget-pace",
                "name": "Budget pacing check-in",
                "type": "Budget pacing",
                "owner": "System",
                "updatedAt": updated_at,
                "tags": ["Pacing", "Forecast", "Risk"],
                "description": "Monitor monthly pacing and spend risk flags.",
                "route": "/dashboards/budget",
            },
            {
                "id": "dash-parish-map",
                "name": "Parish map snapshot",
                "type": "Parish map",
                "owner": "System",
                "updatedAt": updated_at,
                "tags": ["Geo", "Map", "Reach"],
                "description": "Geo performance map with metric toggles.",
                "route": "/dashboards/map",
            },
        ]

        for report in reports[:20]:
            owner = "Team"
            if report.updated_by and report.updated_by.email:
                owner = report.updated_by.email
            elif report.created_by and report.created_by.email:
                owner = report.created_by.email
            items.append(
                {
                    "id": f"report-{report.id}",
                    "name": report.name,
                    "type": "Campaigns",
                    "owner": owner,
                    "updatedAt": report.updated_at.date().isoformat(),
                    "tags": ["Report"],
                    "description": report.description or "Saved report configuration.",
                    "route": f"/reports/{report.id}",
                }
            )

        return Response(items)
