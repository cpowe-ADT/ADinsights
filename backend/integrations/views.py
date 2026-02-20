from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Dict, Optional
import logging
import secrets
import uuid
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from accounts.audit import log_audit_event
from accounts.models import AuditLog
from accounts.tenant_context import tenant_context
from core.db_error_responses import schema_out_of_date_response
from core.metrics import observe_airbyte_sync
from core.observability import emit_observability_event
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
    MetaAccountSyncState,
    PlatformCredential,
    TenantAirbyteSyncStatus,
)
from .serializers import (
    AirbyteConnectionSerializer,
    AlertRuleDefinitionSerializer,
    CampaignBudgetSerializer,
    MetaOAuthExchangeSerializer,
    MetaOAuthStartSerializer,
    MetaPageConnectSerializer,
    MetaProvisionSerializer,
    MetaSystemTokenSerializer,
    MetaAccountSyncStateSerializer,
    PlatformCredentialSerializer,
    SocialConnectionStatusResponseSerializer,
)
from .meta_graph import MetaGraphClient, MetaGraphClientError, MetaGraphConfigurationError
from core.serializers import TenantAirbyteSyncStatusSerializer


logger = logging.getLogger(__name__)

META_OAUTH_STATE_SALT = "integrations.meta.oauth.state"
META_OAUTH_SELECTION_CACHE_PREFIX = "integrations:meta:selection:"
META_OAUTH_STATE_MAX_AGE_SECONDS = 600
META_OAUTH_SELECTION_TTL_SECONDS = 600
META_OAUTH_FLOW_MARKETING = "marketing"
META_OAUTH_FLOW_PAGE_INSIGHTS = "page_insights"
DEFAULT_CONNECTOR_CRON_EXPRESSION = "0 6-22 * * *"
DEFAULT_CONNECTOR_TIMEZONE = "America/Jamaica"
# Airbyte OSS source definition ID for Facebook Marketing.
DEFAULT_META_SOURCE_DEFINITION_ID = "e7778cfc-e97c-4458-9ecb-b4f2bba8946c"
DEFAULT_META_REQUIRED_SCOPE_ANY = ("ads_read", "ads_management")
DEFAULT_META_REQUIRED_SCOPE_ALL = (
    "business_management",
    "pages_read_engagement",
    "pages_show_list",
)
DEFAULT_META_REQUIRED_SCOPES = [
    *DEFAULT_META_REQUIRED_SCOPE_ANY,
    *DEFAULT_META_REQUIRED_SCOPE_ALL,
]
DEFAULT_META_OAUTH_SCOPES = [
    "ads_read",
    "ads_management",
    "business_management",
    "pages_show_list",
    "pages_read_engagement",
]
DEFAULT_META_PAGE_INSIGHTS_OAUTH_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_metadata",
]
DEFAULT_META_INSTAGRAM_REQUIRED_SCOPES = [
    "instagram_basic",
    "instagram_manage_insights",
]
DEFAULT_META_LOGIN_IGNORED_SCOPES = {
    "instagram_basic",
    "instagram_manage_insights",
    "read_insights",
}
SOCIAL_STATUS_STALE_THRESHOLD_MINUTES = 60
SOCIAL_SUCCESS_STATUSES = {"succeeded", "success", "completed"}


def _meta_redirect_uri() -> str:
    configured = (getattr(settings, "META_OAUTH_REDIRECT_URI", "") or "").strip()
    if configured:
        return configured
    frontend_base = (getattr(settings, "FRONTEND_BASE_URL", "") or "").strip().rstrip("/")
    if not frontend_base:
        raise MetaGraphConfigurationError(
            "META_OAUTH_REDIRECT_URI or FRONTEND_BASE_URL must be configured for Meta OAuth."
        )
    return f"{frontend_base}/dashboards/data-sources"


def _meta_state_payload(*, request) -> dict[str, str]:
    path = (getattr(request, "path", "") or "").rstrip("/")
    flow = (
        META_OAUTH_FLOW_PAGE_INSIGHTS
        if path.endswith("/api/meta/connect/start")
        else META_OAUTH_FLOW_MARKETING
    )
    return {
        "tenant_id": str(request.user.tenant_id),
        "user_id": str(request.user.id),
        "nonce": secrets.token_urlsafe(24),
        "flow": flow,
    }


def _oauth_flow_for_request(*, request) -> str:
    path = (getattr(request, "path", "") or "").rstrip("/")
    if path.endswith("/api/meta/connect/start"):
        return META_OAUTH_FLOW_PAGE_INSIGHTS
    return META_OAUTH_FLOW_MARKETING


def _sign_meta_state(*, request) -> str:
    return signing.dumps(_meta_state_payload(request=request), salt=META_OAUTH_STATE_SALT)


