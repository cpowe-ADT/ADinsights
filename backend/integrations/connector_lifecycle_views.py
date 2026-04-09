from __future__ import annotations

from datetime import timedelta
import logging
import secrets
import uuid
from typing import Any, Mapping

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
from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from integrations.google_oauth import (
    GoogleOAuthClient,
    GoogleOAuthClientError,
    GoogleOAuthConfigurationError,
)
from integrations.models import AirbyteConnection, AirbyteJobTelemetry, PlatformCredential
from integrations.provider_registry import get_provider
from integrations.serializers import (
    AirbyteConnectionSerializer,
    IntegrationOAuthCallbackSerializer,
    IntegrationProvisionSerializer,
    PlatformCredentialSerializer,
)

logger = logging.getLogger(__name__)

INTEGRATION_OAUTH_STATE_SALT = "integrations.oauth.state"
INTEGRATION_OAUTH_STATE_MAX_AGE_SECONDS = 600
DEFAULT_CONNECTOR_CRON_EXPRESSION = "0 6-22 * * *"
DEFAULT_CONNECTOR_TIMEZONE = "America/Jamaica"
DEFAULT_GOOGLE_ADS_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
DEFAULT_GA4_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
DEFAULT_SEARCH_CONSOLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
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


def _is_unset_or_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if not normalized:
        return True
    lowered = normalized.lower()
    return lowered.startswith("replace_") or lowered in {"replace-me", "changeme"} or "placeholder" in lowered


def _setting_first(*names: str) -> str:
    for name in names:
        value = getattr(settings, name, "")
        if _is_unset_or_placeholder(value):
            continue
        return str(value).strip()
    return ""


