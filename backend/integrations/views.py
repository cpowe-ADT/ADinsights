from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Dict, Optional
import logging
import secrets
import uuid
from urllib.parse import urlencode

import httpx
from django.core import signing
from django.core.cache import cache
from django.conf import settings
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
    IntegrationOAuthCallbackSerializer,
    IntegrationProvisionSerializer,
    MetaOAuthExchangeSerializer,
    MetaPageConnectSerializer,
    PlatformCredentialSerializer,
)
from .google_oauth import (
    GoogleOAuthClient,
    GoogleOAuthClientError,
    GoogleOAuthConfigurationError,
)
from .meta_graph import MetaGraphClient, MetaGraphClientError, MetaGraphConfigurationError
from .provider_registry import get_provider
from core.serializers import TenantAirbyteSyncStatusSerializer


logger = logging.getLogger(__name__)

META_OAUTH_STATE_SALT = "integrations.meta.oauth.state"
META_OAUTH_SELECTION_CACHE_PREFIX = "integrations:meta:selection:"
META_OAUTH_STATE_MAX_AGE_SECONDS = 600
META_OAUTH_SELECTION_TTL_SECONDS = 600
INTEGRATION_OAUTH_STATE_SALT = "integrations.oauth.state"
INTEGRATION_OAUTH_STATE_MAX_AGE_SECONDS = 600
DEFAULT_CONNECTOR_CRON_EXPRESSION = "0 6-22 * * *"
DEFAULT_CONNECTOR_TIMEZONE = "America/Jamaica"
AUTH_ERROR_HINTS = (
    "oauth",
    "token",
    "auth",
    "unauthorized",
    "forbidden",
    "permission",
    "invalid_grant",
    "expired",
    "reauth",
)


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


def _integration_state_payload(*, request, provider_slug: str) -> dict[str, str]:
    return {
        "provider": provider_slug,
        "tenant_id": str(request.user.tenant_id),
        "user_id": str(request.user.id),
        "nonce": secrets.token_urlsafe(24),
    }


def _sign_integration_state(*, request, provider_slug: str) -> str:
    return signing.dumps(
        _integration_state_payload(request=request, provider_slug=provider_slug),
        salt=INTEGRATION_OAUTH_STATE_SALT,
    )


