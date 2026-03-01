from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import secrets
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.audit import log_audit_event
from core.frontend_runtime import (
    build_runtime_context,
    extract_dataset_source,
    extract_runtime_client_origin,
    resolve_frontend_redirect_uri,
)
from core.observability import emit_observability_event
from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from integrations.google_ads.gaql_templates import get_gaql_template
from integrations.google_ads.catalog import load_reference_catalog
from integrations.google_ads.field_reference import load_fields_reference
from integrations.google_ads.query_reference import load_query_reference
from integrations.google_ads_serializers import (
    GoogleAdsOAuthExchangeSerializer,
    GoogleAdsOAuthStartSerializer,
    GoogleAdsProvisionSerializer,
    GoogleAdsStatusResponseSerializer,
)
from integrations.models import AirbyteConnection, GoogleAdsSyncState, PlatformCredential
from integrations.serializers import AirbyteConnectionSerializer, PlatformCredentialSerializer
from integrations.tasks import sync_google_ads_sdk_incremental

GOOGLE_OAUTH_STATE_SALT = "integrations.google_ads.oauth.state"
GOOGLE_OAUTH_STATE_MAX_AGE_SECONDS = 600
GOOGLE_STATUS_STALE_THRESHOLD_MINUTES = 60
GOOGLE_SUCCESS_STATUSES = {"succeeded", "success", "completed"}
DEFAULT_GOOGLE_SOURCE_DEFINITION_ID = "0b29e8f7-f64c-4a24-9e97-07c4603f8c04"
DEFAULT_GOOGLE_CONNECTOR_CRON_EXPRESSION = "0 6-22 * * *"
DEFAULT_GOOGLE_CONNECTOR_TIMEZONE = "America/Jamaica"
DEFAULT_GOOGLE_ADS_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

logger = logging.getLogger(__name__)


def _is_unset_or_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if not normalized:
        return True
    lowered = normalized.lower()
    return lowered.startswith("replace_") or "placeholder" in lowered or lowered in {
        "replace-me",
        "changeme",
    }