def _resolve_google_oauth_env(provider_slug: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if provider_slug == "google_ads":
        return (
            ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_ID"),
            ("GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_OAUTH_CLIENT_SECRET"),
            ("GOOGLE_ADS_OAUTH_REDIRECT_URI", "GOOGLE_OAUTH_REDIRECT_URI"),
        )
    if provider_slug == "ga4":
        return (
            ("GOOGLE_ANALYTICS_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_ID"),
            ("GOOGLE_ANALYTICS_CLIENT_SECRET", "GOOGLE_OAUTH_CLIENT_SECRET"),
            ("GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI", "GOOGLE_OAUTH_REDIRECT_URI"),
        )
    if provider_slug == "search_console":
        return (
            ("GOOGLE_SEARCH_CONSOLE_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_ID"),
            ("GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET", "GOOGLE_OAUTH_CLIENT_SECRET"),
            ("GOOGLE_SEARCH_CONSOLE_OAUTH_REDIRECT_URI", "GOOGLE_OAUTH_REDIRECT_URI"),
        )
    raise GoogleOAuthConfigurationError("Unsupported provider.")


def _provider_label(provider_slug: str) -> str:
    provider = get_provider(provider_slug)
    return provider.label if provider is not None else provider_slug


def _resolve_google_redirect_uri(
    *,
    provider_slug: str,
    request=None,  # noqa: ANN001 - DRF request
    payload: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    _, _, redirect_env_names = _resolve_google_oauth_env(provider_slug)
    runtime_context_origin = extract_runtime_client_origin(request=request, payload=payload)
    explicit_redirect_uri = _setting_first(*redirect_env_names)

    try:
        redirect_uri, resolution, redirect_source = resolve_frontend_redirect_uri(
            path="/dashboards/data-sources",
            explicit_redirect_uri=explicit_redirect_uri,
            request=request,
            runtime_context_origin=runtime_context_origin,
            missing_message=(
                f"{'/'.join(redirect_env_names)} or FRONTEND_BASE_URL must be configured "
                f"for {_provider_label(provider_slug)} OAuth."
            ),
        )
    except ValueError as exc:
        raise GoogleOAuthConfigurationError(str(exc)) from exc

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


def _resolve_google_oauth_client(
    *,
    provider_slug: str,
    request=None,  # noqa: ANN001 - DRF request
    payload: Mapping[str, Any] | None = None,
) -> tuple[GoogleOAuthClient, dict[str, Any]]:
    client_id, client_secret = _resolve_google_client_credentials(provider_slug)
    redirect_uri, runtime_context = _resolve_google_redirect_uri(
        provider_slug=provider_slug,
        request=request,
        payload=payload,
    )
    return (
        GoogleOAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        ),
        runtime_context,
    )


def _resolve_google_client_credentials(provider_slug: str) -> tuple[str, str]:
    client_id_env_names, client_secret_env_names, _ = _resolve_google_oauth_env(provider_slug)
    client_id = _setting_first(*client_id_env_names)
    client_secret = _setting_first(*client_secret_env_names)
    if not client_id or not client_secret:
        env_names = ", ".join(client_id_env_names + client_secret_env_names)
        raise GoogleOAuthConfigurationError(
            f"{env_names} are required for {_provider_label(provider_slug)} OAuth."
        )
    return client_id, client_secret


def _resolve_google_scopes(provider_slug: str) -> list[str]:
    if provider_slug == "google_ads":
        configured = getattr(settings, "GOOGLE_OAUTH_SCOPES_GOOGLE_ADS", DEFAULT_GOOGLE_ADS_OAUTH_SCOPES)
        defaults = DEFAULT_GOOGLE_ADS_OAUTH_SCOPES
    elif provider_slug == "ga4":
        configured = getattr(
            settings,
            "GOOGLE_OAUTH_SCOPES_GA4",
            getattr(settings, "GOOGLE_ANALYTICS_OAUTH_SCOPES", DEFAULT_GA4_OAUTH_SCOPES),
        )
        defaults = DEFAULT_GA4_OAUTH_SCOPES
    elif provider_slug == "search_console":
        configured = getattr(
            settings,
            "GOOGLE_OAUTH_SCOPES_SEARCH_CONSOLE",
            DEFAULT_SEARCH_CONSOLE_OAUTH_SCOPES,
        )
        defaults = DEFAULT_SEARCH_CONSOLE_OAUTH_SCOPES
    else:
        return []

    candidates = configured if isinstance(configured, list) else defaults
    scopes: list[str] = []
    seen: set[str] = set()
    for raw_scope in candidates:
        if not isinstance(raw_scope, str):
            continue
        scope = raw_scope.strip()
        if not scope or scope in seen:
            continue
        seen.add(scope)
        scopes.append(scope)
    return scopes or list(defaults)


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

    if payload.get("user_id") != str(request.user.id) or payload.get("tenant_id") != str(request.user.tenant_id):
        return {}, Response(
            {"detail": "OAuth state does not match the authenticated tenant user."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return payload, None


def _normalize_google_account_id(provider_slug: str, raw_value: str) -> str:
    normalized = (raw_value or "").strip()
    if provider_slug == "google_ads":
        digits = "".join(ch for ch in normalized if ch.isdigit())
        return digits or normalized
    return normalized


def _discover_google_account_id(*, access_token: str) -> str | None:
    try:
        response = httpx.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    payload = response.json()
    if not isinstance(payload, dict):
        return None
    for key in ("email", "sub"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


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
            destination_sync_mode = (
                "overwrite" if "overwrite" in supported_dest_modes else supported_dest_modes[0]
            )

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
                    cron_expression or DEFAULT_CONNECTOR_CRON_EXPRESSION
                ),
                "cronTimeZone": DEFAULT_CONNECTOR_TIMEZONE,
            }
        },
    }