def _validate_meta_state(*, request, state: str) -> tuple[dict[str, Any], Response | None]:
    try:
        payload = signing.loads(
            state,
            salt=META_OAUTH_STATE_SALT,
            max_age=META_OAUTH_STATE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired:
        return {}, Response(
            {"detail": "Meta OAuth state expired. Restart the connect flow."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except signing.BadSignature:
        return {}, Response(
            {"detail": "Meta OAuth state is invalid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if payload.get("user_id") != str(request.user.id) or payload.get("tenant_id") != str(request.user.tenant_id):
        return {}, Response(
            {"detail": "Meta OAuth state does not match the authenticated tenant user."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return payload, None


def _meta_login_configuration_id() -> str:
    return (getattr(settings, "META_LOGIN_CONFIG_ID", "") or "").strip()


def _meta_login_configuration_required() -> bool:
    return bool(getattr(settings, "META_LOGIN_CONFIG_REQUIRED", True))


def _is_unset_or_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    normalized = value.strip()
    if not normalized:
        return True
    lowered = normalized.lower()
    return lowered.startswith("replace_") or "placeholder" in lowered or lowered in {
        "replace-me",
        "changeme",
    }


def _find_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def _configured_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    raw_streams = catalog.get("streams") or []
    configured_streams: list[dict[str, Any]] = []
    for raw in raw_streams:
        if not isinstance(raw, dict):
            continue
        # Airbyte can return either discovered streams (`{name, supportedSyncModes, ...}`)
        # or preconfigured streams (`{stream: {...}, config: {...}}`).
        stream_def = raw.get("stream") if isinstance(raw.get("stream"), dict) else raw
        if not isinstance(stream_def, dict):
            continue

        supported_sync_modes = stream_def.get("supportedSyncModes") or ["full_refresh"]
        supported_dest_modes = stream_def.get("supportedDestinationSyncModes") or ["append"]
        incremental_supported = "incremental" in supported_sync_modes

        if incremental_supported:
            sync_mode = "incremental"
            if "append_dedup" in supported_dest_modes:
                destination_sync_mode = "append_dedup"
            elif "append" in supported_dest_modes:
                destination_sync_mode = "append"
            else:
                destination_sync_mode = supported_dest_modes[0]
        else:
            sync_mode = "full_refresh"
            destination_sync_mode = "overwrite" if "overwrite" in supported_dest_modes else supported_dest_modes[0]

        cursor_field = stream_def.get("defaultCursorField") or []
        if not isinstance(cursor_field, list):
            cursor_field = []
        primary_key = stream_def.get("sourceDefinedPrimaryKey") or []
        if not isinstance(primary_key, list):
            primary_key = []

        configured_streams.append(
            {
                "stream": stream_def,
                "config": {
                    "aliasName": stream_def.get("name"),
                    "selected": True,
                    "syncMode": sync_mode,
                    "destinationSyncMode": destination_sync_mode,
                    "cursorField": cursor_field if incremental_supported else [],
                    "primaryKey": primary_key,
                },
            }
        )

    if not configured_streams:
        raise ValueError("Discovered catalog has no streams.")
    return {"streams": configured_streams}


def _schedule_payload(*, schedule_type: str, interval_minutes: int | None, cron_expression: str) -> dict[str, Any]:
    if schedule_type == AirbyteConnection.SCHEDULE_MANUAL:
        return {"scheduleType": "manual", "scheduleData": None}
    if schedule_type == AirbyteConnection.SCHEDULE_INTERVAL:
        units = max(int(interval_minutes or 1), 1)
        return {
            "scheduleType": "basic",
            "scheduleData": {"basicSchedule": {"timeUnit": "minutes", "units": units}},
        }
    return {
        "scheduleType": "cron",
        "scheduleData": {
            "cron": {
                "cronExpression": _to_airbyte_cron_expression(
                    cron_expression or DEFAULT_CONNECTOR_CRON_EXPRESSION
                ),
                "cronTimeZone": DEFAULT_CONNECTOR_TIMEZONE,
            }
        },
    }


def _to_airbyte_cron_expression(expression: str) -> str:
    fields = [field for field in expression.split() if field]
    if len(fields) != 5:
        return expression

    minute, hour, day_of_month, month, day_of_week = fields
    normalized_day_of_month = day_of_month
    normalized_day_of_week = day_of_week
    if day_of_month == "*" and day_of_week == "*":
        normalized_day_of_week = "?"
    elif day_of_month == "*":
        normalized_day_of_month = "?"
    elif day_of_week == "*":
        normalized_day_of_week = "?"

    # Quartz format: second minute hour day-of-month month day-of-week.
    return " ".join(
        [
            "0",
            minute,
            hour,
            normalized_day_of_month,
            month,
            normalized_day_of_week,
        ]
    )


def _normalize_meta_account_id(raw_value: str) -> str:
    cleaned = raw_value.strip()
    if cleaned.startswith("act_"):
        digits = cleaned[4:]
        if digits.isdigit():
            return f"act_{digits}"
        return cleaned
    if cleaned.isdigit():
        return f"act_{cleaned}"
    return cleaned


def _meta_numeric_account_id(raw_value: str) -> str:
    normalized = _normalize_meta_account_id(raw_value)
    if normalized.startswith("act_") and normalized[4:].isdigit():
        return normalized[4:]
    return normalized


def _resolve_meta_source_definition_id(requested: str | None) -> str:
    if requested:
        return requested
    configured = (getattr(settings, "AIRBYTE_SOURCE_DEFINITION_META", "") or "").strip()
    if configured:
        return configured
    return DEFAULT_META_SOURCE_DEFINITION_ID


def _resolve_meta_credential(*, request, external_account_id: str | None) -> PlatformCredential | None:
    queryset = PlatformCredential.objects.filter(tenant_id=request.user.tenant_id, provider=PlatformCredential.META)
    if external_account_id:
        normalized = _normalize_meta_account_id(external_account_id)
        queryset = queryset.filter(account_id__in={external_account_id, normalized})
    return queryset.order_by("-updated_at").first()


def _normalize_scopes(raw_scopes: Any) -> list[str]:
    if not isinstance(raw_scopes, list):
        return []
    normalized = sorted(
        {
            str(scope).strip()
            for scope in raw_scopes
            if isinstance(scope, str) and str(scope).strip()
        }
    )
    return normalized


def _resolve_meta_login_scopes(*, flow: str = META_OAUTH_FLOW_MARKETING) -> tuple[list[str], list[str]]:
    if flow == META_OAUTH_FLOW_PAGE_INSIGHTS:
        configured_scopes = getattr(
            settings,
            "META_PAGE_INSIGHTS_OAUTH_SCOPES",
            DEFAULT_META_PAGE_INSIGHTS_OAUTH_SCOPES,
        )
    else:
        configured_scopes = getattr(settings, "META_OAUTH_SCOPES", DEFAULT_META_OAUTH_SCOPES)
    resolved: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()

    for scope in configured_scopes:
        if not isinstance(scope, str):
            continue
        candidate = scope.strip().lower()
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate in DEFAULT_META_LOGIN_IGNORED_SCOPES:
            ignored.append(candidate)
            continue
        resolved.append(candidate)

    return resolved, ignored


def _missing_required_permissions(granted_scopes: list[str]) -> list[str]:
    granted = {scope.strip() for scope in granted_scopes if isinstance(scope, str) and scope.strip()}
    missing: list[str] = []
    if not granted.intersection(DEFAULT_META_REQUIRED_SCOPE_ANY):
        missing.append("ads_read_or_ads_management")
    missing.extend(scope for scope in DEFAULT_META_REQUIRED_SCOPE_ALL if scope not in granted)
    return sorted(missing)


def _token_status_for_expiry(*, expires_at: datetime | None, now: datetime) -> tuple[str, str]:
    if expires_at is None:
        return (PlatformCredential.TOKEN_STATUS_VALID, "")
    if expires_at <= now:
        return (
            PlatformCredential.TOKEN_STATUS_INVALID,
            "Token expiry timestamp is in the past.",
        )
    if expires_at <= now + timedelta(days=7):
        return (
            PlatformCredential.TOKEN_STATUS_EXPIRING,
            "Token expiry is within 7 days.",
        )
    return (PlatformCredential.TOKEN_STATUS_VALID, "")


def _default_meta_window(*, now: datetime) -> tuple[datetime.date, datetime.date]:
    window_end = (now - timedelta(days=1)).date()
    window_start = window_end - timedelta(days=3)
    return window_start, window_end


def _resolve_meta_account_for_connection(*, connection: AirbyteConnection) -> str | None:
    state = (
        MetaAccountSyncState.objects.filter(
            tenant_id=connection.tenant_id,
            connection=connection,
        )
        .order_by("-updated_at")
        .first()
    )
    if state is not None:
        return state.account_id

    credential = (
        PlatformCredential.objects.filter(
            tenant_id=connection.tenant_id,
            provider=PlatformCredential.META,
        )
        .order_by("-updated_at")
        .first()
    )
    return credential.account_id if credential is not None else None


def _upsert_meta_account_sync_state(
    *,
    tenant,
    account_id: str,
    connection: AirbyteConnection | None = None,
    job_id: str | None = None,
    job_status: str | None = None,
    job_error: str | None = None,
    sync_started_at: datetime | None = None,
    sync_completed_at: datetime | None = None,
    window_start: datetime.date | None = None,
    window_end: datetime.date | None = None,
) -> MetaAccountSyncState:
    normalized_account_id = _normalize_meta_account_id(account_id)
    state, _ = MetaAccountSyncState.all_objects.get_or_create(
        tenant=tenant,
        account_id=normalized_account_id,
    )

    update_fields: list[str] = []
    if connection is not None and state.connection_id != connection.id:
        state.connection = connection
        update_fields.append("connection")
    if job_id is not None:
        state.last_job_id = job_id
        update_fields.append("last_job_id")
    if job_status is not None:
        state.last_job_status = job_status
        update_fields.append("last_job_status")
    if job_error is not None:
        state.last_job_error = job_error
        update_fields.append("last_job_error")
    if sync_started_at is not None:
        state.last_sync_started_at = sync_started_at
        update_fields.append("last_sync_started_at")
    if sync_completed_at is not None:
        state.last_sync_completed_at = sync_completed_at
        update_fields.append("last_sync_completed_at")
    if window_start is not None:
        state.last_window_start = window_start
        update_fields.append("last_window_start")
    if window_end is not None:
        state.last_window_end = window_end
        update_fields.append("last_window_end")

    if job_status and job_status.lower() in SOCIAL_SUCCESS_STATUSES:
        state.last_success_at = sync_completed_at or sync_started_at or timezone.now()
        update_fields.append("last_success_at")

    if update_fields:
        state.save(update_fields=sorted(set(update_fields + ["updated_at"])))
    return state


def _airbyte_exception_response(exc: AirbyteClientError) -> Response:
    status_code = (
        status.HTTP_504_GATEWAY_TIMEOUT
        if isinstance(exc.__cause__, httpx.TimeoutException)
        else status.HTTP_502_BAD_GATEWAY
    )
    return Response({"detail": str(exc)}, status=status_code)


def _looks_like_airbyte_source_config_error(message: str) -> bool:
    lowered = message.lower()
    indicators = [
        "configuration does not fulfill the specification",
        "json schema validation failed",
        "config validation error",
        "is a required property",
        "must be a constant value",
        "does not have a value in the enumeration",
    ]
    return any(indicator in lowered for indicator in indicators)


def _is_airbyte_source_config_schema_error(exc: AirbyteClientError) -> bool:
    return _looks_like_airbyte_source_config_error(str(exc))


def _is_meta_ad_account_id(value: str) -> bool:
    normalized = _normalize_meta_account_id(value)
    return normalized.startswith("act_") and normalized[4:].isdigit()


def _is_connection_active(connection: AirbyteConnection | None, now) -> bool:
    if connection is None or connection.is_active is False:
        return False
    if connection.last_job_error:
        return False
    if (connection.last_job_status or "").lower() not in SOCIAL_SUCCESS_STATUSES:
        return False
    if not connection.last_synced_at:
        return False
    return now - connection.last_synced_at <= timedelta(minutes=SOCIAL_STATUS_STALE_THRESHOLD_MINUTES)


def _select_preferred_meta_connection(connections: list[AirbyteConnection], now) -> AirbyteConnection | None:
    if not connections:
        return None

    def score(connection: AirbyteConnection) -> tuple[int, datetime]:
        if _is_connection_active(connection, now):
            return (4, connection.updated_at)
        if connection.is_active and not connection.last_job_error:
            return (3, connection.updated_at)
        if connection.is_active is False:
            return (2, connection.updated_at)
        return (1, connection.updated_at)

    return sorted(connections, key=score, reverse=True)[0]


def _resolve_meta_status(
    *,
    credential: PlatformCredential | None,
    connection: AirbyteConnection | None,
    now,
    oauth_ready: bool,
    provisioning_defaults_ready: bool,
) -> tuple[str, dict[str, str], list[str]]:
    if credential is None:
        return (
            "not_connected",
            {
                "code": "missing_meta_credential",
                "message": "Meta OAuth has not been connected for this tenant.",
            },
            ["connect_oauth"],
        )

    if credential.token_status in {
        PlatformCredential.TOKEN_STATUS_INVALID,
        PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
    }:
        return (
            "started_not_complete",
            {
                "code": "credential_reauth_required",
                "message": credential.token_status_reason
                or "Meta credential needs to be re-authorized.",
            },
            ["connect_oauth"],
        )

    has_valid_ad_account = _is_meta_ad_account_id(credential.account_id)
    if not has_valid_ad_account:
        return (
            "started_not_complete",
            {
                "code": "missing_ad_account_selection",
                "message": "Meta credential exists but ad account selection is incomplete.",
            },
            ["select_assets"],
        )

    if not oauth_ready:
        return (
            "started_not_complete",
            {
                "code": "oauth_not_ready",
                "message": "Meta OAuth app configuration is incomplete.",
            },
            ["connect_oauth"],
        )

    if not provisioning_defaults_ready or connection is None:
        return (
            "started_not_complete",
            {
                "code": "provisioning_incomplete",
                "message": "Meta is connected but provisioning/sync setup is incomplete.",
            },
            ["provision"],
        )

    if _is_connection_active(connection, now):
        return (
            "active",
            {
                "code": "active_sync",
                "message": "Meta connection is active and recently synced.",
            },
            ["sync_now", "view"],
        )

    if connection.is_active is False:
        return (
            "complete",
            {
                "code": "connection_paused",
                "message": "Meta setup is complete, but sync is paused.",
            },
            ["provision", "view"],
        )

    return (
        "complete",
        {
            "code": "awaiting_recent_successful_sync",
            "message": "Meta setup is complete, waiting for a recent successful sync.",
        },
        ["sync_now", "view"],
    )


class MetaOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = MetaOAuthStartSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        auth_type = serializer.validated_data.get("auth_type")

        try:
            app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
            if not app_id:
                raise MetaGraphConfigurationError("META_APP_ID must be configured for Meta OAuth.")
            redirect_uri = _meta_redirect_uri()
            login_configuration_id = _meta_login_configuration_id()
            login_configuration_required = _meta_login_configuration_required()
            if login_configuration_required and not login_configuration_id:
                raise MetaGraphConfigurationError(
                    "META_LOGIN_CONFIG_ID must be configured for Meta OAuth."
                )
        except MetaGraphConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        signed_state = _sign_meta_state(request=request)
        flow = _oauth_flow_for_request(request=request)
        scopes, ignored_scopes = _resolve_meta_login_scopes(flow=flow)
        query_payload: dict[str, str] = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "state": signed_state,
            "response_type": "code",
            "override_default_response_type": "true",
            "scope": ",".join(scopes),
        }
        if login_configuration_required and login_configuration_id:
            query_payload["config_id"] = login_configuration_id
        if isinstance(auth_type, str) and auth_type.strip():
            query_payload["auth_type"] = auth_type.strip()
        query = urlencode(
            query_payload
        )
        graph_version = (getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0").strip()
        authorize_url = f"https://www.facebook.com/{graph_version}/dialog/oauth?{query}"
        return Response(
            {
                "authorize_url": authorize_url,
                "state": signed_state,
                "redirect_uri": redirect_uri,
                "login_configuration_id": (
                    login_configuration_id if login_configuration_required and login_configuration_id else None
                ),
                "oauth_flow": flow,
                "ignored_scopes": ignored_scopes,
            }
        )


class MetaSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        app_secret = (getattr(settings, "META_APP_SECRET", "") or "").strip()
        login_configuration_id = _meta_login_configuration_id()
        login_configuration_required = _meta_login_configuration_required()
        frontend_base_url = (getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
        redirect_uri_configured = bool(
            (getattr(settings, "META_OAUTH_REDIRECT_URI", "") or "").strip()
            or frontend_base_url
        )
        login_configuration_ready = bool(login_configuration_id) or not login_configuration_required
        scopes, ignored_scopes = _resolve_meta_login_scopes()
        scope_set = {scope.strip() for scope in scopes if isinstance(scope, str) and scope.strip()}
        workspace_id_raw = (getattr(settings, "AIRBYTE_DEFAULT_WORKSPACE_ID", "") or "").strip()
        destination_id_raw = (getattr(settings, "AIRBYTE_DEFAULT_DESTINATION_ID", "") or "").strip()
        workspace_id = "" if _is_unset_or_placeholder(workspace_id_raw) else workspace_id_raw
        destination_id = "" if _is_unset_or_placeholder(destination_id_raw) else destination_id_raw
        source_definition_id = _resolve_meta_source_definition_id(None)
        source_definition_configured = bool(
            (getattr(settings, "AIRBYTE_SOURCE_DEFINITION_META", "") or "").strip()
        )

        ready_for_oauth = bool(app_id and app_secret and redirect_uri_configured and login_configuration_ready)
        ready_for_provisioning_defaults = bool(workspace_id and destination_id)
        meta_app_missing = []
        if not app_id:
            meta_app_missing.append("META_APP_ID")
        if not app_secret:
            meta_app_missing.append("META_APP_SECRET")
        login_configuration_missing = []
        if not login_configuration_ready:
            login_configuration_missing.append("META_LOGIN_CONFIG_ID")
        redirect_missing = []
        if not redirect_uri_configured:
            redirect_missing = ["META_OAUTH_REDIRECT_URI", "FRONTEND_BASE_URL"]
        workspace_missing = [] if workspace_id else ["AIRBYTE_DEFAULT_WORKSPACE_ID"]
        destination_missing = [] if destination_id else ["AIRBYTE_DEFAULT_DESTINATION_ID"]
        source_definition_missing = [] if source_definition_configured else ["AIRBYTE_SOURCE_DEFINITION_META"]
        marketing_scope_missing = _missing_required_permissions(sorted(scope_set))

        checks = [
            {
                "key": "meta_app_credentials",
                "label": "Meta app ID/secret configured",
                "ok": bool(app_id and app_secret),
                "env_vars": ["META_APP_ID", "META_APP_SECRET"],
                "missing_env_vars": meta_app_missing,
            },
            {
                "key": "meta_redirect_uri",
                "label": "Meta OAuth redirect configured",
                "ok": redirect_uri_configured,
                "env_vars": ["META_OAUTH_REDIRECT_URI", "FRONTEND_BASE_URL"],
                "missing_env_vars": redirect_missing,
            },
            {
                "key": "meta_login_configuration_id",
                "label": "Meta Login for Business configuration ID set",
                "ok": login_configuration_ready,
                "required": login_configuration_required,
                "env_vars": ["META_LOGIN_CONFIG_ID"],
                "missing_env_vars": login_configuration_missing,
            },
            {
                "key": "airbyte_workspace_default",
                "label": "Default Airbyte workspace configured",
                "ok": bool(workspace_id),
                "env_vars": ["AIRBYTE_DEFAULT_WORKSPACE_ID"],
                "missing_env_vars": workspace_missing,
            },
            {
                "key": "airbyte_destination_default",
                "label": "Default Airbyte destination configured",
                "ok": bool(destination_id),
                "env_vars": ["AIRBYTE_DEFAULT_DESTINATION_ID"],
                "missing_env_vars": destination_missing,
            },
            {
                "key": "airbyte_source_definition_meta",
                "label": "Meta source definition set",
                "ok": source_definition_configured,
                "using_fallback_default": not source_definition_configured,
                "env_vars": ["AIRBYTE_SOURCE_DEFINITION_META"],
                "missing_env_vars": source_definition_missing,
            },
            {
                "key": "meta_marketing_scopes",
                "label": "Meta Marketing API scopes included",
                "ok": not marketing_scope_missing,
                "required_scopes": DEFAULT_META_REQUIRED_SCOPES,
                "missing_scopes": marketing_scope_missing,
            },
            {
                "key": "meta_instagram_scopes",
                "label": "Instagram scopes requested via Facebook Login",
                "ok": True,
                "required": False,
                "required_scopes": DEFAULT_META_INSTAGRAM_REQUIRED_SCOPES,
                "ignored_scopes": ignored_scopes,
                "note": "Instagram scopes are ignored in Facebook Login authorize requests.",
            },
        ]
        missing_env_vars = sorted(
            {
                var
                for check in checks
                for var in check.get("missing_env_vars", [])
                if isinstance(var, str) and var
            }
        )

        try:
            resolved_redirect_uri = _meta_redirect_uri()
        except MetaGraphConfigurationError:
            resolved_redirect_uri = None

        return Response(
            {
                "provider": "meta_ads",
                "ready_for_oauth": ready_for_oauth,
                "ready_for_provisioning_defaults": ready_for_provisioning_defaults,
                "checks": checks,
                "missing_env_vars": missing_env_vars,
                "oauth_scopes": scopes,
                "oauth_ignored_scopes": ignored_scopes,
                "graph_api_version": (getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0").strip(),
                "redirect_uri": resolved_redirect_uri,
                "source_definition_id": source_definition_id,
                "login_configuration_id_configured": bool(login_configuration_id),
                "login_configuration_id": login_configuration_id or None,
                "login_configuration_required": login_configuration_required,
                "login_mode": "facebook_login_for_business",
            }
        )


class MetaOAuthExchangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = MetaOAuthExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload, state_error = _validate_meta_state(request=request, state=str(serializer.validated_data["state"]))
        if state_error is not None:
            return state_error
        if payload.get("flow") == META_OAUTH_FLOW_PAGE_INSIGHTS:
            return Response(
                {
                    "detail": "OAuth state belongs to the Page Insights flow. Use /api/meta/connect/callback/.",
                    "code": "wrong_oauth_flow",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = str(serializer.validated_data["code"])
        try:
            redirect_uri = _meta_redirect_uri()
            with MetaGraphClient.from_settings() as client:
                short_lived = client.exchange_code(code=code, redirect_uri=redirect_uri)
                try:
                    token = client.exchange_for_long_lived_user_token(
                        short_lived_user_token=short_lived.access_token
                    )
                except MetaGraphClientError:
                    token = short_lived
                token_debug = client.debug_token(input_token=token.access_token)
                debug_valid = bool(token_debug.get("is_valid"))
                debug_app_id_raw = token_debug.get("app_id")
                debug_app_id = str(debug_app_id_raw) if debug_app_id_raw is not None else ""
                configured_app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
                if not debug_valid:
                    return Response(
                        {"detail": "Meta OAuth token failed debug_token validation."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if configured_app_id and debug_app_id and debug_app_id != configured_app_id:
                    return Response(
                        {"detail": "Meta OAuth token app_id did not match META_APP_ID."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                permissions = client.list_permissions(user_access_token=token.access_token)
                granted_permissions = sorted(
                    {
                        str(row.get("permission")).strip()
                        for row in permissions
                        if isinstance(row, dict)
                        and str(row.get("status", "")).strip().lower() == "granted"
                        and str(row.get("permission", "")).strip()
                    }
                )
                declined_permissions = sorted(
                    {
                        str(row.get("permission")).strip()
                        for row in permissions
                        if isinstance(row, dict)
                        and str(row.get("status", "")).strip().lower() == "declined"
                        and str(row.get("permission", "")).strip()
                    }
                )
                missing_required_permissions = _missing_required_permissions(granted_permissions)
                pages = client.list_pages(user_access_token=token.access_token)
                ad_accounts = client.list_ad_accounts(user_access_token=token.access_token)
                instagram_accounts = client.list_instagram_accounts(pages=pages)
        except MetaGraphConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except MetaGraphClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if not pages:
            return Response(
                {"detail": "No Facebook pages were returned for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expires_at: str | None = None
        if token.expires_in is not None:
            expires_at = (timezone.now() + timedelta(seconds=token.expires_in)).isoformat()

        selection_token = secrets.token_urlsafe(32)
        cache.set(
            f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}",
            {
                "tenant_id": str(request.user.tenant_id),
                "user_id": str(request.user.id),
                "user_access_token": token.access_token,
                "token_expires_at": expires_at,
                "pages": [page.as_public_dict() for page in pages],
                "ad_accounts": [account.as_public_dict() for account in ad_accounts],
                "instagram_accounts": [
                    instagram_account.as_public_dict() for instagram_account in instagram_accounts
                ],
                "granted_permissions": granted_permissions,
                "declined_permissions": declined_permissions,
                "missing_required_permissions": missing_required_permissions,
                "token_debug_valid": debug_valid,
            },
            timeout=META_OAUTH_SELECTION_TTL_SECONDS,
        )

        return Response(
            {
                "selection_token": selection_token,
                "expires_in_seconds": META_OAUTH_SELECTION_TTL_SECONDS,
                "pages": [page.as_public_dict() for page in pages],
                "ad_accounts": [account.as_public_dict() for account in ad_accounts],
                "instagram_accounts": [
                    instagram_account.as_public_dict() for instagram_account in instagram_accounts
                ],
                "granted_permissions": granted_permissions,
                "declined_permissions": declined_permissions,
                "missing_required_permissions": missing_required_permissions,
                "token_debug_valid": debug_valid,
                "oauth_connected_but_missing_permissions": bool(missing_required_permissions),
            }
        )


class MetaSystemTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = MetaSystemTokenSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        raw_account_id = str(serializer.validated_data["account_id"])
        account_id = _normalize_meta_account_id(raw_account_id)
        access_token = str(serializer.validated_data["access_token"])
        requested_expires_at = serializer.validated_data.get("expires_at")
        granted_scopes = _normalize_scopes(serializer.validated_data.get("granted_scopes", []))

        now = timezone.now()
        try:
            with MetaGraphClient.from_settings() as client:
                token_debug = client.debug_token(input_token=access_token)
        except MetaGraphConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except MetaGraphClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not bool(token_debug.get("is_valid")):
            return Response(
                {"detail": "Meta system-user token failed debug_token validation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        configured_app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        debug_app_id_raw = token_debug.get("app_id")
        debug_app_id = str(debug_app_id_raw).strip() if debug_app_id_raw is not None else ""
        if configured_app_id and debug_app_id and debug_app_id != configured_app_id:
            return Response(
                {"detail": "Meta token app_id did not match META_APP_ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expires_at = requested_expires_at
        expires_raw = token_debug.get("expires_at")
        if expires_at is None and isinstance(expires_raw, (int, float)) and int(expires_raw) > 0:
            expires_at = datetime.fromtimestamp(int(expires_raw), tz=dt_timezone.utc)

        issued_at = now
        issued_raw = token_debug.get("issued_at")
        if isinstance(issued_raw, (int, float)) and int(issued_raw) > 0:
            issued_at = datetime.fromtimestamp(int(issued_raw), tz=dt_timezone.utc)

        if not granted_scopes:
            granted_scopes = _normalize_scopes(token_debug.get("scopes"))
        token_status, token_status_reason = _token_status_for_expiry(expires_at=expires_at, now=now)

        with transaction.atomic():
            credential, _ = PlatformCredential.objects.select_for_update().get_or_create(
                tenant=request.user.tenant,
                provider=PlatformCredential.META,
                account_id=account_id,
                defaults={"expires_at": expires_at},
            )
            credential.expires_at = expires_at
            credential.auth_mode = PlatformCredential.AUTH_MODE_SYSTEM_USER
            credential.granted_scopes = granted_scopes
            credential.declined_scopes = []
            credential.issued_at = issued_at
            credential.last_validated_at = now
            credential.last_refreshed_at = now
            credential.token_status = token_status
            credential.token_status_reason = token_status_reason
            credential.mark_refresh_token_for_clear()
            credential.set_raw_tokens(access_token, None)
            credential.save()

        emit_observability_event(
            logger,
            "meta.system_token.connected",
            tenant_id=str(request.user.tenant_id),
            auth_mode=credential.auth_mode,
            account_id=credential.account_id,
        )

        return Response(
            {
                "credential": PlatformCredentialSerializer(credential).data,
                "token_debug_valid": True,
            },
            status=status.HTTP_201_CREATED,
        )


class MetaPageConnectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = MetaPageConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        selection_token = str(serializer.validated_data["selection_token"])
        cache_key = f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}"
        cached_payload = cache.get(cache_key)
        if not isinstance(cached_payload, dict):
            return Response(
                {"detail": "Meta page selection token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            cached_payload.get("tenant_id") != str(request.user.tenant_id)
            or cached_payload.get("user_id") != str(request.user.id)
        ):
            return Response(
                {"detail": "Meta page selection token does not match this tenant user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pages = cached_payload.get("pages")
        if not isinstance(pages, list):
            pages = []
        selected_page = next(
            (
                page
                for page in pages
                if isinstance(page, dict) and page.get("id") == serializer.validated_data["page_id"]
            ),
            None,
        )
        if selected_page is None:
            return Response(
                {"detail": "Selected Facebook page was not found in the OAuth result set."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_access_token = cached_payload.get("user_access_token")
        if not isinstance(user_access_token, str) or not user_access_token.strip():
            return Response(
                {"detail": "Meta OAuth token payload is missing an access token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        missing_required_permissions_raw = cached_payload.get("missing_required_permissions")
        missing_required_permissions = (
            [
                str(scope).strip()
                for scope in missing_required_permissions_raw
                if isinstance(scope, str) and scope.strip()
            ]
            if isinstance(missing_required_permissions_raw, list)
            else []
        )
        if missing_required_permissions:
            credential = (
                PlatformCredential.objects.filter(
                    tenant=request.user.tenant,
                    provider=PlatformCredential.META,
                )
                .order_by("-updated_at")
                .first()
            )
            if credential is not None:
                credential.granted_scopes = _normalize_scopes(cached_payload.get("granted_permissions"))
                credential.declined_scopes = _normalize_scopes(cached_payload.get("declined_permissions"))
                credential.last_validated_at = timezone.now()
                credential.token_status = PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED
                credential.token_status_reason = (
                    "Missing required Meta permissions: " + ", ".join(missing_required_permissions)
                )
                credential.save(
                    update_fields=[
                        "granted_scopes",
                        "declined_scopes",
                        "last_validated_at",
                        "token_status",
                        "token_status_reason",
                        "updated_at",
                    ]
                )
            return Response(
                {
                    "detail": "Meta OAuth is missing required permissions. Re-request permissions first.",
                    "missing_required_permissions": missing_required_permissions,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        selected_account: dict[str, Any] | None = None
        ad_account_input = (serializer.validated_data.get("ad_account_id") or "").strip()
        if not ad_account_input:
            return Response(
                {"detail": "A Meta ad account selection is required to provision Marketing API insights."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ad_accounts = cached_payload.get("ad_accounts")
        if ad_account_input and isinstance(ad_accounts, list):
            normalized_requested = _normalize_meta_account_id(ad_account_input)
            selected_account = next(
                (
                    account
                    for account in ad_accounts
                    if isinstance(account, dict)
                    and (
                        account.get("id") == ad_account_input
                        or account.get("account_id") == ad_account_input
                        or _normalize_meta_account_id(str(account.get("id", ""))) == normalized_requested
                        or _normalize_meta_account_id(str(account.get("account_id", ""))) == normalized_requested
                    )
                ),
                None,
            )
            if selected_account is None:
                return Response(
                    {"detail": "Selected ad account was not returned by Meta OAuth."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        selected_instagram_account: dict[str, Any] | None = None
        instagram_account_input = (serializer.validated_data.get("instagram_account_id") or "").strip()
        instagram_accounts = cached_payload.get("instagram_accounts")
        if instagram_account_input and isinstance(instagram_accounts, list):
            selected_instagram_account = next(
                (
                    account
                    for account in instagram_accounts
                    if isinstance(account, dict) and str(account.get("id", "")).strip() == instagram_account_input
                ),
                None,
            )
            if selected_instagram_account is None:
                return Response(
                    {"detail": "Selected Instagram account was not returned by Meta OAuth."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        account_id = selected_page["id"]
        if selected_account:
            account_raw = (
                str(selected_account.get("id"))
                if selected_account.get("id")
                else str(selected_account.get("account_id"))
            )
            account_id = _normalize_meta_account_id(account_raw)

        expires_at_raw = cached_payload.get("token_expires_at")
        expires_at = None
        if isinstance(expires_at_raw, str) and expires_at_raw.strip():
            try:
                expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
            except ValueError:
                expires_at = None
        now = timezone.now()
        token_status, token_status_reason = _token_status_for_expiry(expires_at=expires_at, now=now)
        granted_permissions = _normalize_scopes(cached_payload.get("granted_permissions"))
        declined_permissions = _normalize_scopes(cached_payload.get("declined_permissions"))

        with transaction.atomic():
            credential, _ = PlatformCredential.objects.select_for_update().get_or_create(
                tenant=request.user.tenant,
                provider=PlatformCredential.META,
                account_id=account_id,
                defaults={"expires_at": expires_at},
            )
            credential.expires_at = expires_at
            credential.auth_mode = PlatformCredential.AUTH_MODE_USER_OAUTH
            credential.granted_scopes = granted_permissions
            credential.declined_scopes = declined_permissions
            credential.issued_at = now
            credential.last_validated_at = now
            credential.last_refreshed_at = now
            credential.token_status = token_status
            credential.token_status_reason = token_status_reason
            credential.mark_refresh_token_for_clear()
            credential.set_raw_tokens(user_access_token, None)
            credential.save()

        cache.delete(cache_key)
        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="meta_oauth_connected",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": PlatformCredential.META,
                "page_id": selected_page.get("id"),
                "ad_account_id": account_id if selected_account else None,
                "instagram_account_id": (
                    str(selected_instagram_account.get("id")) if selected_instagram_account else None
                ),
                "granted_permissions": cached_payload.get("granted_permissions", []),
                "declined_permissions": cached_payload.get("declined_permissions", []),
            },
        )

        return Response(
            {
                "credential": PlatformCredentialSerializer(credential).data,
                "page": selected_page,
                "ad_account": selected_account,
                "instagram_account": selected_instagram_account,
                "granted_permissions": cached_payload.get("granted_permissions", []),
                "declined_permissions": cached_payload.get("declined_permissions", []),
                "missing_required_permissions": missing_required_permissions,
            },
            status=status.HTTP_201_CREATED,
        )


class MetaProvisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = MetaProvisionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        requested_account_id = (validated.get("external_account_id") or "").strip() or None
        credential = _resolve_meta_credential(request=request, external_account_id=requested_account_id)
        if credential is None:
            return Response(
                {"detail": "No Meta credential found for this tenant. Complete OAuth first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        workspace_id = validated.get("workspace_id") or getattr(settings, "AIRBYTE_DEFAULT_WORKSPACE_ID", None)
        destination_id = validated.get("destination_id") or getattr(settings, "AIRBYTE_DEFAULT_DESTINATION_ID", None)
        if _is_unset_or_placeholder(workspace_id):
            workspace_id = None
        if _is_unset_or_placeholder(destination_id):
            destination_id = None
        if not workspace_id or not destination_id:
            return Response(
                {
                    "detail": (
                        "workspace_id and destination_id are required unless "
                        "AIRBYTE_DEFAULT_WORKSPACE_ID and AIRBYTE_DEFAULT_DESTINATION_ID are configured."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        source_definition_id = _resolve_meta_source_definition_id(
            str(validated["source_definition_id"]) if validated.get("source_definition_id") else None
        )
        schedule_type = validated.get("schedule_type") or AirbyteConnection.SCHEDULE_CRON
        interval_minutes = validated.get("interval_minutes")
        cron_expression = (validated.get("cron_expression") or "").strip() or DEFAULT_CONNECTOR_CRON_EXPRESSION
        is_active = validated.get("is_active", True)
        connection_name = (validated.get("connection_name") or "").strip() or f"Meta Insights {credential.account_id}"
        numeric_account_id = _meta_numeric_account_id(credential.account_id)
        if not numeric_account_id.isdigit():
            return Response(
                {
                    "detail": (
                        "Stored Meta credential account_id must be an ad account ID. "
                        "Reconnect Meta and select a valid ad account."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_token = credential.decrypt_access_token()
        if not access_token:
            return Response(
                {"detail": "Stored Meta credential is missing an access token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        app_secret = (getattr(settings, "META_APP_SECRET", "") or "").strip()
        if not app_id or not app_secret:
            return Response(
                {"detail": "META_APP_ID and META_APP_SECRET are required for Meta provisioning."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        source_name = f"Meta Source {credential.account_id}"
        source_reused = False
        connection_reused = False
        modern_source_config = {
            "account_ids": [numeric_account_id],
            "credentials": {
                "auth_type": "Service",
                "access_token": access_token,
            },
            "start_date": "2024-01-01T00:00:00Z",
            "insights_lookback_window": 3,
            "fetch_thumbnail_images": False,
        }
        legacy_source_config = {
            "account_id": numeric_account_id,
            "access_token": access_token,
            "app_id": app_id,
            "app_secret": app_secret,
            "start_date": "2024-01-01T00:00:00Z",
            "insights_lookback_window": 3,
            "window_in_days": 3,
            "report_interval": "daily",
            "fetch_thumbnail_images": False,
            "custom_insights_fields": [
                "impressions",
                "clicks",
                "spend",
                "actions",
                "action_values",
            ],
        }
        source_config_candidates = [modern_source_config, legacy_source_config]
        try:
            with AirbyteClient.from_settings() as client:
                sources = client.list_sources(str(workspace_id))
                existing_source = next(
                    (
                        source
                        for source in sources
                        if source.get("name") == source_name
                        and source.get("sourceDefinitionId") == source_definition_id
                    ),
                    None,
                )
                source_id: str | None = None
                configured_catalog: dict[str, Any] | None = None
                last_schema_error: AirbyteClientError | None = None
                last_config_validation_error: str | None = None
                for source_config in source_config_candidates:
                    source: dict[str, Any] | None = None
                    try:
                        if existing_source:
                            source_reused = True
                            existing_source_id = existing_source.get("sourceId")
                            if not isinstance(existing_source_id, str) or not existing_source_id:
                                raise ValueError("Airbyte source list response missing sourceId.")
                            source = client.update_source(
                                {
                                    "sourceId": existing_source_id,
                                    "name": source_name,
                                    "connectionConfiguration": source_config,
                                }
                            )
                        else:
                            source = client.create_source(
                                {
                                    "name": source_name,
                                    "sourceDefinitionId": source_definition_id,
                                    "workspaceId": str(workspace_id),
                                    "connectionConfiguration": source_config,
                                }
                            )
                    except AirbyteClientError as exc:
                        if _is_airbyte_source_config_schema_error(exc):
                            last_schema_error = exc
                            continue
                        raise

                    candidate_source_id = source.get("sourceId") if isinstance(source, dict) else None
                    if not isinstance(candidate_source_id, str) or not candidate_source_id:
                        raise ValueError("Airbyte source create/list response missing sourceId.")

                    check_payload = client.check_source(candidate_source_id)
                    check_job = check_payload.get("jobInfo") if isinstance(check_payload, dict) else None
                    check_status = (
                        str(check_job.get("status", "")).lower()
                        if isinstance(check_job, dict)
                        else str(check_payload.get("status", "")).lower()
                    )
                    if check_status and check_status not in {"succeeded", "success"}:
                        check_message_parts = []
                        if isinstance(check_payload, dict):
                            for key in ("message", "status"):
                                value = check_payload.get(key)
                                if isinstance(value, str) and value.strip():
                                    check_message_parts.append(value.strip())
                            failure_reason = check_payload.get("failureReason")
                            if isinstance(failure_reason, dict):
                                for key in ("externalMessage", "internalMessage"):
                                    value = failure_reason.get(key)
                                    if isinstance(value, str) and value.strip():
                                        check_message_parts.append(value.strip())
                        check_message = " | ".join(check_message_parts)
                        if _looks_like_airbyte_source_config_error(check_message):
                            last_config_validation_error = check_message or f"status={check_status}"
                            continue
                        raise ValueError(f"Airbyte source check failed (status={check_status}).")

                    discovered = client.discover_source_schema(candidate_source_id)
                    catalog = discovered.get("catalog") if isinstance(discovered, dict) else None
                    if not isinstance(catalog, dict):
                        discover_message_parts = []
                        if isinstance(discovered, dict):
                            job_info = discovered.get("jobInfo")
                            if isinstance(job_info, dict):
                                failure_reason = job_info.get("failureReason")
                                if isinstance(failure_reason, dict):
                                    for key in ("externalMessage", "internalMessage"):
                                        value = failure_reason.get(key)
                                        if isinstance(value, str) and value.strip():
                                            discover_message_parts.append(value.strip())
                            message = discovered.get("message")
                            if isinstance(message, str) and message.strip():
                                discover_message_parts.append(message.strip())
                        discover_message = " | ".join(discover_message_parts)
                        if _looks_like_airbyte_source_config_error(discover_message):
                            last_config_validation_error = discover_message or "discover schema failed validation"
                            continue
                        raise ValueError("Airbyte discover schema response missing catalog.")

                    source_id = candidate_source_id
                    configured_catalog = _configured_catalog(catalog)
                    break

                if source_id is None or configured_catalog is None:
                    if last_schema_error is not None:
                        raise ValueError(
                            "Meta source configuration did not match connector spec in Airbyte."
                        ) from last_schema_error
                    if last_config_validation_error:
                        raise ValueError(
                            "Meta source configuration failed Airbyte connector validation. "
                            "Try reconnecting Meta and re-running provisioning."
                        )
                    raise ValueError("Unable to create or update Meta source in Airbyte.")

                connections = client.list_connections(str(workspace_id))
                existing_connection = _find_by_name(connections, connection_name)
                if existing_connection:
                    connection_reused = True
                    existing_connection_id = existing_connection.get("connectionId")
                    if not isinstance(existing_connection_id, str) or not existing_connection_id:
                        raise ValueError("Airbyte connection list response missing connectionId.")
                    connection_payload = client.update_connection(
                        {
                            "connectionId": existing_connection_id,
                            "name": connection_name,
                            "sourceId": source_id,
                            "destinationId": str(
                                existing_connection.get("destinationId") or destination_id
                            ),
                            "workspaceId": str(workspace_id),
                            "status": "active" if is_active else "inactive",
                            "syncCatalog": configured_catalog,
                            "namespaceDefinition": "destination",
                            "operationIds": existing_connection.get("operationIds") or [],
                            **_schedule_payload(
                                schedule_type=schedule_type,
                                interval_minutes=interval_minutes,
                                cron_expression=cron_expression,
                            ),
                        }
                    )
                else:
                    connection_payload = client.create_connection(
                        {
                            "name": connection_name,
                            "sourceId": source_id,
                            "destinationId": str(destination_id),
                            "workspaceId": str(workspace_id),
                            "status": "active" if is_active else "inactive",
                            "syncCatalog": configured_catalog,
                            "namespaceDefinition": "destination",
                            "operationIds": [],
                            **_schedule_payload(
                                schedule_type=schedule_type,
                                interval_minutes=interval_minutes,
                                cron_expression=cron_expression,
                            ),
                        }
                    )
        except AirbyteClientConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except AirbyteClientError as exc:
            return _airbyte_exception_response(exc)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        connection_id = connection_payload.get("connectionId")
        if not isinstance(connection_id, str) or not connection_id:
            return Response(
                {"detail": "Airbyte connection create/list response missing connectionId."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            parsed_connection_id = uuid.UUID(connection_id)
        except ValueError:
            return Response(
                {"detail": "Airbyte returned an invalid connectionId."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        connection_record, _ = AirbyteConnection.objects.update_or_create(
            tenant=request.user.tenant,
            connection_id=parsed_connection_id,
            defaults={
                "name": connection_name,
                "workspace_id": workspace_id,
                "provider": PlatformCredential.META,
                "schedule_type": schedule_type,
                "interval_minutes": interval_minutes if schedule_type == AirbyteConnection.SCHEDULE_INTERVAL else None,
                "cron_expression": cron_expression if schedule_type == AirbyteConnection.SCHEDULE_CRON else "",
                "is_active": bool(is_active),
            },
        )
        window_start, window_end = _default_meta_window(now=timezone.now())
        _upsert_meta_account_sync_state(
            tenant=request.user.tenant,
            account_id=credential.account_id,
            connection=connection_record,
            window_start=window_start,
            window_end=window_end,
        )

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="meta_airbyte_provisioned",
            resource_type="airbyte_connection",
            resource_id=connection_record.id,
            metadata={
                "connection_id": connection_id,
                "source_id": source_id,
                "provider": PlatformCredential.META,
                "source_reused": source_reused,
                "connection_reused": connection_reused,
            },
        )

        return Response(
            {
                "provider": "meta_ads",
                "credential": PlatformCredentialSerializer(credential).data,
                "connection": AirbyteConnectionSerializer(connection_record).data,
                "source": {
                    "source_id": source_id,
                    "name": source_name,
                },
                "source_reused": source_reused,
                "connection_reused": connection_reused,
            },
            status=status.HTTP_201_CREATED,
        )


class MetaSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        connection = (
            AirbyteConnection.objects.filter(tenant_id=request.user.tenant_id, provider=PlatformCredential.META)
            .order_by("-updated_at")
            .first()
        )
        if connection is None:
            return Response(
                {"detail": "No Meta Airbyte connection found for this tenant."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with AirbyteClient.from_settings() as client:
                payload = client.trigger_sync(str(connection.connection_id))
        except AirbyteClientConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except AirbyteClientError as exc:
            return _airbyte_exception_response(exc)

        job_id = extract_job_id(payload)
        sync_started_at = timezone.now()
        if job_id is not None:
            connection.record_sync(job_id=job_id, job_status="pending", job_created_at=sync_started_at)

        account_id = _resolve_meta_account_for_connection(connection=connection)
        if account_id:
            window_start, window_end = _default_meta_window(now=sync_started_at)
            _upsert_meta_account_sync_state(
                tenant=connection.tenant,
                account_id=account_id,
                connection=connection,
                job_id=str(job_id) if job_id is not None else None,
                job_status="pending",
                sync_started_at=sync_started_at,
                window_start=window_start,
                window_end=window_end,
            )

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="meta_sync_triggered",
            resource_type="airbyte_connection",
            resource_id=connection.id,
            metadata={
                "provider": PlatformCredential.META,
                "connection_id": str(connection.connection_id),
                "job_id": str(job_id) if job_id is not None else None,
            },
        )

        return Response(
            {
                "provider": "meta_ads",
                "connection_id": str(connection.connection_id),
                "job_id": str(job_id) if job_id is not None else None,
            },
            status=status.HTTP_202_ACCEPTED if job_id is not None else status.HTTP_200_OK,
        )


class MetaLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        queryset = PlatformCredential.objects.filter(
            tenant_id=request.user.tenant_id,
            provider=PlatformCredential.META,
        )
        existing_ids = [str(credential_id) for credential_id in queryset.values_list("id", flat=True)]
        deleted_count, _ = queryset.delete()

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="meta_oauth_disconnected",
            resource_type="platform_credential",
            resource_id=existing_ids[0] if existing_ids else None,
            metadata={
                "provider": PlatformCredential.META,
                "deleted_credentials": deleted_count,
            },
        )

        return Response(
            {
                "provider": "meta_ads",
                "disconnected": bool(deleted_count),
                "deleted_credentials": deleted_count,
            }
        )


class MetaSyncStateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        queryset = MetaAccountSyncState.objects.filter(
            tenant_id=request.user.tenant_id
        ).order_by("account_id")
        serializer = MetaAccountSyncStateSerializer(queryset, many=True)
        return Response(
            {
                "count": len(serializer.data),
                "results": serializer.data,
            }
        )


class SocialConnectionStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        try:
            return self._get(request, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = schema_out_of_date_response(
                exc=exc,
                logger=logger,
                endpoint="integrations.social_connection_status",
                tenant_id=getattr(request.user, "tenant_id", None),
            )
            if schema_response is not None:
                return schema_response
            raise

    def _get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        now = timezone.now()
        tenant_id = request.user.tenant_id

        meta_credential = (
            PlatformCredential.objects.filter(
                tenant_id=tenant_id,
                provider=PlatformCredential.META,
            )
            .order_by("-updated_at")
            .first()
        )
        meta_connections = list(
            AirbyteConnection.objects.filter(
                tenant_id=tenant_id,
                provider=PlatformCredential.META,
            ).order_by("-updated_at")
        )
        preferred_connection = _select_preferred_meta_connection(meta_connections, now)
        meta_sync_state = None
        if meta_credential is not None:
            meta_sync_state = (
                MetaAccountSyncState.objects.filter(
                    tenant_id=tenant_id,
                    account_id=_normalize_meta_account_id(meta_credential.account_id),
                )
                .order_by("-updated_at")
                .first()
            )
        if meta_sync_state is None and preferred_connection is not None:
            meta_sync_state = (
                MetaAccountSyncState.objects.filter(
                    tenant_id=tenant_id,
                    connection=preferred_connection,
                )
                .order_by("-updated_at")
                .first()
            )

        app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        app_secret = (getattr(settings, "META_APP_SECRET", "") or "").strip()
        frontend_base_url = (getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
        login_configuration_id = _meta_login_configuration_id()
        login_configuration_required = _meta_login_configuration_required()
        redirect_uri_configured = bool(
            (getattr(settings, "META_OAUTH_REDIRECT_URI", "") or "").strip()
            or frontend_base_url
        )
        workspace_id = (getattr(settings, "AIRBYTE_DEFAULT_WORKSPACE_ID", "") or "").strip()
        destination_id = (getattr(settings, "AIRBYTE_DEFAULT_DESTINATION_ID", "") or "").strip()
        login_configuration_ready = bool(login_configuration_id) or not login_configuration_required
        oauth_ready = bool(app_id and app_secret and redirect_uri_configured and login_configuration_ready)
        provisioning_defaults_ready = bool(workspace_id and destination_id)

        meta_status, meta_reason, meta_actions = _resolve_meta_status(
            credential=meta_credential,
            connection=preferred_connection,
            now=now,
            oauth_ready=oauth_ready,
            provisioning_defaults_ready=provisioning_defaults_ready,
        )

        latest_meta_oauth_audit = (
            AuditLog.objects.filter(
                tenant_id=tenant_id,
                action="meta_oauth_connected",
                resource_type="platform_credential",
                resource_id=str(meta_credential.id) if meta_credential else None,
            )
            .order_by("-created_at")
            .first()
        )
        latest_meta_metadata = latest_meta_oauth_audit.metadata if latest_meta_oauth_audit else {}
        instagram_linked_id = None
        if isinstance(latest_meta_metadata, dict):
            instagram_value = latest_meta_metadata.get("instagram_account_id")
            if isinstance(instagram_value, str) and instagram_value.strip():
                instagram_linked_id = instagram_value.strip()

        if meta_credential is None:
            instagram_status = "not_connected"
            instagram_reason = {
                "code": "missing_meta_credential",
                "message": "Connect Meta first to enable Instagram business linking.",
            }
            instagram_actions = ["connect_oauth"]
        elif not instagram_linked_id:
            instagram_status = "started_not_complete"
            instagram_reason = {
                "code": "instagram_not_linked",
                "message": "Meta is connected, but no Instagram business account is linked yet.",
            }
            instagram_actions = ["select_assets"]
        elif meta_status == "active":
            instagram_status = "active"
            instagram_reason = {
                "code": "instagram_active_via_meta",
                "message": "Instagram is linked and Meta sync is active.",
            }
            instagram_actions = ["view"]
        else:
            instagram_status = "complete"
            instagram_reason = {
                "code": "instagram_linked_waiting_meta_active",
                "message": "Instagram is linked and will report as active once Meta sync is active.",
            }
            instagram_actions = ["sync_now", "view"]

        payload = {
            "generated_at": now,
            "platforms": [
                {
                    "platform": "meta",
                    "display_name": "Meta (Facebook)",
                    "status": meta_status,
                    "reason": meta_reason,
                    "last_checked_at": now,
                    "last_synced_at": preferred_connection.last_synced_at if preferred_connection else None,
                    "actions": meta_actions,
                    "metadata": {
                        "has_credential": bool(meta_credential),
                        "credential_account_id": meta_credential.account_id if meta_credential else None,
                        "has_valid_ad_account": bool(
                            meta_credential and _is_meta_ad_account_id(meta_credential.account_id)
                        ),
                        "has_connection": bool(preferred_connection),
                        "connection_id": str(preferred_connection.id) if preferred_connection else None,
                        "connection_active": bool(preferred_connection and preferred_connection.is_active),
                        "sync_state_last_job_status": (
                            meta_sync_state.last_job_status if meta_sync_state else None
                        ),
                        "sync_state_last_job_error": (
                            meta_sync_state.last_job_error if meta_sync_state else None
                        ),
                        "sync_state_last_success_at": (
                            meta_sync_state.last_success_at.isoformat()
                            if meta_sync_state and meta_sync_state.last_success_at
                            else None
                        ),
                        "sync_state_last_sync_completed_at": (
                            meta_sync_state.last_sync_completed_at.isoformat()
                            if meta_sync_state and meta_sync_state.last_sync_completed_at
                            else None
                        ),
                        "sync_state_last_window_start": (
                            meta_sync_state.last_window_start.isoformat()
                            if meta_sync_state and meta_sync_state.last_window_start
                            else None
                        ),
                        "sync_state_last_window_end": (
                            meta_sync_state.last_window_end.isoformat()
                            if meta_sync_state and meta_sync_state.last_window_end
                            else None
                        ),
                        "sync_state_updated_at": (
                            meta_sync_state.updated_at.isoformat()
                            if meta_sync_state and meta_sync_state.updated_at
                            else None
                        ),
                    },
                },
                {
                    "platform": "instagram",
                    "display_name": "Instagram (Business)",
                    "status": instagram_status,
                    "reason": instagram_reason,
                    "last_checked_at": now,
                    "last_synced_at": preferred_connection.last_synced_at if preferred_connection else None,
                    "actions": instagram_actions,
                    "metadata": {
                        "linked_instagram_account_id": instagram_linked_id,
                        "meta_status": meta_status,
                    },
                },
            ],
        }
        serializer = SocialConnectionStatusResponseSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


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


class AirbyteConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = AirbyteConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return AirbyteConnection.objects.none()
        return AirbyteConnection.objects.filter(tenant_id=user.tenant_id).order_by(
            "name"
        )

    def perform_create(self, serializer):
        connection = serializer.save(tenant=self.request.user.tenant)
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=connection.tenant,
            user=actor,
            action="airbyte_connection_created",
            resource_type="airbyte_connection",
            resource_id=connection.id,
            metadata={
                "connection_id": str(connection.connection_id),
                "provider": connection.provider,
                "schedule_type": connection.schedule_type,
            },
        )

    def perform_update(self, serializer):
        connection = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=connection.tenant,
            user=actor,
            action="airbyte_connection_updated",
            resource_type="airbyte_connection",
            resource_id=connection.id,
            metadata={
                "connection_id": str(connection.connection_id),
                "provider": connection.provider,
                "schedule_type": connection.schedule_type,
                "is_active": connection.is_active,
            },
        )

    def perform_destroy(self, instance):
        connection_id = str(instance.connection_id)
        provider = instance.provider
        schedule_type = instance.schedule_type
        tenant = instance.tenant
        actor = self.request.user if self.request.user.is_authenticated else None
        super().perform_destroy(instance)
        log_audit_event(
            tenant=tenant,
            user=actor,
            action="airbyte_connection_deleted",
            resource_type="airbyte_connection",
            resource_id=str(instance.id),
            metadata={
                "connection_id": connection_id,
                "provider": provider,
                "schedule_type": schedule_type,
            },
        )

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        connections = list(self.get_queryset())
        now = timezone.now()

        total = len(connections)
        active = sum(1 for connection in connections if connection.is_active)
        inactive = total - active
        due = sum(1 for connection in connections if connection.should_trigger(now))

        by_provider: Dict[str, Dict[str, int]] = {}
        for connection in connections:
            provider_key = connection.provider or "UNKNOWN"
            entry = by_provider.setdefault(
                provider_key, {"total": 0, "active": 0, "due": 0}
            )
            entry["total"] += 1
            if connection.is_active:
                entry["active"] += 1
            if connection.should_trigger(now):
                entry["due"] += 1

        sync_status = (
            TenantAirbyteSyncStatus.objects.select_related("last_connection")
            .filter(tenant_id=request.user.tenant_id)
            .first()
        )

        payload = {
            "total": total,
            "active": active,
            "inactive": inactive,
            "due": due,
            "by_provider": by_provider,
            "latest_sync": TenantAirbyteSyncStatusSerializer(sync_status).data
            if sync_status
            else None,
        }

        actor = request.user if request.user.is_authenticated else None
        log_audit_event(
            tenant=request.user.tenant,
            user=actor,
            action="airbyte_connection_summary_viewed",
            resource_type="airbyte_connection",
            resource_id="summary",
            metadata={
                "total": total,
                "active": active,
                "inactive": inactive,
                "due": due,
            },
        )

        return Response(payload)

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
            if connection.provider == PlatformCredential.META:
                account_id = _resolve_meta_account_for_connection(connection=connection)
                if account_id:
                    started_at = snapshot.started_at or created_at
                    window_start, window_end = _default_meta_window(now=started_at)
                    _upsert_meta_account_sync_state(
                        tenant=connection.tenant,
                        account_id=account_id,
                        connection=connection,
                        job_id=update.job_id,
                        job_status=job_status,
                        job_error=error_message or "",
                        sync_started_at=started_at,
                        sync_completed_at=completed_at,
                        window_start=window_start,
                        window_end=window_end,
                    )

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
    schema = AutoSchema(operation_id_base="AdminAlertRuleDefinition")

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