def _resolve_google_redirect_uri(
    *,
    request=None,  # noqa: ANN001 - DRF request
    payload: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    runtime_context_origin = extract_runtime_client_origin(request=request, payload=payload)
    redirect_uri, resolution, redirect_source = resolve_frontend_redirect_uri(
        path="/dashboards/data-sources",
        explicit_redirect_uri=(getattr(settings, "GOOGLE_ADS_OAUTH_REDIRECT_URI", "") or "").strip(),
        request=request,
        runtime_context_origin=runtime_context_origin,
        missing_message=(
            "GOOGLE_ADS_OAUTH_REDIRECT_URI or FRONTEND_BASE_URL must be configured for Google OAuth."
        ),
    )
    dataset_source = extract_dataset_source(request=request, payload=payload)
    return (
        redirect_uri,
        build_runtime_context(
            redirect_uri=redirect_uri,
            redirect_source=redirect_source,
            resolution=resolution,
            dataset_source=dataset_source,
        ),
    )


def _google_redirect_uri(
    *,
    request=None,  # noqa: ANN001 - DRF request
    payload: dict[str, Any] | None = None,
) -> str:
    redirect_uri, _ = _resolve_google_redirect_uri(request=request, payload=payload)
    return redirect_uri


def _google_oauth_scopes() -> list[str]:
    configured = getattr(settings, "GOOGLE_ADS_OAUTH_SCOPES", DEFAULT_GOOGLE_ADS_OAUTH_SCOPES)
    if not isinstance(configured, list):
        return list(DEFAULT_GOOGLE_ADS_OAUTH_SCOPES)
    resolved: list[str] = []
    seen: set[str] = set()
    for scope in configured:
        if not isinstance(scope, str):
            continue
        candidate = scope.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(candidate)
    return resolved or list(DEFAULT_GOOGLE_ADS_OAUTH_SCOPES)


def _google_state_payload(*, request) -> dict[str, str]:
    return {
        "tenant_id": str(request.user.tenant_id),
        "user_id": str(request.user.id),
        "nonce": secrets.token_urlsafe(24),
        "flow": "google_ads",
    }


def _sign_google_state(*, request) -> str:
    return signing.dumps(_google_state_payload(request=request), salt=GOOGLE_OAUTH_STATE_SALT)


def _validate_google_state(*, request, state: str) -> tuple[dict[str, Any], Response | None]:
    try:
        payload = signing.loads(
            state,
            salt=GOOGLE_OAUTH_STATE_SALT,
            max_age=GOOGLE_OAUTH_STATE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired:
        return {}, Response(
            {"detail": "Google OAuth state expired. Restart the connect flow."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except signing.BadSignature:
        return {}, Response(
            {"detail": "Google OAuth state is invalid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if payload.get("user_id") != str(request.user.id) or payload.get("tenant_id") != str(request.user.tenant_id):
        return {}, Response(
            {"detail": "Google OAuth state does not match the authenticated tenant user."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return payload, None


def _normalize_google_customer_id(raw_value: str) -> str:
    cleaned = "".join(ch for ch in raw_value if ch.isdigit())
    return cleaned


def _resolve_google_source_definition_id(requested: str | None) -> str:
    if requested:
        return requested
    configured = (getattr(settings, "AIRBYTE_SOURCE_DEFINITION_GOOGLE", "") or "").strip()
    if configured:
        return configured
    return DEFAULT_GOOGLE_SOURCE_DEFINITION_ID


def _resolve_google_credential(*, request, external_account_id: str | None) -> PlatformCredential | None:
    queryset = PlatformCredential.objects.filter(tenant_id=request.user.tenant_id, provider=PlatformCredential.GOOGLE)
    if external_account_id:
        normalized = _normalize_google_customer_id(external_account_id)
        queryset = queryset.filter(account_id__in={external_account_id, normalized})
    return queryset.order_by("-updated_at").first()


def _resolve_google_sync_state(
    *,
    tenant,
    account_id: str,
) -> GoogleAdsSyncState:
    desired_default = (getattr(settings, "GOOGLE_ADS_SYNC_ENGINE_DEFAULT", "sdk") or "sdk").strip().lower()
    if desired_default not in {GoogleAdsSyncState.ENGINE_SDK, GoogleAdsSyncState.ENGINE_AIRBYTE}:
        desired_default = GoogleAdsSyncState.ENGINE_SDK
    sync_state, _ = GoogleAdsSyncState.all_objects.get_or_create(
        tenant=tenant,
        account_id=account_id,
        defaults={
            "desired_engine": desired_default,
            "effective_engine": desired_default,
        },
    )
    return sync_state


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
                    cron_expression or DEFAULT_GOOGLE_CONNECTOR_CRON_EXPRESSION
                ),
                "cronTimeZone": DEFAULT_GOOGLE_CONNECTOR_TIMEZONE,
            }
        },
    }


def _configured_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    raw_streams = catalog.get("streams") or []
    configured_streams: list[dict[str, Any]] = []
    for raw in raw_streams:
        if not isinstance(raw, dict):
            continue
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


def _airbyte_exception_response(exc: AirbyteClientError) -> Response:
    status_code = (
        status.HTTP_504_GATEWAY_TIMEOUT
        if isinstance(exc.__cause__, httpx.TimeoutException)
        else status.HTTP_502_BAD_GATEWAY
    )
    return Response({"detail": str(exc)}, status=status_code)


def _is_connection_active(connection: AirbyteConnection | None, now) -> bool:
    if connection is None or connection.is_active is False:
        return False
    if connection.last_job_error:
        return False
    if (connection.last_job_status or "").lower() not in GOOGLE_SUCCESS_STATUSES:
        return False
    if not connection.last_synced_at:
        return False
    return now - connection.last_synced_at <= timedelta(minutes=GOOGLE_STATUS_STALE_THRESHOLD_MINUTES)


def _resolve_google_status(
    *,
    credential: PlatformCredential | None,
    connection: AirbyteConnection | None,
    sync_state: GoogleAdsSyncState | None,
    oauth_ready: bool,
    provisioning_defaults_ready: bool,
    now: datetime,
) -> tuple[str, dict[str, str], list[str]]:
    if credential is None:
        return (
            "not_connected",
            {
                "code": "missing_google_credential",
                "message": "Google Ads OAuth has not been connected for this tenant.",
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
                "message": credential.token_status_reason or "Google Ads credential needs re-authorization.",
            },
            ["connect_oauth"],
        )

    if not oauth_ready:
        return (
            "started_not_complete",
            {
                "code": "oauth_not_ready",
                "message": "Google OAuth configuration is incomplete.",
            },
            ["connect_oauth"],
        )

    if sync_state and sync_state.effective_engine == GoogleAdsSyncState.ENGINE_SDK:
        if sync_state.fallback_active:
            return (
                "complete",
                {
                    "code": "sdk_fallback_active",
                    "message": "SDK fallback to Airbyte is active after recent validation failures.",
                },
                ["sync_now", "view"],
            )
        if sync_state.last_sync_success_at and now - sync_state.last_sync_success_at <= timedelta(
            minutes=GOOGLE_STATUS_STALE_THRESHOLD_MINUTES
        ):
            return (
                "active",
                {
                    "code": "active_sync_sdk",
                    "message": "Google Ads SDK sync is active and recently completed.",
                },
                ["sync_now", "view"],
            )
        return (
            "complete",
            {
                "code": "awaiting_recent_successful_sync_sdk",
                "message": "Google Ads SDK is configured, waiting for a recent successful sync.",
            },
            ["sync_now", "view"],
        )

    if not provisioning_defaults_ready or connection is None:
        return (
            "started_not_complete",
            {
                "code": "provisioning_incomplete",
                "message": "Google Ads is connected but Airbyte provisioning is incomplete.",
            },
            ["provision"],
        )

    if _is_connection_active(connection, now):
        return (
            "active",
            {
                "code": "active_sync",
                "message": "Google Ads connection is active and recently synced.",
            },
            ["sync_now", "view"],
        )

    if connection.is_active is False:
        return (
            "complete",
            {
                "code": "connection_paused",
                "message": "Google Ads setup is complete, but sync is paused.",
            },
            ["provision", "view"],
        )

    return (
        "complete",
        {
            "code": "awaiting_recent_successful_sync",
            "message": "Google Ads setup is complete, waiting for a recent successful sync.",
        },
        ["sync_now", "view"],
    )


def _runtime_window_query() -> str:
    template = get_gaql_template("ad_group_ad_daily_performance").query
    return (
        template.replace("'{start_date}'", "'{{ runtime_from_date }}'")
        .replace("'{end_date}'", "'{{ runtime_to_date }}'")
    )


class GoogleAdsSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        client_id = (getattr(settings, "GOOGLE_ADS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", "") or "").strip()
        developer_token = (getattr(settings, "GOOGLE_ADS_DEVELOPER_TOKEN", "") or "").strip()
        resolved_redirect_uri = None
        runtime_context = None
        try:
            resolved_redirect_uri, runtime_context = _resolve_google_redirect_uri(
                request=request,
                payload=request.GET,
            )
            redirect_uri_configured = True
        except ValueError:
            redirect_uri_configured = False
        workspace_id_raw = (getattr(settings, "AIRBYTE_DEFAULT_WORKSPACE_ID", "") or "").strip()
        destination_id_raw = (getattr(settings, "AIRBYTE_DEFAULT_DESTINATION_ID", "") or "").strip()
        workspace_id = "" if _is_unset_or_placeholder(workspace_id_raw) else workspace_id_raw
        destination_id = "" if _is_unset_or_placeholder(destination_id_raw) else destination_id_raw
        source_definition_id = _resolve_google_source_definition_id(None)
        source_definition_configured = bool(
            (getattr(settings, "AIRBYTE_SOURCE_DEFINITION_GOOGLE", "") or "").strip()
        )

        ready_for_oauth = bool(client_id and client_secret and redirect_uri_configured)
        ready_for_provisioning_defaults = bool(workspace_id and destination_id)
        checks = [
            {
                "key": "google_oauth_credentials",
                "label": "Google OAuth client ID/secret configured",
                "ok": bool(client_id and client_secret),
                "env_vars": ["GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET"],
            },
            {
                "key": "google_oauth_redirect_uri",
                "label": "Google OAuth redirect configured",
                "ok": redirect_uri_configured,
                "env_vars": ["GOOGLE_ADS_OAUTH_REDIRECT_URI", "FRONTEND_BASE_URL"],
            },
            {
                "key": "google_ads_developer_token",
                "label": "Google Ads developer token configured",
                "ok": bool(developer_token),
                "env_vars": ["GOOGLE_ADS_DEVELOPER_TOKEN"],
            },
            {
                "key": "airbyte_workspace_default",
                "label": "Default Airbyte workspace configured",
                "ok": bool(workspace_id),
                "env_vars": ["AIRBYTE_DEFAULT_WORKSPACE_ID"],
            },
            {
                "key": "airbyte_destination_default",
                "label": "Default Airbyte destination configured",
                "ok": bool(destination_id),
                "env_vars": ["AIRBYTE_DEFAULT_DESTINATION_ID"],
            },
            {
                "key": "airbyte_source_definition_google",
                "label": "Google Ads source definition set",
                "ok": source_definition_configured,
                "using_fallback_default": not source_definition_configured,
                "env_vars": ["AIRBYTE_SOURCE_DEFINITION_GOOGLE"],
            },
        ]

        return Response(
            {
                "provider": "google_ads",
                "ready_for_oauth": ready_for_oauth,
                "ready_for_provisioning_defaults": ready_for_provisioning_defaults,
                "checks": checks,
                "oauth_scopes": _google_oauth_scopes(),
                "redirect_uri": resolved_redirect_uri,
                "source_definition_id": source_definition_id,
                "runtime_context": runtime_context,
            }
        )


class GoogleAdsOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = GoogleAdsOAuthStartSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        client_id = (getattr(settings, "GOOGLE_ADS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", "") or "").strip()
        if not client_id or not client_secret:
            return Response(
                {"detail": "GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET are required."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            redirect_uri = _google_redirect_uri(request=request, payload=serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        signed_state = _sign_google_state(request=request)
        prompt = serializer.validated_data.get("prompt") or "consent"
        query_payload = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(_google_oauth_scopes()),
            "state": signed_state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": prompt,
        }
        authorize_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(query_payload)}"
        return Response(
            {
                "authorize_url": authorize_url,
                "state": signed_state,
                "redirect_uri": redirect_uri,
                "oauth_scopes": _google_oauth_scopes(),
            }
        )


class GoogleAdsOAuthExchangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = GoogleAdsOAuthExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        _, state_error = _validate_google_state(request=request, state=str(serializer.validated_data["state"]))
        if state_error is not None:
            return state_error

        client_id = (getattr(settings, "GOOGLE_ADS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", "") or "").strip()
        if not client_id or not client_secret:
            return Response(
                {"detail": "GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET are required."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        customer_id = _normalize_google_customer_id(str(serializer.validated_data["customer_id"]))
        if not customer_id:
            return Response(
                {"detail": "customer_id must contain digits."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            redirect_uri = _google_redirect_uri(request=request, payload=serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        token_payload = {
            "code": str(serializer.validated_data["code"]),
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            token_response = httpx.post(
                "https://oauth2.googleapis.com/token",
                data=token_payload,
                timeout=30.0,
            )
            token_response.raise_for_status()
        except httpx.HTTPError as exc:
            return Response(
                {"detail": f"Google OAuth token exchange failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payload = token_response.json()
        access_token = str(payload.get("access_token") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()
        if not access_token:
            return Response(
                {"detail": "Google OAuth token exchange response was missing access_token."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        expires_in = payload.get("expires_in")
        expires_at = None
        if isinstance(expires_in, (int, float)) and int(expires_in) > 0:
            expires_at = timezone.now() + timedelta(seconds=int(expires_in))
        scope_raw = str(payload.get("scope") or "").strip()
        granted_scopes = sorted({scope for scope in scope_raw.split(" ") if scope})
        now = timezone.now()
        token_status, token_status_reason = _token_status_for_expiry(expires_at=expires_at, now=now)

        with transaction.atomic():
            credential, _ = PlatformCredential.objects.select_for_update().get_or_create(
                tenant=request.user.tenant,
                provider=PlatformCredential.GOOGLE,
                account_id=customer_id,
                defaults={"expires_at": expires_at},
            )
            credential.expires_at = expires_at
            credential.auth_mode = PlatformCredential.AUTH_MODE_USER_OAUTH
            credential.granted_scopes = granted_scopes
            credential.declined_scopes = []
            credential.issued_at = now
            credential.last_validated_at = now
            credential.last_refreshed_at = now
            credential.token_status = token_status
            credential.token_status_reason = token_status_reason
            credential.set_raw_tokens(access_token, refresh_token or None)
            credential.save()

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="google_ads_oauth_connected",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": PlatformCredential.GOOGLE,
                "customer_id": customer_id,
                "refresh_token_received": bool(refresh_token),
                "login_customer_id": serializer.validated_data.get("login_customer_id") or "",
            },
        )
        emit_observability_event(
            logger,
            "google_ads.oauth.connected",
            tenant_id=str(request.user.tenant_id),
            customer_id=customer_id,
        )

        return Response(
            {
                "credential": PlatformCredentialSerializer(credential).data,
                "refresh_token_received": bool(refresh_token),
            },
            status=status.HTTP_201_CREATED,
        )


class GoogleAdsProvisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = GoogleAdsProvisionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        requested_account_id = (validated.get("external_account_id") or "").strip() or None
        credential = _resolve_google_credential(request=request, external_account_id=requested_account_id)
        if credential is None:
            return Response(
                {"detail": "No Google Ads credential found for this tenant. Complete OAuth first."},
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

        source_definition_id = _resolve_google_source_definition_id(
            str(validated["source_definition_id"]) if validated.get("source_definition_id") else None
        )
        schedule_type = validated.get("schedule_type") or AirbyteConnection.SCHEDULE_CRON
        interval_minutes = validated.get("interval_minutes")
        cron_expression = (
            validated.get("cron_expression") or ""
        ).strip() or DEFAULT_GOOGLE_CONNECTOR_CRON_EXPRESSION
        is_active = validated.get("is_active", True)
        connection_name = (
            validated.get("connection_name") or ""
        ).strip() or f"Google Ads {credential.account_id}"

        refresh_token = credential.decrypt_refresh_token()
        if not refresh_token:
            return Response(
                {
                    "detail": (
                        "Stored Google Ads credential is missing refresh token. "
                        "Reconnect with offline access."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_id = (getattr(settings, "GOOGLE_ADS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", "") or "").strip()
        developer_token = (getattr(settings, "GOOGLE_ADS_DEVELOPER_TOKEN", "") or "").strip()
        if not client_id or not client_secret or not developer_token:
            return Response(
                {
                    "detail": (
                        "GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, and "
                        "GOOGLE_ADS_DEVELOPER_TOKEN are required for provisioning."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        customer_id = _normalize_google_customer_id(credential.account_id)
        if not customer_id:
            return Response(
                {"detail": "Stored Google Ads account_id is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login_customer_candidate = (
            str(validated.get("login_customer_id") or "").strip()
            or str(getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "") or "").strip()
        )
        login_customer_id = _normalize_google_customer_id(login_customer_candidate) or customer_id
        start_date = str(getattr(settings, "GOOGLE_ADS_START_DATE", "2024-01-01") or "2024-01-01")
        conversion_window = int(getattr(settings, "GOOGLE_ADS_CONVERSION_WINDOW_DAYS", 30) or 30)
        lookback_window = int(getattr(settings, "GOOGLE_ADS_LOOKBACK_WINDOW_DAYS", 3) or 3)

        runtime_query = _runtime_window_query()
        source_name = f"Google Ads Source {customer_id}"
        source_reused = False
        connection_reused = False
        source_config_candidates = [
            {
                "developer_token": developer_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "customer_id": customer_id,
                "login_customer_id": login_customer_id,
                "start_date": start_date,
                "conversion_window": conversion_window,
                "lookback_window": lookback_window,
                "use_resource_custom_queries": True,
                "custom_queries": [
                    {
                        "name": "ad_group_ad_performance_daily",
                        "query": runtime_query,
                        "primary_key": ["campaign.id", "ad_group.id", "ad_group_ad.ad.id", "segments.date"],
                        "cursor_field": "segments.date",
                        "destination_sync_mode": "append_dedup",
                    }
                ],
            },
            {
                "developer_token": developer_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "customer_id": customer_id,
                "login_customer_id": login_customer_id,
                "start_date": start_date,
                "conversion_window": conversion_window,
                "lookback_window": lookback_window,
                "include_zero_impressions": True,
                "custom_queries": [
                    {
                        "query": runtime_query,
                        "cursor_field": "segments.date",
                        "primary_key": ["campaign.id", "ad_group.id", "ad_group_ad.ad.id", "segments.date"],
                    }
                ],
            },
        ]

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
                for source_config in source_config_candidates:
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

                    candidate_source_id = source.get("sourceId") if isinstance(source, dict) else None
                    if not isinstance(candidate_source_id, str) or not candidate_source_id:
                        raise ValueError("Airbyte source create/list response missing sourceId.")

                    check_payload = client.check_source(candidate_source_id)
                    check_status = str(check_payload.get("status", "")).lower()
                    if check_status and check_status not in {"succeeded", "success"}:
                        continue

                    discovered = client.discover_source_schema(candidate_source_id)
                    catalog = discovered.get("catalog") if isinstance(discovered, dict) else None
                    if not isinstance(catalog, dict):
                        continue

                    source_id = candidate_source_id
                    configured_catalog = _configured_catalog(catalog)
                    break

                if source_id is None or configured_catalog is None:
                    raise ValueError("Unable to create or update Google Ads source in Airbyte.")

                connections = client.list_connections(str(workspace_id))
                existing_connection = next(
                    (connection for connection in connections if connection.get("name") == connection_name),
                    None,
                )
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
                "provider": PlatformCredential.GOOGLE,
                "schedule_type": schedule_type,
                "interval_minutes": interval_minutes if schedule_type == AirbyteConnection.SCHEDULE_INTERVAL else None,
                "cron_expression": cron_expression if schedule_type == AirbyteConnection.SCHEDULE_CRON else "",
                "is_active": bool(is_active),
            },
        )
        requested_sync_engine = (validated.get("sync_engine") or getattr(settings, "GOOGLE_ADS_SYNC_ENGINE_DEFAULT", "sdk"))
        normalized_sync_engine = str(requested_sync_engine).strip().lower()
        if normalized_sync_engine not in {GoogleAdsSyncState.ENGINE_SDK, GoogleAdsSyncState.ENGINE_AIRBYTE}:
            normalized_sync_engine = GoogleAdsSyncState.ENGINE_SDK
        sync_state = _resolve_google_sync_state(
            tenant=request.user.tenant,
            account_id=customer_id,
        )
        sync_state.desired_engine = normalized_sync_engine
        if not sync_state.fallback_active:
            sync_state.effective_engine = normalized_sync_engine
        sync_state.save(update_fields=["desired_engine", "effective_engine", "updated_at"])

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="google_ads_airbyte_provisioned",
            resource_type="airbyte_connection",
            resource_id=connection_record.id,
            metadata={
                "connection_id": connection_id,
                "provider": PlatformCredential.GOOGLE,
                "source_reused": source_reused,
                "connection_reused": connection_reused,
            },
        )

        return Response(
            {
                "provider": "google_ads",
                "credential": PlatformCredentialSerializer(credential).data,
                "connection": AirbyteConnectionSerializer(connection_record).data,
                "sync_engine": sync_state.effective_engine,
                "fallback_active": sync_state.fallback_active,
                "source_reused": source_reused,
                "connection_reused": connection_reused,
            },
            status=status.HTTP_201_CREATED,
        )


class GoogleAdsSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        credential = (
            PlatformCredential.objects.filter(
                tenant_id=request.user.tenant_id,
                provider=PlatformCredential.GOOGLE,
            )
            .order_by("-updated_at")
            .first()
        )
        sync_state = None
        if credential is not None:
            account_id = _normalize_google_customer_id(credential.account_id)
            if account_id:
                sync_state = _resolve_google_sync_state(
                    tenant=request.user.tenant,
                    account_id=account_id,
                )

        if sync_state is not None and sync_state.effective_engine == GoogleAdsSyncState.ENGINE_SDK:
            task_result = sync_google_ads_sdk_incremental.delay(str(request.user.tenant_id))
            log_audit_event(
                tenant=request.user.tenant,
                user=request.user,
                action="google_ads_sdk_sync_triggered",
                resource_type="sync",
                resource_id=sync_state.id,
                metadata={
                    "provider": PlatformCredential.GOOGLE,
                    "sync_engine": GoogleAdsSyncState.ENGINE_SDK,
                    "task_id": task_result.id,
                },
            )
            return Response(
                {
                    "provider": "google_ads",
                    "sync_engine": GoogleAdsSyncState.ENGINE_SDK,
                    "task_id": task_result.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        connection = (
            AirbyteConnection.objects.filter(tenant_id=request.user.tenant_id, provider=PlatformCredential.GOOGLE)
            .order_by("-updated_at")
            .first()
        )
        if connection is None:
            return Response(
                {"detail": "No Google Ads Airbyte connection found for this tenant."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with AirbyteClient.from_settings() as client:
                payload = client.trigger_sync(str(connection.connection_id))
        except AirbyteClientConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except AirbyteClientError as exc:
            return _airbyte_exception_response(exc)

        job_id = payload.get("job", {}).get("id") if isinstance(payload, dict) else None
        sync_started_at = timezone.now()
        if job_id is not None:
            parsed_job_id = int(job_id) if str(job_id).isdigit() else None
            connection.record_sync(job_id=parsed_job_id, job_status="pending", job_created_at=sync_started_at)

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="google_ads_sync_triggered",
            resource_type="airbyte_connection",
            resource_id=connection.id,
            metadata={
                "provider": PlatformCredential.GOOGLE,
                "connection_id": str(connection.connection_id),
                "job_id": str(job_id) if job_id is not None else None,
            },
        )

        return Response(
            {
                "provider": "google_ads",
                "sync_engine": GoogleAdsSyncState.ENGINE_AIRBYTE,
                "connection_id": str(connection.connection_id),
                "job_id": str(job_id) if job_id is not None else None,
            },
            status=status.HTTP_202_ACCEPTED if job_id is not None else status.HTTP_200_OK,
        )


class GoogleAdsStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        now = timezone.now()
        credential = (
            PlatformCredential.objects.filter(tenant_id=request.user.tenant_id, provider=PlatformCredential.GOOGLE)
            .order_by("-updated_at")
            .first()
        )
        sync_state = None
        if credential is not None:
            account_id = _normalize_google_customer_id(credential.account_id)
            if account_id:
                sync_state = _resolve_google_sync_state(
                    tenant=request.user.tenant,
                    account_id=account_id,
                )
        connection = (
            AirbyteConnection.objects.filter(tenant_id=request.user.tenant_id, provider=PlatformCredential.GOOGLE)
            .order_by("-updated_at")
            .first()
        )

        client_id = (getattr(settings, "GOOGLE_ADS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", "") or "").strip()
        developer_token = (getattr(settings, "GOOGLE_ADS_DEVELOPER_TOKEN", "") or "").strip()
        frontend_base_url = (getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
        redirect_uri_configured = bool(
            (getattr(settings, "GOOGLE_ADS_OAUTH_REDIRECT_URI", "") or "").strip()
            or frontend_base_url
        )
        workspace_id = (getattr(settings, "AIRBYTE_DEFAULT_WORKSPACE_ID", "") or "").strip()
        destination_id = (getattr(settings, "AIRBYTE_DEFAULT_DESTINATION_ID", "") or "").strip()
        oauth_ready = bool(client_id and client_secret and redirect_uri_configured)
        provisioning_defaults_ready = bool(workspace_id and destination_id and developer_token)

        status_value, reason, actions = _resolve_google_status(
            credential=credential,
            connection=connection,
            sync_state=sync_state,
            oauth_ready=oauth_ready,
            provisioning_defaults_ready=provisioning_defaults_ready,
            now=now,
        )
        payload = {
            "provider": "google_ads",
            "status": status_value,
            "reason": reason,
            "actions": actions,
            "last_checked_at": now,
            "last_synced_at": (
                sync_state.last_sync_success_at
                if sync_state and sync_state.effective_engine == GoogleAdsSyncState.ENGINE_SDK
                else (connection.last_synced_at if connection is not None else None)
            ),
            "sync_engine": (
                sync_state.effective_engine
                if sync_state is not None
                else GoogleAdsSyncState.ENGINE_AIRBYTE
            ),
            "fallback_active": bool(sync_state and sync_state.fallback_active),
            "parity_state": (
                sync_state.parity_state
                if sync_state is not None
                else GoogleAdsSyncState.PARITY_UNKNOWN
            ),
            "last_parity_passed_at": (
                sync_state.last_parity_passed_at
                if sync_state is not None
                else None
            ),
            "metadata": {
                "has_credential": bool(credential),
                "credential_account_id": credential.account_id if credential else None,
                "has_connection": bool(connection),
                "connection_id": str(connection.connection_id) if connection else None,
                "connection_active": bool(connection and connection.is_active),
                "last_job_status": connection.last_job_status if connection else None,
                "last_job_error": connection.last_job_error if connection else None,
                "oauth_ready": oauth_ready,
                "provisioning_defaults_ready": provisioning_defaults_ready,
                "desired_sync_engine": sync_state.desired_engine if sync_state else None,
                "sdk_last_sync_success_at": sync_state.last_sync_success_at if sync_state else None,
                "sdk_last_sync_error": sync_state.last_sync_error if sync_state else None,
                "consecutive_sdk_failures": sync_state.consecutive_sdk_failures if sync_state else 0,
                "consecutive_parity_failures": sync_state.consecutive_parity_failures if sync_state else 0,
            },
        }
        response_serializer = GoogleAdsStatusResponseSerializer(data=payload)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data)


class GoogleAdsDisconnectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        paused_count = AirbyteConnection.objects.filter(
            tenant_id=request.user.tenant_id,
            provider=PlatformCredential.GOOGLE,
            is_active=True,
        ).update(is_active=False)

        credential_qs = PlatformCredential.objects.filter(
            tenant_id=request.user.tenant_id,
            provider=PlatformCredential.GOOGLE,
        )
        existing_ids = [str(credential_id) for credential_id in credential_qs.values_list("id", flat=True)]
        deleted_count, _ = credential_qs.delete()

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="google_ads_disconnected",
            resource_type="platform_credential",
            resource_id=existing_ids[0] if existing_ids else None,
            metadata={
                "provider": PlatformCredential.GOOGLE,
                "paused_connections": paused_count,
                "deleted_credentials": deleted_count,
            },
        )
        return Response(
            {
                "provider": "google_ads",
                "disconnected": bool(deleted_count or paused_count),
                "paused_connections": paused_count,
                "deleted_credentials": deleted_count,
            }
        )


class GoogleAdsReferenceSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        service_catalog = _safe_load(load_reference_catalog)
        query_reference = _safe_load(load_query_reference)
        fields_reference = _safe_load(load_fields_reference)
        return Response(
            {
                "provider": "google_ads",
                "version": "v23",
                "service_catalog": {
                    "available": service_catalog is not None,
                    "counts": (service_catalog or {}).get("counts", {}),
                    "total_entries": (service_catalog or {}).get("total_entries", 0),
                },
                "query_reference": {
                    "available": query_reference is not None,
                    "resource_count": (query_reference or {}).get("resource_count", 0),
                },
                "fields_reference": {
                    "available": fields_reference is not None,
                    "counts": (fields_reference or {}).get("counts", {}),
                    "total_fields": (fields_reference or {}).get("total_fields", 0),
                },
            }
        )


def _safe_load(loader):  # type: ignore[no-untyped-def]
    try:
        return loader()
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None