def _resolve_source_definition_id(provider_slug: str, requested_id: str | None) -> str:
    if requested_id:
        return requested_id
    provider = get_provider(provider_slug)
    if provider is not None and provider.source_definition_id:
        return provider.source_definition_id
    if provider_slug == "ga4":
        configured = _setting_first("AIRBYTE_SOURCE_DEFINITION_GA4")
        if configured:
            return configured
        raise ValueError("Set AIRBYTE_SOURCE_DEFINITION_GA4 or pass source_definition_id.")
    if provider_slug == "search_console":
        configured = _setting_first("AIRBYTE_SOURCE_DEFINITION_SEARCH_CONSOLE")
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

    if provider_slug == "google_ads":
        developer_token = _setting_first("AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN")
        login_customer_id = _setting_first("AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID")
        client_id, client_secret = _resolve_google_client_credentials(provider_slug)
        if not developer_token:
            raise ValueError("AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN is required for Google Ads provisioning.")
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

    client_id, client_secret = _resolve_google_client_credentials(provider_slug)
    if not refresh_token:
        raise ValueError(f"{_provider_label(provider_slug)} provisioning requires a refresh token.")
    if provider_slug == "ga4":
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
    if provider_slug == "google_ads":
        candidates = [str(config.get("customer_id") or "")]
    elif provider_slug == "ga4":
        candidates = [str(config.get("property_id") or "")]
    elif provider_slug == "search_console":
        candidates = [str(config.get("site_url") or "")]
    else:
        candidates = []
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
    return str(connection.get("sourceId") or "") == source_id and str(connection.get("destinationId") or "") == destination_id


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


def _logged_error_response(
    *,
    detail: str,
    status_code: int,
    log_message: str,
    provider_slug: str | None = None,
) -> Response:
    extra: dict[str, Any] = {}
    if provider_slug is not None:
        extra["provider"] = provider_slug
    logger.warning(log_message, extra=extra, exc_info=True)
    return Response({"detail": detail}, status=status_code)


def _airbyte_error_response(exc: Exception) -> Response:
    if isinstance(exc, AirbyteClientConfigurationError):
        return _logged_error_response(
            detail="Airbyte is not configured for this environment.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            log_message="Airbyte connector lifecycle request failed due to missing configuration.",
        )
    return _logged_error_response(
        detail="Airbyte request failed while processing the connector lifecycle operation.",
        status_code=status.HTTP_502_BAD_GATEWAY,
        log_message="Airbyte connector lifecycle request failed.",
    )


def _provision_validation_detail(exc: ValueError) -> str:
    message = str(exc)
    if "source_configuration must be an object" in message:
        return "source_configuration must be an object when provided."
    if "source definition" in message:
        return "Source definition is not configured for this provider."
    if "refresh token" in message or "access token" in message:
        return "Reconnect this provider before provisioning."
    if "developer token" in message:
        return "Google Ads provisioning is missing the required developer token."
    if "Multiple Airbyte sources match" in message:
        return "Multiple Airbyte sources already match this provider/account. Clean them up or choose a unique connection_name."
    if "different source/destination" in message:
        return "connection_name is already used by a different Airbyte source/destination."
    if "missing sourceId" in message:
        return "Airbyte source response is missing sourceId."
    if "did not return a catalog" in message or "catalog has no streams" in message:
        return "Airbyte schema discovery did not return a valid catalog."
    return "Connector provisioning request is invalid."


class IntegrationOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None or provider_config.oauth_family != "google":
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        signed_state = _sign_integration_state(request=request, provider_slug=provider_config.slug)
        try:
            oauth_client, runtime_context = _resolve_google_oauth_client(
                provider_slug=provider_config.slug,
                request=request,
                payload=request.data or {},
            )
            authorize_url = oauth_client.build_authorize_url(
                state=signed_state,
                scopes=_resolve_google_scopes(provider_config.slug),
            )
        except GoogleOAuthConfigurationError:
            return _logged_error_response(
                detail="Google OAuth is not configured for this provider.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                log_message="Integration OAuth start failed due to missing Google OAuth configuration.",
                provider_slug=provider_config.slug,
            )

        return Response(
            {
                "provider": provider_config.slug,
                "authorize_url": authorize_url,
                "state": signed_state,
                "redirect_uri": oauth_client.redirect_uri,
                "runtime_context": runtime_context,
            }
        )


