from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, Optional
import logging
import uuid

import httpx
from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.audit import log_audit_event
from accounts.tenant_context import tenant_context
from core.metrics import observe_airbyte_sync
from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from integrations.airbyte.service import (
    AttemptSnapshot,
    extract_attempt_snapshot,
    extract_job_created_at,
    extract_job_error,
    extract_job_id,
    extract_job_status,
    extract_job_updated_at,
    infer_completion_time,
)
from .models import (
    AirbyteConnection,
    AirbyteJobTelemetry,
    AlertRuleDefinition,
    CampaignBudget,
    ConnectionSyncUpdate,
    PlatformCredential,
)
from .serializers import (
    AlertRuleDefinitionSerializer,
    CampaignBudgetSerializer,
    PlatformCredentialSerializer,
)


logger = logging.getLogger(__name__)


class PlatformCredentialViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformCredentialSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return PlatformCredential.objects.none()
        return PlatformCredential.objects.filter(tenant_id=user.tenant_id).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        credential = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=credential.tenant,
            user=actor,
            action="credential_created",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": credential.provider,
                "account_id": credential.account_id,
            },
        )

    def perform_update(self, serializer):
        credential = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=credential.tenant,
            user=actor,
            action="credential_updated",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": credential.provider,
                "account_id": credential.account_id,
            },
        )

    def perform_destroy(self, instance):
        tenant = instance.tenant
        credential_id = instance.id
        provider = instance.provider
        account_id = instance.account_id
        actor = self.request.user if self.request.user.is_authenticated else None
        super().perform_destroy(instance)
        log_audit_event(
            tenant=tenant,
            user=actor,
            action="credential_deleted",
            resource_type="platform_credential",
            resource_id=credential_id,
            metadata={"provider": provider, "account_id": account_id},
        )


class AirbyteConnectionViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return AirbyteConnection.objects.none()
        return AirbyteConnection.objects.filter(tenant_id=user.tenant_id).order_by(
            "name"
        )

    @action(detail=False, methods=["get"], url_path="health")
    def health(self, request):
        client = self._create_client()
        if isinstance(client, Response):
            return client

        queryset = self.get_queryset()

        try:
            with client as airbyte:
                connections = [
                    self._serialize_connection(connection, airbyte)
                    for connection in queryset
                ]
        except AirbyteClientError as exc:  # pragma: no cover - handled in helper
            return self._error_response(exc)

        return Response({"connections": connections})

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, pk=None):  # noqa: ANN001 - signature enforced by DRF
        connection = self.get_object()
        client = self._create_client()
        if isinstance(client, Response):
            return client

        try:
            with client as airbyte:
                payload = airbyte.trigger_sync(str(connection.connection_id))
        except AirbyteClientError as exc:  # pragma: no cover - handled in helper
            return self._error_response(exc)

        job_id = self._extract_job_id(payload)

        actor = request.user if request.user.is_authenticated else None
        log_audit_event(
            tenant=connection.tenant,
            user=actor,
            action="airbyte_connection_sync_triggered",
            resource_type="airbyte_connection",
            resource_id=connection.id,
            metadata={
                "connection_id": str(connection.connection_id),
                "job_id": job_id,
            },
        )

        status_code = status.HTTP_202_ACCEPTED if job_id is not None else status.HTTP_200_OK
        return Response({"job_id": job_id}, status=status_code)

    def _create_client(self) -> AirbyteClient | Response:
        try:
            return AirbyteClient.from_settings()
        except AirbyteClientConfigurationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    def _error_response(self, exc: AirbyteClientError) -> Response:
        status_code = (
            status.HTTP_504_GATEWAY_TIMEOUT
            if isinstance(exc.__cause__, httpx.TimeoutException)
            else status.HTTP_502_BAD_GATEWAY
        )
        return Response({"detail": str(exc)}, status=status_code)

    def _serialize_connection(
        self, connection: AirbyteConnection, client: AirbyteClient
    ) -> Dict[str, Any]:
        job_payload = client.latest_job(str(connection.connection_id))
        job_summary = self._summarize_job(job_payload)
        return {
            "id": str(connection.id),
            "name": connection.name,
            "connection_id": str(connection.connection_id),
            "workspace_id": str(connection.workspace_id) if connection.workspace_id else None,
            "provider": connection.provider,
            "last_synced_at": self._format_datetime(connection.last_synced_at),
            "last_job_id": connection.last_job_id or (job_summary.get("id") if job_summary else ""),
            "last_job_status": connection.last_job_status or (job_summary.get("status") if job_summary else ""),
            "last_job_updated_at": self._format_datetime(connection.last_job_updated_at),
            "last_job_completed_at": self._format_datetime(connection.last_job_completed_at),
            "last_job_error": connection.last_job_error or "",
            "latest_job": job_summary,
        }

    def _summarize_job(self, payload: Any) -> Dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
        if not isinstance(job, dict):
            return None
        job_id = job.get("id") or job.get("jobId")
        status_value = job.get("status")
        created_at = job.get("createdAt") or job.get("created_at")
        return {
            "id": str(job_id) if job_id is not None else None,
            "status": status_value,
            "created_at": self._normalise_timestamp(created_at),
        }

    def _normalise_timestamp(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=dt_timezone.utc).isoformat()
        if isinstance(value, str):
            cleaned = value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(cleaned)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_timezone.utc)
            return parsed.isoformat()
        if isinstance(value, datetime):
            parsed = value if value.tzinfo else value.replace(tzinfo=dt_timezone.utc)
            return parsed.isoformat()
        return None

    def _format_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_timezone.utc)
        return value.isoformat()

    def _extract_job_id(self, payload: Any) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
        if not isinstance(job, dict):
            return None
        job_id = job.get("id") or job.get("jobId")
        return str(job_id) if job_id is not None else None