def _validate_integration_state(*, state: str, provider_slug: str, request) -> tuple[dict[str, Any], Response | None]:
    try:
        payload = signing.loads(
            state,
            salt=INTEGRATION_OAUTH_STATE_SALT,
            max_age=INTEGRATION_OAUTH_STATE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired:
        return {}, Response(
            {"detail": "OAuth state expired. Restart the connect flow."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except signing.BadSignature:
        return {}, Response(
            {"detail": "OAuth state is invalid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if payload.get("provider") != provider_slug:
        return {}, Response(
            {"detail": "OAuth state provider mismatch."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expected_user_id = payload.get("user_id")
    expected_tenant_id = payload.get("tenant_id")
    if expected_user_id != str(request.user.id) or expected_tenant_id != str(request.user.tenant_id):
        return {}, Response(
            {"detail": "OAuth state does not match the authenticated tenant user."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return payload, None


def _resolve_google_scopes(provider_slug: str) -> list[str]:
    if provider_slug == "google_ads":
        return [scope for scope in getattr(settings, "GOOGLE_OAUTH_SCOPES_GOOGLE_ADS", []) if scope]
    if provider_slug == "ga4":
        return [scope for scope in getattr(settings, "GOOGLE_OAUTH_SCOPES_GA4", []) if scope]
    if provider_slug == "search_console":
        return [
            scope for scope in getattr(settings, "GOOGLE_OAUTH_SCOPES_SEARCH_CONSOLE", []) if scope
        ]
    return []


def _extract_job_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
    if not isinstance(job, dict):
        return None
    job_id = job.get("id") or job.get("jobId")
    return str(job_id) if job_id is not None else None


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


def _resolve_source_definition_id(provider_slug: str, requested_id: str | None) -> str:
    if requested_id:
        return requested_id
    provider = get_provider(provider_slug)
    if provider and provider.source_definition_id:
        return provider.source_definition_id
    if provider_slug == "ga4":
        configured = (getattr(settings, "AIRBYTE_SOURCE_DEFINITION_GA4", "") or "").strip()
        if configured:
            return configured
        raise ValueError("Set AIRBYTE_SOURCE_DEFINITION_GA4 or pass source_definition_id.")
    if provider_slug == "search_console":
        configured = (getattr(settings, "AIRBYTE_SOURCE_DEFINITION_SEARCH_CONSOLE", "") or "").strip()
        if configured:
            return configured
        raise ValueError(
            "Set AIRBYTE_SOURCE_DEFINITION_SEARCH_CONSOLE or pass source_definition_id."
        )
    raise ValueError("No source definition configured for this provider.")


def _build_source_configuration(provider_slug: str, credential: PlatformCredential) -> dict[str, Any]:
    access_token = credential.decrypt_access_token()
    refresh_token = credential.decrypt_refresh_token()
    if not access_token:
        raise ValueError("Stored credential is missing an access token.")

    if provider_slug in {"meta_ads", "facebook_pages"}:
        app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        app_secret = (getattr(settings, "META_APP_SECRET", "") or "").strip()
        if not app_id or not app_secret:
            raise ValueError("META_APP_ID and META_APP_SECRET must be configured for Meta provisioning.")
        return {
            "account_id": credential.account_id,
            "access_token": access_token,
            "app_id": app_id,
            "app_secret": app_secret,
            "start_date": "2024-01-01T00:00:00Z",
            "include_deleted": False,
            "action_breakdowns": ["action_type"],
            "breakdowns": ["region", "impression_device"],
            "insights_lookback_window": 3,
            "window_in_days": 3,
            "report_interval": "daily",
            "custom_insights_fields": ["impressions", "clicks", "spend", "actions", "action_values"],
        }

    client_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or "").strip()
    client_secret = (getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or "").strip()
    if provider_slug == "google_ads":
        developer_token = (getattr(settings, "AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN", "") or "").strip()
        login_customer_id = (
            getattr(settings, "AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID", "") or ""
        ).strip()
        if not developer_token or not client_id or not client_secret:
            raise ValueError(
                "AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN and Google OAuth client credentials are required."
            )
        if not refresh_token:
            raise ValueError("Google Ads provisioning requires a refresh token.")
        return {
            "developer_token": developer_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "customer_id": credential.account_id,
            "login_customer_id": login_customer_id or credential.account_id,
            "start_date": "2024-01-01",
            "conversion_window": 30,
            "lookback_window": 3,
        }

    if provider_slug == "ga4":
        if not client_id or not client_secret:
            raise ValueError("Google OAuth client credentials are required for GA4 provisioning.")
        if not refresh_token:
            raise ValueError("GA4 provisioning requires a refresh token.")
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "property_id": credential.account_id,
            "start_date": "2024-01-01",
            "lookback_window": 3,
            "timezone": DEFAULT_CONNECTOR_TIMEZONE,
            "dimensions": [
                "date",
                "sessionDefaultChannelGroup",
                "country",
                "city",
                "campaignName",
            ],
            "metrics": [
                "sessions",
                "engagedSessions",
                "conversions",
                "purchaseRevenue",
            ],
        }

    if provider_slug == "search_console":
        if not client_id or not client_secret:
            raise ValueError("Google OAuth client credentials are required for Search Console provisioning.")
        if not refresh_token:
            raise ValueError("Search Console provisioning requires a refresh token.")
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "site_url": credential.account_id,
            "start_date": "2024-01-01",
            "lookback_window": 3,
            "dimensions": ["date", "country", "device", "query", "page"],
            "row_limit": 25000,
        }
    raise ValueError("Unsupported provider for provisioning.")


def _source_matches_account(
    *,
    provider_slug: str,
    account_id: str,
    source: dict[str, Any],
    source_definition_id: str,
) -> bool:
    if str(source.get("sourceDefinitionId") or "") != source_definition_id:
        return False
    config = source.get("connectionConfiguration")
    if not isinstance(config, dict):
        return False
    candidates: list[str] = []
    if provider_slug in {"meta_ads", "facebook_pages"}:
        candidates = [str(config.get("account_id") or "")]
    elif provider_slug == "google_ads":
        candidates = [str(config.get("customer_id") or "")]
    elif provider_slug == "ga4":
        candidates = [str(config.get("property_id") or "")]
    elif provider_slug == "search_console":
        candidates = [str(config.get("site_url") or "")]
    return account_id in [candidate.strip() for candidate in candidates]


def _find_source_for_account(
    *,
    provider_slug: str,
    account_id: str,
    sources: list[dict[str, Any]],
    source_definition_id: str,
) -> dict[str, Any] | None:
    matching = [
        source
        for source in sources
        if _source_matches_account(
            provider_slug=provider_slug,
            account_id=account_id,
            source=source,
            source_definition_id=source_definition_id,
        )
    ]
    if not matching:
        return None
    if len(matching) > 1:
        raise ValueError(
            "Multiple Airbyte sources match this provider/account. "
            "Set a unique connection_name or clean duplicate sources."
        )
    return matching[0]


def _connection_matches_source_destination(
    connection: dict[str, Any],
    *,
    source_id: str,
    destination_id: str,
) -> bool:
    return str(connection.get("sourceId") or "") == source_id and str(
        connection.get("destinationId") or ""
    ) == destination_id


def _credential_needs_reauth(
    *,
    credentials: list[PlatformCredential],
    latest_connection: AirbyteConnection | None,
) -> bool:
    if not credentials:
        return False
    now = timezone.now()
    for credential in credentials:
        if credential.expires_at and credential.expires_at <= now:
            return True
    if latest_connection and latest_connection.last_job_error:
        error_value = latest_connection.last_job_error.lower()
        if any(hint in error_value for hint in AUTH_ERROR_HINTS):
            return True
    return False



class MetaOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
            if not app_id:
                raise MetaGraphConfigurationError("META_APP_ID must be configured for Meta OAuth.")
            redirect_uri = _meta_redirect_uri()
        except MetaGraphConfigurationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state_payload = {
            "tenant_id": str(request.user.tenant_id),
            "user_id": str(request.user.id),
            "nonce": secrets.token_urlsafe(24),
        }
        signed_state = signing.dumps(state_payload, salt=META_OAUTH_STATE_SALT)
        scope_values = [scope for scope in getattr(settings, "META_OAUTH_SCOPES", []) if scope]
        query = urlencode(
            {
                "client_id": app_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "state": signed_state,
                "scope": ",".join(scope_values),
            }
        )
        authorize_url = f"https://www.facebook.com/{getattr(settings, 'META_GRAPH_API_VERSION', 'v20.0')}/dialog/oauth?{query}"
        return Response(
            {
                "authorize_url": authorize_url,
                "state": signed_state,
                "redirect_uri": redirect_uri,
            }
        )


class MetaOAuthExchangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MetaOAuthExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            state_payload = signing.loads(
                serializer.validated_data["state"],
                salt=META_OAUTH_STATE_SALT,
                max_age=META_OAUTH_STATE_MAX_AGE_SECONDS,
            )
        except signing.SignatureExpired:
            return Response(
                {"detail": "Meta OAuth state expired. Restart the connect flow."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            return Response(
                {"detail": "Meta OAuth state is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expected_user_id = state_payload.get("user_id")
        expected_tenant_id = state_payload.get("tenant_id")
        if expected_user_id != str(request.user.id) or expected_tenant_id != str(request.user.tenant_id):
            return Response(
                {"detail": "Meta OAuth state does not match the authenticated tenant user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            redirect_uri = _meta_redirect_uri()
            with MetaGraphClient.from_settings() as client:
                user_access_token = client.exchange_code(
                    code=serializer.validated_data["code"],
                    redirect_uri=redirect_uri,
                )
                pages = client.list_pages(user_access_token=user_access_token)
        except MetaGraphConfigurationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except MetaGraphClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if not pages:
            return Response(
                {"detail": "No Facebook pages were returned for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selection_token = secrets.token_urlsafe(24)
        cache_payload = {
            "tenant_id": str(request.user.tenant_id),
            "user_id": str(request.user.id),
            "pages": [
                {
                    "id": page.id,
                    "name": page.name,
                    "category": page.category,
                    "tasks": page.tasks or [],
                    "perms": page.perms or [],
                    "access_token": page.access_token,
                }
                for page in pages
            ],
        }
        cache.set(
            f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}",
            cache_payload,
            timeout=META_OAUTH_SELECTION_TTL_SECONDS,
        )
        return Response(
            {
                "selection_token": selection_token,
                "expires_in_seconds": META_OAUTH_SELECTION_TTL_SECONDS,
                "pages": [page.as_public_dict() for page in pages],
            }
        )


class MetaPageConnectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MetaPageConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selection_token = serializer.validated_data["selection_token"]
        cache_key = f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}"
        selection_payload = cache.get(cache_key)
        if not isinstance(selection_payload, dict):
            return Response(
                {"detail": "Meta page selection token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            selection_payload.get("tenant_id") != str(request.user.tenant_id)
            or selection_payload.get("user_id") != str(request.user.id)
        ):
            return Response(
                {"detail": "Meta page selection token does not match this tenant user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        page_id = serializer.validated_data["page_id"]
        page_record = None
        for row in selection_payload.get("pages", []):
            if isinstance(row, dict) and row.get("id") == page_id:
                page_record = row
                break

        if page_record is None:
            return Response(
                {"detail": "Selected Facebook page was not found in the OAuth result set."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_token = page_record.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            return Response(
                {"detail": "Selected Facebook page is missing an access token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        credential, _ = PlatformCredential.objects.update_or_create(
            tenant=request.user.tenant,
            provider=PlatformCredential.META,
            account_id=page_id,
            defaults={},
        )
        credential.mark_refresh_token_for_clear()
        credential.set_raw_tokens(access_token, None)
        credential.save()
        cache.delete(cache_key)

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user if request.user.is_authenticated else None,
            action="meta_page_connected",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": PlatformCredential.META,
                "account_id": page_id,
                "page_name": page_record.get("name"),
            },
        )

        return Response(
            {
                "credential": PlatformCredentialSerializer(credential).data,
                "page": {
                    "id": page_id,
                    "name": page_record.get("name"),
                    "category": page_record.get("category"),
                    "tasks": page_record.get("tasks", []),
                    "perms": page_record.get("perms", []),
                },
            }
        )


class IntegrationOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None:
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        signed_state = _sign_integration_state(request=request, provider_slug=provider_config.slug)

        if provider_config.oauth_family == "meta":
            try:
                app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
                if not app_id:
                    raise MetaGraphConfigurationError("META_APP_ID must be configured for Meta OAuth.")
                redirect_uri = _meta_redirect_uri()
            except MetaGraphConfigurationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            scopes = [scope for scope in getattr(settings, "META_OAUTH_SCOPES", []) if scope]
            query = urlencode(
                {
                    "client_id": app_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "state": signed_state,
                    "scope": ",".join(scopes),
                }
            )
            authorize_url = (
                f"https://www.facebook.com/{getattr(settings, 'META_GRAPH_API_VERSION', 'v20.0')}"
                f"/dialog/oauth?{query}"
            )
            return Response(
                {
                    "provider": provider_config.slug,
                    "authorize_url": authorize_url,
                    "state": signed_state,
                    "redirect_uri": redirect_uri,
                }
            )

        try:
            oauth_client = GoogleOAuthClient.from_settings(settings)
            scopes = _resolve_google_scopes(provider_config.slug)
            authorize_url = oauth_client.build_authorize_url(state=signed_state, scopes=scopes)
        except GoogleOAuthConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "provider": provider_config.slug,
                "authorize_url": authorize_url,
                "state": signed_state,
                "redirect_uri": oauth_client.redirect_uri,
            }
        )


class IntegrationOAuthCallbackView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None:
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        serializer = IntegrationOAuthCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, error_response = _validate_integration_state(
            state=serializer.validated_data["state"],
            provider_slug=provider_config.slug,
            request=request,
        )
        if error_response is not None:
            return error_response

        if provider_config.oauth_family == "meta":
            return self._handle_meta_callback(request, provider_config.slug, serializer.validated_data)
        return self._handle_google_callback(request, provider_config, serializer.validated_data)

    def _handle_google_callback(
        self,
        request,
        provider_config,
        payload: dict[str, Any],
    ) -> Response:
        account_id = (payload.get("external_account_id") or "").strip() or "default"
        try:
            oauth_client = GoogleOAuthClient.from_settings(settings)
            token = oauth_client.exchange_code(code=str(payload["code"]))
        except GoogleOAuthConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except GoogleOAuthClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        credential, _ = PlatformCredential.objects.get_or_create(
            tenant=request.user.tenant,
            provider=provider_config.credential_provider,
            account_id=account_id,
        )
        credential.set_raw_tokens(token.access_token, token.refresh_token)
        if token.expires_in is not None:
            credential.expires_at = timezone.now() + timedelta(seconds=token.expires_in)
        credential.save()

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user if request.user.is_authenticated else None,
            action="integration_oauth_connected",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": provider_config.slug,
                "credential_provider": provider_config.credential_provider,
                "account_id": account_id,
            },
        )
        return Response(
            {
                "provider": provider_config.slug,
                "credential": PlatformCredentialSerializer(credential).data,
                "status": "connected",
            }
        )

    def _handle_meta_callback(self, request, provider_slug: str, validated_data: dict[str, Any]) -> Response:
        del provider_slug  # metadata only
        try:
            redirect_uri = _meta_redirect_uri()
            with MetaGraphClient.from_settings() as client:
                user_access_token = client.exchange_code(
                    code=validated_data["code"],
                    redirect_uri=redirect_uri,
                )
                pages = client.list_pages(user_access_token=user_access_token)
        except MetaGraphConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except MetaGraphClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if not pages:
            return Response(
                {"detail": "No Facebook pages were returned for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page_id = (validated_data.get("page_id") or "").strip()
        if page_id:
            for page in pages:
                if page.id == page_id:
                    credential, _ = PlatformCredential.objects.update_or_create(
                        tenant=request.user.tenant,
                        provider=PlatformCredential.META,
                        account_id=page.id,
                        defaults={},
                    )
                    credential.mark_refresh_token_for_clear()
                    credential.set_raw_tokens(page.access_token, None)
                    credential.save()
                    log_audit_event(
                        tenant=request.user.tenant,
                        user=request.user if request.user.is_authenticated else None,
                        action="meta_page_connected",
                        resource_type="platform_credential",
                        resource_id=credential.id,
                        metadata={
                            "provider": "facebook_pages",
                            "account_id": page.id,
                            "page_name": page.name,
                        },
                    )
                    return Response(
                        {
                            "provider": "facebook_pages",
                            "credential": PlatformCredentialSerializer(credential).data,
                            "page": page.as_public_dict(),
                            "status": "connected",
                        }
                    )
            return Response(
                {"detail": "Selected Facebook page was not returned by Meta OAuth."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selection_token = secrets.token_urlsafe(24)
        cache_payload = {
            "tenant_id": str(request.user.tenant_id),
            "user_id": str(request.user.id),
            "pages": [
                {
                    "id": page.id,
                    "name": page.name,
                    "category": page.category,
                    "tasks": page.tasks or [],
                    "perms": page.perms or [],
                    "access_token": page.access_token,
                }
                for page in pages
            ],
        }
        cache.set(
            f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}",
            cache_payload,
            timeout=META_OAUTH_SELECTION_TTL_SECONDS,
        )
        return Response(
            {
                "provider": "facebook_pages",
                "selection_token": selection_token,
                "expires_in_seconds": META_OAUTH_SELECTION_TTL_SECONDS,
                "pages": [page.as_public_dict() for page in pages],
                "status": "selection_required",
            }
        )


class IntegrationProvisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None:
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        serializer = IntegrationProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        account_filter = (validated.get("external_account_id") or "").strip()
        credentials = PlatformCredential.objects.filter(
            tenant_id=request.user.tenant_id,
            provider=provider_config.credential_provider,
        ).order_by("-updated_at")
        if account_filter:
            credentials = credentials.filter(account_id=account_filter)
        credential = credentials.first()
        if credential is None:
            return Response(
                {
                    "detail": (
                        f"No credential found for provider '{provider_config.slug}'. "
                        "Complete OAuth first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        workspace_id = validated.get("workspace_id") or getattr(settings, "AIRBYTE_DEFAULT_WORKSPACE_ID", None)
        destination_id = validated.get("destination_id") or getattr(
            settings, "AIRBYTE_DEFAULT_DESTINATION_ID", None
        )
        if not workspace_id or not destination_id:
            return Response(
                {
                    "detail": (
                        "workspace_id and destination_id are required unless "
                        "AIRBYTE_DEFAULT_WORKSPACE_ID and AIRBYTE_DEFAULT_DESTINATION_ID are set."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        source_definition_id_raw = validated.get("source_definition_id")
        source_definition_id = str(source_definition_id_raw) if source_definition_id_raw else None
        try:
            resolved_source_definition_id = _resolve_source_definition_id(
                provider_config.slug,
                source_definition_id,
            )
            source_configuration = (
                validated.get("source_configuration")
                or _build_source_configuration(provider_config.slug, credential)
            )
            if not isinstance(source_configuration, dict):
                raise ValueError("source_configuration must be an object when provided.")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                credential = PlatformCredential.objects.select_for_update().get(pk=credential.pk)
                with AirbyteClient.from_settings() as client:
                    source_name = (
                        f"{request.user.tenant.name} "
                        f"{provider_config.label} Source {credential.account_id}"
                    )
                    workspace_sources = client.list_sources(str(workspace_id))
                    existing_source = _find_by_name(workspace_sources, source_name)
                    if existing_source is None:
                        existing_source = _find_source_for_account(
                            provider_slug=provider_config.slug,
                            account_id=credential.account_id,
                            sources=workspace_sources,
                            source_definition_id=resolved_source_definition_id,
                        )
                    source_reused = existing_source is not None
                    if existing_source is None:
                        source_payload = {
                            "workspaceId": str(workspace_id),
                            "name": source_name,
                            "sourceDefinitionId": resolved_source_definition_id,
                            "connectionConfiguration": source_configuration,
                        }
                        source = client.create_source(source_payload)
                    else:
                        source = existing_source
                    source_id = source.get("sourceId")
                    if not source_id:
                        raise ValueError("Airbyte source create/list response missing sourceId.")

                    discovered = client.discover_source_schema(str(source_id))
                    catalog = discovered.get("catalog")
                    if not isinstance(catalog, dict):
                        raise ValueError("Airbyte schema discovery did not return a catalog.")
                    sync_catalog = _configured_catalog(catalog)

                    connection_name = (
                        str(validated.get("connection_name") or "").strip()
                        or f"{request.user.tenant.name} {provider_config.default_connection_name}"
                    )
                    workspace_connections = client.list_connections(str(workspace_id))
                    existing_connection = _find_by_name(workspace_connections, connection_name)
                    if existing_connection and not _connection_matches_source_destination(
                        existing_connection,
                        source_id=str(source_id),
                        destination_id=str(destination_id),
                    ):
                        raise ValueError(
                            "Existing Airbyte connection name maps to a different "
                            "source/destination. Choose a unique connection_name."
                        )
                    if existing_connection is None:
                        for candidate in workspace_connections:
                            if _connection_matches_source_destination(
                                candidate,
                                source_id=str(source_id),
                                destination_id=str(destination_id),
                            ):
                                existing_connection = candidate
                                break

                    connection_reused = existing_connection is not None
                    if existing_connection is None:
                        schedule = _schedule_payload(
                            schedule_type=str(validated["schedule_type"]),
                            interval_minutes=validated.get("interval_minutes"),
                            cron_expression=str(validated.get("cron_expression") or ""),
                        )
                        connection_payload = {
                            "name": connection_name,
                            "workspaceId": str(workspace_id),
                            "sourceId": str(source_id),
                            "destinationId": str(destination_id),
                            "status": "active" if bool(validated.get("is_active", True)) else "inactive",
                            "syncCatalog": sync_catalog,
                            "prefix": "",
                            **schedule,
                        }
                        airbyte_connection = client.create_connection(connection_payload)
                    else:
                        airbyte_connection = existing_connection

        except (AirbyteClientConfigurationError, AirbyteClientError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        connection_id_raw = airbyte_connection.get("connectionId")
        if not connection_id_raw:
            return Response(
                {"detail": "Airbyte connection response did not include connectionId."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        connection_id = uuid.UUID(str(connection_id_raw))
        local_connection, _ = AirbyteConnection.objects.update_or_create(
            tenant=request.user.tenant,
            connection_id=connection_id,
            defaults={
                "name": str(airbyte_connection.get("name") or provider_config.default_connection_name),
                "workspace_id": uuid.UUID(str(workspace_id)),
                "provider": provider_config.credential_provider,
                "schedule_type": serializer.validated_data["schedule_type"],
                "interval_minutes": serializer.validated_data.get("interval_minutes"),
                "cron_expression": str(serializer.validated_data.get("cron_expression") or ""),
                "is_active": bool(serializer.validated_data.get("is_active", True)),
            },
        )

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user if request.user.is_authenticated else None,
            action="integration_provisioned",
            resource_type="airbyte_connection",
            resource_id=local_connection.id,
            metadata={
                "provider": provider_config.slug,
                "credential_provider": provider_config.credential_provider,
                "account_id": credential.account_id,
                "source_id": source.get("sourceId"),
                "connection_id": str(local_connection.connection_id),
                "source_reused": source_reused,
                "connection_reused": connection_reused,
            },
        )

        return Response(
            {
                "provider": provider_config.slug,
                "credential": PlatformCredentialSerializer(credential).data,
                "connection": AirbyteConnectionSerializer(local_connection).data,
                "source": {
                    "source_id": source.get("sourceId"),
                    "name": source.get("name"),
                },
                "source_reused": source_reused,
                "connection_reused": connection_reused,
            },
            status=status.HTTP_201_CREATED if not connection_reused else status.HTTP_200_OK,
        )


class IntegrationSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None:
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        connection = (
            AirbyteConnection.objects.filter(
                tenant_id=request.user.tenant_id,
                provider=provider_config.credential_provider,
                is_active=True,
            )
            .order_by("-updated_at")
            .first()
        )
        if connection is None:
            return Response(
                {"detail": f"No active Airbyte connection found for provider '{provider_config.slug}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with AirbyteClient.from_settings() as client:
                payload = client.trigger_sync(str(connection.connection_id))
        except AirbyteClientConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except AirbyteClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        job_id = _extract_job_id(payload)
        log_audit_event(
            tenant=request.user.tenant,
            user=request.user if request.user.is_authenticated else None,
            action="integration_sync_triggered",
            resource_type="airbyte_connection",
            resource_id=connection.id,
            metadata={
                "provider": provider_config.slug,
                "connection_id": str(connection.connection_id),
                "job_id": job_id,
            },
        )
        return Response(
            {
                "provider": provider_config.slug,
                "connection_id": str(connection.connection_id),
                "job_id": job_id,
            },
            status=status.HTTP_202_ACCEPTED if job_id else status.HTTP_200_OK,
        )


class IntegrationReconnectView(IntegrationOAuthStartView):
    permission_classes = [permissions.IsAuthenticated]


class IntegrationDisconnectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None:
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        account_filter = str(request.data.get("external_account_id") or "").strip()
        credentials = PlatformCredential.objects.filter(
            tenant_id=request.user.tenant_id,
            provider=provider_config.credential_provider,
        )
        if account_filter:
            credentials = credentials.filter(account_id=account_filter)

        connections = AirbyteConnection.objects.filter(
            tenant_id=request.user.tenant_id,
            provider=provider_config.credential_provider,
        )

        with transaction.atomic():
            credential_count = credentials.count()
            connection_count = connections.count()
            connections.update(
                is_active=False,
                last_job_status="disconnected",
                last_job_error="Disconnected by operator.",
                updated_at=timezone.now(),
            )
            credentials.delete()

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user if request.user.is_authenticated else None,
            action="integration_disconnected",
            resource_type="platform_credential",
            resource_id=provider_config.slug,
            metadata={
                "provider": provider_config.slug,
                "credential_provider": provider_config.credential_provider,
                "account_filter": account_filter or None,
                "credentials_deleted": credential_count,
                "connections_paused": connection_count,
            },
        )
        return Response(
            {
                "provider": provider_config.slug,
                "state": "disconnected",
                "credentials_deleted": credential_count,
                "connections_paused": connection_count,
            }
        )


class IntegrationJobsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None:
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        limit_raw = request.query_params.get("limit")
        try:
            limit = int(limit_raw) if limit_raw else 20
        except ValueError:
            return Response({"detail": "limit must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        limit = max(1, min(limit, 100))

        jobs = list(
            AirbyteJobTelemetry.objects.filter(
                tenant_id=request.user.tenant_id,
                connection__provider=provider_config.credential_provider,
            )
            .select_related("connection")
            .order_by("-started_at")[:limit]
        )
        payload_jobs = [
            {
                "job_id": job.job_id,
                "status": job.status,
                "started_at": job.started_at.isoformat(),
                "duration_seconds": job.duration_seconds,
                "records_synced": job.records_synced,
                "bytes_synced": job.bytes_synced,
                "api_cost": str(job.api_cost) if job.api_cost is not None else None,
                "connection": {
                    "id": str(job.connection.id),
                    "name": job.connection.name,
                    "connection_id": str(job.connection.connection_id),
                },
            }
            for job in jobs
        ]
        return Response(
            {
                "provider": provider_config.slug,
                "count": len(payload_jobs),
                "jobs": payload_jobs,
            }
        )


class IntegrationStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None:
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        credentials = list(
            PlatformCredential.objects.filter(
                tenant_id=request.user.tenant_id,
                provider=provider_config.credential_provider,
            ).order_by("-updated_at")
        )
        connections = list(
            AirbyteConnection.objects.filter(
                tenant_id=request.user.tenant_id,
                provider=provider_config.credential_provider,
            ).order_by("-updated_at")
        )
        latest_connection = connections[0] if connections else None
        state = "not_connected"
        if credentials and _credential_needs_reauth(
            credentials=credentials,
            latest_connection=latest_connection,
        ):
            state = "needs_reauth"
        elif credentials and not connections:
            state = "needs_provisioning"
        elif latest_connection is not None:
            status_value = (latest_connection.last_job_status or "").lower()
            if not latest_connection.is_active:
                state = "paused"
            elif status_value in {"failed", "error", "cancelled"} or latest_connection.last_job_error:
                state = "error"
            elif status_value in {"running", "pending", "in_progress"}:
                state = "syncing"
            else:
                state = "connected"

        return Response(
            {
                "provider": provider_config.slug,
                "label": provider_config.label,
                "state": state,
                "credentials": PlatformCredentialSerializer(credentials, many=True).data,
                "connections": AirbyteConnectionSerializer(connections, many=True).data,
                "latest_connection_id": str(latest_connection.id) if latest_connection else None,
            }
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