class IntegrationOAuthCallbackView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None or provider_config.oauth_family != "google":
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

        try:
            oauth_client, _ = _resolve_google_oauth_client(
                provider_slug=provider_config.slug,
                request=request,
                payload=serializer.validated_data,
            )
            token = oauth_client.exchange_code(code=serializer.validated_data["code"])
        except GoogleOAuthConfigurationError:
            return _logged_error_response(
                detail="Google OAuth is not configured for this provider.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                log_message="Integration OAuth callback failed due to missing Google OAuth configuration.",
                provider_slug=provider_config.slug,
            )
        except GoogleOAuthClientError:
            return _logged_error_response(
                detail="Google OAuth exchange failed for this provider.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                log_message="Integration OAuth callback failed during code exchange.",
                provider_slug=provider_config.slug,
            )

        account_id = _normalize_google_account_id(
            provider_config.slug,
            str(serializer.validated_data.get("external_account_id") or ""),
        )
        if not account_id:
            account_id = _discover_google_account_id(access_token=token.access_token) or "default"

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
                "refresh_token_received": bool(token.refresh_token),
            }
        )


class IntegrationProvisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider: str):
        provider_config = get_provider(provider)
        if provider_config is None or provider_config.oauth_family != "google":
            return Response({"detail": "Unsupported provider."}, status=status.HTTP_404_NOT_FOUND)

        serializer = IntegrationProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        account_filter = _normalize_google_account_id(
            provider_config.slug,
            str(validated.get("external_account_id") or ""),
        )
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
        except GoogleOAuthConfigurationError:
            return _logged_error_response(
                detail="Google OAuth is not configured for this provider.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                log_message="Integration provisioning failed due to missing Google OAuth configuration.",
                provider_slug=provider_config.slug,
            )
        except ValueError as exc:
            return _logged_error_response(
                detail=_provision_validation_detail(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                log_message="Integration provisioning request was invalid.",
                provider_slug=provider_config.slug,
            )

        source_reused = False
        connection_reused = False
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
                        source = client.create_source(
                            {
                                "workspaceId": str(workspace_id),
                                "name": source_name,
                                "sourceDefinitionId": resolved_source_definition_id,
                                "connectionConfiguration": source_configuration,
                            }
                        )
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
                        airbyte_connection = client.create_connection(
                            {
                                "name": connection_name,
                                "workspaceId": str(workspace_id),
                                "sourceId": str(source_id),
                                "destinationId": str(destination_id),
                                "status": "active" if bool(validated.get("is_active", True)) else "inactive",
                                "syncCatalog": sync_catalog,
                                "prefix": "",
                                **_schedule_payload(
                                    schedule_type=str(validated["schedule_type"]),
                                    interval_minutes=validated.get("interval_minutes"),
                                    cron_expression=str(validated.get("cron_expression") or ""),
                                ),
                            }
                        )
                    else:
                        airbyte_connection = existing_connection
        except (AirbyteClientConfigurationError, AirbyteClientError) as exc:
            return _airbyte_error_response(exc)
        except ValueError as exc:
            return _logged_error_response(
                detail=_provision_validation_detail(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                log_message="Integration provisioning request failed validation during Airbyte setup.",
                provider_slug=provider_config.slug,
            )

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
        except (AirbyteClientConfigurationError, AirbyteClientError) as exc:
            return _airbyte_error_response(exc)

        job_id = _extract_job_id(payload)
        if job_id:
            connection.last_job_id = job_id
            connection.last_job_status = "queued"
            connection.last_job_created_at = timezone.now()
            connection.updated_at = timezone.now()
            connection.save(
                update_fields=[
                    "last_job_id",
                    "last_job_status",
                    "last_job_created_at",
                    "updated_at",
                ]
            )

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

        account_filter = _normalize_google_account_id(
            provider_config.slug,
            str(request.data.get("external_account_id") or ""),
        )
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

        now = timezone.now()
        with transaction.atomic():
            credential_count = credentials.count()
            connection_count = connections.count()
            connections.update(
                is_active=False,
                last_job_status="disconnected",
                last_job_error="Disconnected by operator.",
                updated_at=now,
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
            elif status_value in {"running", "pending", "queued", "in_progress"}:
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