class AirbyteWebhookView(APIView):
    """Handle Airbyte job lifecycle callbacks."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        secret_response = self._verify_secret(request)
        if secret_response is not None:
            return secret_response

        payload = request.data or {}
        connection_or_response = self._resolve_connection(payload)
        if isinstance(connection_or_response, Response):
            return connection_or_response
        connection = connection_or_response

        job_payload = payload.get("job") if isinstance(payload, dict) else None
        job_envelope = job_payload if isinstance(job_payload, dict) else payload

        job_id = extract_job_id(job_envelope)
        job_status = extract_job_status(job_envelope) or payload.get("status")
        created_at = (
            extract_job_created_at(job_envelope)
            or timezone.now()
        )
        snapshot = (
            extract_attempt_snapshot(job_envelope)
            or AttemptSnapshot(
                started_at=created_at,
                duration_seconds=None,
                records_synced=None,
                bytes_synced=None,
                api_cost=None,
            )
        )
        updated_at = extract_job_updated_at(job_envelope) or created_at
        completed_at = infer_completion_time(job_envelope, snapshot)
        error_message = extract_job_error(job_envelope)

        metrics_payload: dict[str, Any] = {}
        if isinstance(job_envelope, dict):
            attempts = job_envelope.get("attempts") or []
            if attempts:
                latest = attempts[-1]
                metrics_payload = (
                    latest.get("metrics")
                    or latest.get("attempt", {}).get("metrics")
                    or {}
                )

        duration_seconds = snapshot.duration_seconds
        if duration_seconds is None:
            time_candidate = (
                metrics_payload.get("timeInMillis")
                or metrics_payload.get("processingTimeInMillis")
                or metrics_payload.get("totalTimeInMillis")
            )
            if time_candidate is not None:
                try:
                    duration_seconds = max(int(int(time_candidate) / 1000), 0)
                except (TypeError, ValueError):  # pragma: no cover - defensive
                    duration_seconds = None

        records_synced = snapshot.records_synced
        if records_synced is None:
            candidate = (
                metrics_payload.get("recordsSynced")
                or metrics_payload.get("recordsEmitted")
                or metrics_payload.get("recordsCommitted")
            )
            if candidate is not None:
                try:
                    records_synced = int(candidate)
                except (TypeError, ValueError):  # pragma: no cover - defensive
                    records_synced = None

        bytes_synced = snapshot.bytes_synced
        if bytes_synced is None:
            candidate_bytes = metrics_payload.get("bytesSynced") or metrics_payload.get("bytesEmitted")
            if candidate_bytes is not None:
                try:
                    bytes_synced = int(candidate_bytes)
                except (TypeError, ValueError):  # pragma: no cover - defensive
                    bytes_synced = None

        with tenant_context(str(connection.tenant_id)):
            update = ConnectionSyncUpdate(
                connection=connection,
                job_id=str(job_id) if job_id is not None else None,
                status=job_status,
                created_at=created_at,
                updated_at=updated_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                records_synced=records_synced,
                bytes_synced=bytes_synced,
                api_cost=snapshot.api_cost,
                error=error_message,
            )
            AirbyteConnection.persist_sync_updates([update])

            if update.job_id:
                started_at = snapshot.started_at or created_at
                AirbyteJobTelemetry.objects.update_or_create(
                    connection=connection,
                    job_id=update.job_id,
                    defaults={
                        "tenant": connection.tenant,
                        "status": job_status or "",
                        "started_at": started_at,
                        "duration_seconds": duration_seconds,
                        "records_synced": records_synced,
                        "bytes_synced": bytes_synced,
                        "api_cost": snapshot.api_cost,
                    },
                )

            observe_airbyte_sync(
                tenant_id=str(connection.tenant_id),
                provider=connection.provider,
                connection_id=str(connection.connection_id),
                duration_seconds=float(duration_seconds)
                if duration_seconds is not None
                else None,
                records_synced=records_synced,
                status=job_status,
            )

            log_audit_event(
                tenant=connection.tenant,
                user=None,
                action="airbyte_job_webhook",
                resource_type="airbyte_connection",
                resource_id=connection.id,
                metadata={
                    "connection_id": str(connection.connection_id),
                    "job_id": update.job_id,
                    "status": job_status,
                    "records_synced": records_synced,
                    "duration_seconds": duration_seconds,
                    "error": error_message,
                },
            )

        logger.info(
            "Airbyte webhook processed",
            extra={
                "tenant_id": str(connection.tenant_id),
                "connection_id": str(connection.connection_id),
                "job_id": update.job_id,
                "status": job_status,
            },
        )

        status_code = (
            status.HTTP_202_ACCEPTED
            if job_status and job_status.lower() not in {"succeeded", "success"}
            else status.HTTP_200_OK
        )
        return Response(
            {
                "connection_id": str(connection.connection_id),
                "job_id": update.job_id,
                "status": job_status,
                "received_at": timezone.now().isoformat(),
            },
            status=status_code,
        )

    def _verify_secret(self, request) -> Response | None:
        required = getattr(settings, "AIRBYTE_WEBHOOK_SECRET_REQUIRED", True)
        expected = getattr(settings, "AIRBYTE_WEBHOOK_SECRET", None)
        if not expected:
            if required:
                logger.error("Airbyte webhook secret required but not configured")
                return Response(
                    {"detail": "webhook secret not configured"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return None
        provided = request.headers.get("X-Airbyte-Webhook-Secret")
        if provided == expected:
            return None
        logger.warning(
            "Airbyte webhook secret mismatch",
            extra={"provided": bool(provided)},
        )
        return Response({"detail": "invalid webhook secret"}, status=status.HTTP_403_FORBIDDEN)

    def _resolve_connection(self, payload: dict) -> AirbyteConnection | Response:
        identifier = self._extract_connection_id(payload)
        if identifier is None:
            return Response({"detail": "connection_id missing"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            connection_uuid = uuid.UUID(str(identifier))
        except ValueError:
            return Response({"detail": "invalid connection_id"}, status=status.HTTP_400_BAD_REQUEST)
        connection = (
            AirbyteConnection.all_objects.select_related("tenant")
            .filter(connection_id=connection_uuid)
            .first()
        )
        if connection is None:
            return Response({"detail": "connection not found"}, status=status.HTTP_404_NOT_FOUND)
        return connection

    def _extract_connection_id(self, payload: dict) -> str | None:
        if not isinstance(payload, dict):
            return None
        job_payload = payload.get("job") if isinstance(payload.get("job"), dict) else None
        candidates = [
            payload.get("connectionId"),
            payload.get("connection_id"),
        ]
        if isinstance(job_payload, dict):
            candidates.extend(
                [job_payload.get("connectionId"), job_payload.get("connection_id")]
            )
        for candidate in candidates:
            if candidate:
                return candidate
        return None


class CampaignBudgetViewSet(viewsets.ModelViewSet):
    serializer_class = CampaignBudgetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return CampaignBudget.objects.none()
        return CampaignBudget.objects.filter(tenant_id=user.tenant_id).order_by("name")

    def _actor(self):
        user = self.request.user
        return user if user and user.is_authenticated else None

    def _audit_metadata(self, fields: list[str]) -> dict[str, object]:
        return {"redacted": True, "fields": sorted(fields)}

    def perform_create(self, serializer):
        validated_fields = list(serializer.validated_data.keys())
        actor = self._actor()
        tenant = getattr(actor, "tenant", None) if actor is not None else None
        if tenant is not None:
            budget = serializer.save(tenant=tenant)
        else:  # pragma: no cover - permission guards ensure actor exists
            budget = serializer.save()
        log_audit_event(
            tenant=budget.tenant,
            user=actor,
            action="campaign_budget_created",
            resource_type="campaign_budget",
            resource_id=budget.id,
            metadata=self._audit_metadata(validated_fields),
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        validated_data = serializer.validated_data
        changed_fields = [
            field
            for field, value in validated_data.items()
            if getattr(instance, field) != value
        ]
        budget = serializer.save()
        log_audit_event(
            tenant=budget.tenant,
            user=self._actor(),
            action="campaign_budget_updated",
            resource_type="campaign_budget",
            resource_id=budget.id,
            metadata=self._audit_metadata(changed_fields),
        )

    def perform_destroy(self, instance):
        tenant = instance.tenant
        budget_id = instance.id
        super().perform_destroy(instance)
        log_audit_event(
            tenant=tenant,
            user=self._actor(),
            action="campaign_budget_deleted",
            resource_type="campaign_budget",
            resource_id=budget_id,
            metadata=self._audit_metadata([]),
        )


class AlertRuleDefinitionViewSet(viewsets.ModelViewSet):
    serializer_class = AlertRuleDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return AlertRuleDefinition.objects.none()
        return AlertRuleDefinition.objects.filter(
            tenant_id=user.tenant_id
        ).order_by("name")

    def _audit_metadata(self, serializer) -> dict[str, object]:
        fields = sorted(serializer.validated_data.keys())
        return {"redacted": True, "fields": fields}

    def perform_create(self, serializer):
        alert_rule = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=alert_rule.tenant,
            user=actor,
            action="alert_rule_created",
            resource_type="alert_rule_definition",
            resource_id=alert_rule.id,
            metadata=self._audit_metadata(serializer),
        )

    def perform_update(self, serializer):
        alert_rule = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=alert_rule.tenant,
            user=actor,
            action="alert_rule_updated",
            resource_type="alert_rule_definition",
            resource_id=alert_rule.id,
            metadata=self._audit_metadata(serializer),
        )
