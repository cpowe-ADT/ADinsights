from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, Optional

import httpx
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.audit import log_audit_event
from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from .models import (
    AirbyteConnection,
    AlertRuleDefinition,
    CampaignBudget,
    PlatformCredential,
)
from .serializers import (
    AlertRuleDefinitionSerializer,
    CampaignBudgetSerializer,
    PlatformCredentialSerializer,
)


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
            "last_synced_at": self._format_datetime(connection.last_synced_at),
            "last_job_id": connection.last_job_id or (job_summary.get("id") if job_summary else ""),
            "last_job_status": connection.last_job_status or (job_summary.get("status") if job_summary else ""),
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
