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
    TenantAirbyteSyncStatus,
)
from .serializers import (
    AirbyteConnectionSerializer,
    AlertRuleDefinitionSerializer,
    CampaignBudgetSerializer,
    MetaOAuthExchangeSerializer,
    MetaPageConnectSerializer,
    MetaProvisionSerializer,
    PlatformCredentialSerializer,
)
from .meta_graph import MetaGraphClient, MetaGraphClientError, MetaGraphConfigurationError
from core.serializers import TenantAirbyteSyncStatusSerializer


logger = logging.getLogger(__name__)

META_OAUTH_STATE_SALT = "integrations.meta.oauth.state"
META_OAUTH_SELECTION_CACHE_PREFIX = "integrations:meta:selection:"
META_OAUTH_STATE_MAX_AGE_SECONDS = 600
META_OAUTH_SELECTION_TTL_SECONDS = 600
DEFAULT_CONNECTOR_CRON_EXPRESSION = "0 6-22 * * *"
DEFAULT_CONNECTOR_TIMEZONE = "America/Jamaica"
DEFAULT_META_SOURCE_DEFINITION_ID = "778daa7c-feaf-4db6-96f3-70fd645acc77"
DEFAULT_META_REQUIRED_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "ads_read",
    "business_management",
]
DEFAULT_META_OAUTH_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_read_user_content",
    "ads_read",
    "business_management",
    "read_insights",
    "instagram_basic",
    "instagram_manage_insights",
]
DEFAULT_META_INSTAGRAM_REQUIRED_SCOPES = [
    "instagram_basic",
    "instagram_manage_insights",
]


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
    return {
        "tenant_id": str(request.user.tenant_id),
        "user_id": str(request.user.id),
        "nonce": secrets.token_urlsafe(24),
    }


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
        supported_sync_modes = raw.get("supportedSyncModes") or ["full_refresh"]
        supported_dest_modes = raw.get("supportedDestinationSyncModes") or ["append"]
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

        cursor_field = raw.get("defaultCursorField") or []
        if not isinstance(cursor_field, list):
            cursor_field = []
        primary_key = raw.get("sourceDefinedPrimaryKey") or []
        if not isinstance(primary_key, list):
            primary_key = []

        configured_streams.append(
            {
                "stream": raw,
                "config": {
                    "aliasName": raw.get("name"),
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
                "cronExpression": cron_expression or DEFAULT_CONNECTOR_CRON_EXPRESSION,
                "cronTimeZone": DEFAULT_CONNECTOR_TIMEZONE,
            }
        },
    }


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


def _airbyte_exception_response(exc: AirbyteClientError) -> Response:
    status_code = (
        status.HTTP_504_GATEWAY_TIMEOUT
        if isinstance(exc.__cause__, httpx.TimeoutException)
        else status.HTTP_502_BAD_GATEWAY
    )
    return Response({"detail": str(exc)}, status=status_code)


class MetaOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        try:
            app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
            if not app_id:
                raise MetaGraphConfigurationError("META_APP_ID must be configured for Meta OAuth.")
            redirect_uri = _meta_redirect_uri()
        except MetaGraphConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        signed_state = _sign_meta_state(request=request)
        scopes = [scope for scope in getattr(settings, "META_OAUTH_SCOPES", DEFAULT_META_OAUTH_SCOPES) if scope]
        query = urlencode(
            {
                "client_id": app_id,
                "redirect_uri": redirect_uri,
                "state": signed_state,
                "response_type": "code",
                "scope": ",".join(scopes),
            }
        )
        graph_version = (getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0").strip()
        authorize_url = f"https://www.facebook.com/{graph_version}/dialog/oauth?{query}"
        return Response(
            {
                "authorize_url": authorize_url,
                "state": signed_state,
                "redirect_uri": redirect_uri,
            }
        )


class MetaSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        app_secret = (getattr(settings, "META_APP_SECRET", "") or "").strip()
        frontend_base_url = (getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
        redirect_uri_configured = bool(
            (getattr(settings, "META_OAUTH_REDIRECT_URI", "") or "").strip()
            or frontend_base_url
        )
        scopes = [scope for scope in getattr(settings, "META_OAUTH_SCOPES", DEFAULT_META_OAUTH_SCOPES) if scope]
        scope_set = {scope.strip() for scope in scopes if isinstance(scope, str) and scope.strip()}
        workspace_id = (getattr(settings, "AIRBYTE_DEFAULT_WORKSPACE_ID", "") or "").strip()
        destination_id = (getattr(settings, "AIRBYTE_DEFAULT_DESTINATION_ID", "") or "").strip()
        source_definition_id = _resolve_meta_source_definition_id(None)
        source_definition_configured = bool(
            (getattr(settings, "AIRBYTE_SOURCE_DEFINITION_META", "") or "").strip()
        )

        ready_for_oauth = bool(app_id and app_secret and redirect_uri_configured)
        ready_for_provisioning_defaults = bool(workspace_id and destination_id)
        meta_app_missing = []
        if not app_id:
            meta_app_missing.append("META_APP_ID")
        if not app_secret:
            meta_app_missing.append("META_APP_SECRET")
        redirect_missing = []
        if not redirect_uri_configured:
            redirect_missing = ["META_OAUTH_REDIRECT_URI", "FRONTEND_BASE_URL"]
        workspace_missing = [] if workspace_id else ["AIRBYTE_DEFAULT_WORKSPACE_ID"]
        destination_missing = [] if destination_id else ["AIRBYTE_DEFAULT_DESTINATION_ID"]
        source_definition_missing = [] if source_definition_configured else ["AIRBYTE_SOURCE_DEFINITION_META"]
        instagram_scope_missing = [
            scope for scope in DEFAULT_META_INSTAGRAM_REQUIRED_SCOPES if scope not in scope_set
        ]
        marketing_scope_missing = [scope for scope in DEFAULT_META_REQUIRED_SCOPES if scope not in scope_set]

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
                "label": "Instagram OAuth scopes included",
                "ok": not instagram_scope_missing,
                "required_scopes": DEFAULT_META_INSTAGRAM_REQUIRED_SCOPES,
                "missing_scopes": instagram_scope_missing,
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
                "graph_api_version": (getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0").strip(),
                "redirect_uri": resolved_redirect_uri,
                "source_definition_id": source_definition_id,
            }
        )


class MetaOAuthExchangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):  # noqa: ANN001 - DRF signature
        serializer = MetaOAuthExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        _, state_error = _validate_meta_state(request=request, state=str(serializer.validated_data["state"]))
        if state_error is not None:
            return state_error

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
            }
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

        with transaction.atomic():
            credential, _ = PlatformCredential.objects.select_for_update().get_or_create(
                tenant=request.user.tenant,
                provider=PlatformCredential.META,
                account_id=account_id,
                defaults={"expires_at": expires_at},
            )
            credential.expires_at = expires_at
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
            },
        )

        return Response(
            {
                "credential": PlatformCredentialSerializer(credential).data,
                "page": selected_page,
                "ad_account": selected_account,
                "instagram_account": selected_instagram_account,
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
        try:
            with AirbyteClient.from_settings() as client:
                sources = client.list_sources(str(workspace_id))
                existing_source = _find_by_name(sources, source_name)
                if existing_source:
                    source = existing_source
                    source_reused = True
                else:
                    source = client.create_source(
                        {
                            "name": source_name,
                            "sourceDefinitionId": source_definition_id,
                            "workspaceId": str(workspace_id),
                            "connectionConfiguration": {
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
                            },
                        }
                    )

                source_id = source.get("sourceId") if isinstance(source, dict) else None
                if not isinstance(source_id, str) or not source_id:
                    raise ValueError("Airbyte source create/list response missing sourceId.")

                check_payload = client.check_source(source_id)
                check_job = check_payload.get("jobInfo") if isinstance(check_payload, dict) else None
                check_status = (
                    str(check_job.get("status", "")).lower()
                    if isinstance(check_job, dict)
                    else str(check_payload.get("status", "")).lower()
                )
                if check_status and check_status not in {"succeeded", "success"}:
                    raise ValueError(f"Airbyte source check failed (status={check_status}).")

                discovered = client.discover_source_schema(source_id)
                catalog = discovered.get("catalog") if isinstance(discovered, dict) else None
                if not isinstance(catalog, dict):
                    raise ValueError("Airbyte discover schema response missing catalog.")
                configured_catalog = _configured_catalog(catalog)

                connections = client.list_connections(str(workspace_id))
                existing_connection = _find_by_name(connections, connection_name)
                if existing_connection:
                    connection_payload = existing_connection
                    connection_reused = True
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
        if job_id is not None:
            connection.record_sync(job_id=job_id, job_status="pending", job_created_at=timezone.now())

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
