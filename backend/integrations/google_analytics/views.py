from __future__ import annotations

import logging
import secrets
from datetime import timedelta
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

from core.frontend_runtime import (
    build_runtime_context,
    extract_dataset_source,
    extract_runtime_client_origin,
    resolve_frontend_redirect_uri,
)
from integrations.models import GoogleAnalyticsConnection, PlatformCredential
from integrations.serializers import PlatformCredentialSerializer
from integrations.google_analytics_serializers import (
    GoogleAnalyticsConnectionSerializer,
    GoogleAnalyticsOAuthExchangeSerializer,
    GoogleAnalyticsOAuthStartSerializer,
    GoogleAnalyticsPropertiesQuerySerializer,
    GoogleAnalyticsProvisionSerializer,
)

logger = logging.getLogger(__name__)

GA4_OAUTH_STATE_SALT = "integrations.google_analytics.oauth.state"
GA4_OAUTH_STATE_MAX_AGE_SECONDS = 600
DEFAULT_GA4_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_ANALYTICS_ACCOUNT_SUMMARIES_URL = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"
GA4_ACCOUNT_SUMMARIES_PAGE_SIZE = 200
GA4_ACCOUNT_SUMMARIES_MAX_PAGES = 10


def _resolve_ga4_redirect_uri(
    *,
    request=None,
    payload: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    runtime_context_origin = extract_runtime_client_origin(request=request, payload=payload)
    redirect_uri, resolution, redirect_source = resolve_frontend_redirect_uri(
        path="/dashboards/data-sources",
        explicit_redirect_uri=(getattr(settings, "GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI", "") or "").strip(),
        request=request,
        runtime_context_origin=runtime_context_origin,
        missing_message=(
            "GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI or FRONTEND_BASE_URL must be configured for GA4 OAuth."
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


def _ga4_oauth_scopes() -> list[str]:
    configured = getattr(settings, "GOOGLE_ANALYTICS_OAUTH_SCOPES", DEFAULT_GA4_OAUTH_SCOPES)
    return list(configured) if isinstance(configured, list) else list(DEFAULT_GA4_OAUTH_SCOPES)


def _credential_bearer_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _ga4_account_id_from_userinfo(payload: dict[str, Any]) -> str | None:
    for key in ("email", "sub"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_property_summaries(payload: dict[str, Any]) -> list[dict[str, str]]:
    properties: list[dict[str, str]] = []
    raw_summaries = payload.get("accountSummaries")
    if not isinstance(raw_summaries, list):
        return properties

    for account_summary in raw_summaries:
        if not isinstance(account_summary, dict):
            continue
        account_name = str(account_summary.get("displayName") or "").strip()
        property_summaries = account_summary.get("propertySummaries")
        if not isinstance(property_summaries, list):
            continue
        for property_summary in property_summaries:
            if not isinstance(property_summary, dict):
                continue
            property_ref = str(property_summary.get("property") or "").strip()
            property_name = str(property_summary.get("displayName") or "").strip()
            property_id = property_ref.removeprefix("properties/") if property_ref else ""
            if not property_id:
                continue
            properties.append(
                {
                    "property": property_ref,
                    "property_id": property_id,
                    "property_name": property_name or property_id,
                    "account_name": account_name,
                }
            )
    return properties


def _discover_ga4_properties(*, access_token: str) -> list[dict[str, str]]:
    page_token = ""
    discovered: list[dict[str, str]] = []
    seen_property_ids: set[str] = set()

    for _ in range(GA4_ACCOUNT_SUMMARIES_MAX_PAGES):
        params: dict[str, Any] = {"pageSize": GA4_ACCOUNT_SUMMARIES_PAGE_SIZE}
        if page_token:
            params["pageToken"] = page_token

        try:
            properties_response = httpx.get(
                GOOGLE_ANALYTICS_ACCOUNT_SUMMARIES_URL,
                params=params,
                headers=_credential_bearer_headers(access_token),
                timeout=30.0,
            )
            properties_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Property discovery failed: {exc}") from exc

        payload = properties_response.json()
        for property_summary in _normalize_property_summaries(payload):
            property_id = property_summary["property_id"]
            if property_id in seen_property_ids:
                continue
            seen_property_ids.add(property_id)
            discovered.append(property_summary)

        next_page_token = payload.get("nextPageToken")
        if not isinstance(next_page_token, str) or not next_page_token.strip():
            break
        page_token = next_page_token.strip()

    return discovered


def _sign_ga4_state(*, request) -> str:
    payload = {
        "tenant_id": str(request.user.tenant_id),
        "user_id": str(request.user.id),
        "nonce": secrets.token_urlsafe(24),
        "flow": "google_analytics",
    }
    return signing.dumps(payload, salt=GA4_OAUTH_STATE_SALT)


def _validate_ga4_state(*, request, state: str) -> tuple[dict[str, Any], Response | None]:
    try:
        payload = signing.loads(
            state,
            salt=GA4_OAUTH_STATE_SALT,
            max_age=GA4_OAUTH_STATE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired:
        return {}, Response(
            {"detail": "GA4 OAuth state expired. Restart the connect flow."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except signing.BadSignature:
        return {}, Response(
            {"detail": "GA4 OAuth state is invalid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if payload.get("user_id") != str(request.user.id) or payload.get("tenant_id") != str(request.user.tenant_id):
        return {}, Response(
            {"detail": "GA4 OAuth state mismatch."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return payload, None


class GoogleAnalyticsSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        client_id = (getattr(settings, "GOOGLE_ANALYTICS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ANALYTICS_CLIENT_SECRET", "") or "").strip()

        try:
            redirect_uri, runtime_context = _resolve_ga4_redirect_uri(request=request, payload=request.GET)
            redirect_configured = True
        except ValueError:
            redirect_uri, runtime_context, redirect_configured = None, None, False
        runtime_redirect_ready = (
            runtime_context.get("redirect_origin_matches_runtime") is not False
            if runtime_context is not None
            else True
        )

        return Response({
            "provider": "google_analytics",
            "ready_for_oauth": bool(
                client_id and client_secret and redirect_configured and runtime_redirect_ready
            ),
            "oauth_scopes": _ga4_oauth_scopes(),
            "redirect_uri": redirect_uri,
            "runtime_context": runtime_context,
            "checks": [
                {
                    "key": "ga4_runtime_redirect_origin",
                    "label": "Open the app on the same host as the configured OAuth redirect",
                    "ok": runtime_redirect_ready,
                    "details": (
                        runtime_context.get("redirect_origin_mismatch_message")
                        if runtime_context is not None
                        else None
                    ),
                }
            ],
        })


class GoogleAnalyticsOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = GoogleAnalyticsOAuthStartSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        client_id = (getattr(settings, "GOOGLE_ANALYTICS_CLIENT_ID", "") or "").strip()
        if not client_id:
            return Response({"detail": "GA4 Client ID not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            redirect_uri, runtime_context = _resolve_ga4_redirect_uri(
                request=request,
                payload=serializer.validated_data,
            )
            if runtime_context.get("redirect_origin_matches_runtime") is False:
                return Response(
                    {
                        "detail": runtime_context.get("redirect_origin_mismatch_message")
                        or "Open the app on the configured OAuth redirect host and try again.",
                        "runtime_context": runtime_context,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        signed_state = _sign_ga4_state(request=request)
        query = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(_ga4_oauth_scopes()),
            "state": signed_state,
            "access_type": "offline",
            "prompt": serializer.validated_data.get("prompt") or "consent",
        }
        return Response({
            "authorize_url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(query)}",
            "state": signed_state,
        })


class GoogleAnalyticsOAuthExchangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = GoogleAnalyticsOAuthExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        _, state_error = _validate_ga4_state(request=request, state=serializer.validated_data["state"])
        if state_error:
            return state_error

        client_id = (getattr(settings, "GOOGLE_ANALYTICS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ANALYTICS_CLIENT_SECRET", "") or "").strip()
        
        try:
            redirect_uri, _ = _resolve_ga4_redirect_uri(request=request, payload=serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        token_payload = {
            "code": serializer.validated_data["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        
        try:
            token_response = httpx.post("https://oauth2.googleapis.com/token", data=token_payload, timeout=30.0)
            token_response.raise_for_status()
        except httpx.HTTPError as exc:
            return Response({"detail": f"Token exchange failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        payload = token_response.json()
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        scope_value = payload.get("scope")

        try:
            userinfo_response = httpx.get(
                GOOGLE_USERINFO_URL,
                headers=_credential_bearer_headers(access_token),
                timeout=30.0,
            )
            userinfo_response.raise_for_status()
        except httpx.HTTPError as exc:
            return Response(
                {"detail": f"User profile lookup failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        userinfo = userinfo_response.json()
        account_id = _ga4_account_id_from_userinfo(userinfo)
        if not account_id:
            return Response(
                {"detail": "Unable to determine Google Analytics account identity."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        expires_at = timezone.now() + timedelta(seconds=int(expires_in)) if expires_in else None

        with transaction.atomic():
            credential = (
                PlatformCredential.objects.select_for_update()
                .filter(
                    tenant=request.user.tenant,
                    provider=PlatformCredential.GOOGLE_ANALYTICS,
                    account_id=account_id,
                )
                .first()
            )
            if credential is None:
                credential = PlatformCredential(
                    tenant=request.user.tenant,
                    provider=PlatformCredential.GOOGLE_ANALYTICS,
                    account_id=account_id,
                )
            credential.expires_at = expires_at
            credential.issued_at = credential.issued_at or timezone.now()
            credential.last_validated_at = timezone.now()
            credential.granted_scopes = (
                [scope for scope in scope_value.split() if scope]
                if isinstance(scope_value, str)
                else []
            )
            credential.set_raw_tokens(access_token, refresh_token)
            credential.save()

        return Response({
            "credential": PlatformCredentialSerializer(credential).data,
            "refresh_token_received": bool(refresh_token),
        }, status=status.HTTP_201_CREATED)


class GoogleAnalyticsPropertiesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = GoogleAnalyticsPropertiesQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        credentials = PlatformCredential.objects.filter(
            tenant=request.user.tenant,
            provider=PlatformCredential.GOOGLE_ANALYTICS,
        )
        credential_id = serializer.validated_data.get("credential_id")
        if credential_id is not None:
            credential = credentials.filter(id=credential_id).first()
        else:
            credential = (
                credentials.order_by("-updated_at")
                .first()
            )

        if credential is None:
            return Response({"detail": "Credential not found."}, status=status.HTTP_400_BAD_REQUEST)

        access_token = credential.decrypt_access_token()
        if not access_token:
            return Response(
                {"detail": "Credential access token is unavailable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            properties = _discover_ga4_properties(access_token=access_token)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "credential_id": str(credential.id),
                "properties": properties,
            }
        )


class GoogleAnalyticsProvisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = GoogleAnalyticsProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        credential = PlatformCredential.objects.filter(
            tenant=request.user.tenant,
            provider=PlatformCredential.GOOGLE_ANALYTICS,
            id=serializer.validated_data["credential_id"],
        ).first()

        if not credential:
            return Response({"detail": "Credential not found."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            connection, _ = GoogleAnalyticsConnection.objects.update_or_create(
                tenant=request.user.tenant,
                property_id=serializer.validated_data["property_id"],
                defaults={
                    "credentials": credential,
                    "property_name": serializer.validated_data["property_name"],
                    "is_active": serializer.validated_data.get("is_active", True),
                    "sync_frequency": serializer.validated_data.get("sync_frequency", "daily"),
                }
            )
            if connection.is_active:
                GoogleAnalyticsConnection.objects.filter(
                    tenant=request.user.tenant,
                    is_active=True,
                ).exclude(id=connection.id).update(
                    is_active=False,
                    updated_at=timezone.now(),
                )

        return Response(
            {"connection": GoogleAnalyticsConnectionSerializer(connection).data},
            status=status.HTTP_201_CREATED,
        )


class GoogleAnalyticsStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        credential = PlatformCredential.objects.filter(
            tenant=request.user.tenant, 
            provider=PlatformCredential.GOOGLE_ANALYTICS
        ).first()
        connection = (
            GoogleAnalyticsConnection.objects.filter(
                tenant=request.user.tenant,
                is_active=True,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )
        if connection is None:
            connection = (
                GoogleAnalyticsConnection.objects.filter(tenant=request.user.tenant)
                .order_by("-updated_at", "-created_at")
                .first()
            )

        status_val = "not_connected"
        if credential:
            status_val = "complete" if connection else "started_not_complete"
            if connection and connection.is_active and connection.last_synced_at:
                if now - connection.last_synced_at < timedelta(hours=25):
                    status_val = "active"

        payload = {
            "provider": "google_analytics",
            "status": status_val,
            "reason": {"message": "System check complete"},
            "actions": ["connect_oauth"] if status_val == "not_connected" else ["view"],
            "last_checked_at": now,
            "last_synced_at": connection.last_synced_at if connection else None,
            "metadata": {
                "has_credential": bool(credential),
                "has_connection": bool(connection),
            }
        }
        return Response(payload)
