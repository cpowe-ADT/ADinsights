from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from integrations.models import GoogleAnalyticsConnection, PlatformCredential

pytestmark = pytest.mark.django_db


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):  # noqa: D401
        return None

    def json(self):
        return self._payload


def test_google_analytics_setup_endpoint(api_client: APIClient, user, settings):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ANALYTICS_CLIENT_ID = "ga4-client-id"
    settings.GOOGLE_ANALYTICS_CLIENT_SECRET = "ga4-client-secret"
    settings.GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI = (
        "https://app.example.com/oauth/google-analytics/callback"
    )

    response = api_client.get("/api/integrations/google_analytics/setup/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_analytics"
    assert payload["ready_for_oauth"] is True
    assert payload["runtime_context"]["redirect_source"] == "explicit_redirect_uri"


def test_google_analytics_oauth_start_endpoint(api_client: APIClient, user, settings):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ANALYTICS_CLIENT_ID = "ga4-client-id"
    settings.GOOGLE_ANALYTICS_CLIENT_SECRET = "ga4-client-secret"
    settings.GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI = (
        "https://app.example.com/oauth/google-analytics/callback"
    )

    response = api_client.post(
        "/api/integrations/google_analytics/oauth/start/",
        {},
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["authorize_url"].startswith(
        "https://accounts.google.com/o/oauth2/v2/auth?"
    )
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert "https://www.googleapis.com/auth/analytics.readonly" in query["scope"][0]
    assert payload["state"]


def test_google_analytics_oauth_exchange_persists_credential(
    api_client: APIClient,
    user,
    settings,
    monkeypatch,
):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ANALYTICS_CLIENT_ID = "ga4-client-id"
    settings.GOOGLE_ANALYTICS_CLIENT_SECRET = "ga4-client-secret"
    settings.GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI = (
        "https://app.example.com/oauth/google-analytics/callback"
    )

    monkeypatch.setattr(
        "integrations.google_analytics.views.httpx.post",
        lambda *args, **kwargs: DummyResponse(
            {
                "access_token": "ga4-access-token",
                "refresh_token": "ga4-refresh-token",
                "expires_in": 3600,
                "scope": (
                    "https://www.googleapis.com/auth/analytics.readonly "
                    "openid https://www.googleapis.com/auth/userinfo.email"
                ),
            }
        ),
    )
    monkeypatch.setattr(
        "integrations.google_analytics.views.httpx.get",
        lambda *args, **kwargs: DummyResponse(
            {"sub": "google-user-123", "email": "ga4@example.com"}
        ),
    )

    start = api_client.post(
        "/api/integrations/google_analytics/oauth/start/",
        {},
        format="json",
    )
    assert start.status_code == 200
    state = start.json()["state"]

    response = api_client.post(
        "/api/integrations/google_analytics/oauth/exchange/",
        {"code": "oauth-code", "state": state},
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["credential"]["provider"] == PlatformCredential.GOOGLE_ANALYTICS
    assert payload["credential"]["account_id"] == "ga4@example.com"
    assert payload["refresh_token_received"] is True


def test_google_analytics_properties_endpoint_lists_properties(
    api_client: APIClient,
    user,
    monkeypatch,
):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="ga4@example.com",
    )
    credential.set_raw_tokens("ga4-access-token", "ga4-refresh-token")
    credential.save()

    monkeypatch.setattr(
        "integrations.google_analytics.views.httpx.get",
        lambda *args, **kwargs: DummyResponse(
            {
                "accountSummaries": [
                    {
                        "displayName": "Main Account",
                        "propertySummaries": [
                            {
                                "property": "properties/123456789",
                                "displayName": "Primary Property",
                            }
                        ],
                    }
                ]
            }
        ),
    )

    response = api_client.get("/api/integrations/google_analytics/properties/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["credential_id"] == str(credential.id)
    assert payload["properties"] == [
        {
            "property_id": "123456789",
            "property_name": "Primary Property",
            "account_name": "Main Account",
            "property": "properties/123456789",
        }
    ]


def test_google_analytics_properties_endpoint_paginates_and_deduplicates(
    api_client: APIClient,
    user,
    monkeypatch,
):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="ga4@example.com",
    )
    credential.set_raw_tokens("ga4-access-token", "ga4-refresh-token")
    credential.save()

    seen_page_tokens: list[str] = []
    pages = {
        "": {
            "accountSummaries": [
                {
                    "displayName": "Main Account",
                    "propertySummaries": [
                        {
                            "property": "properties/123456789",
                            "displayName": "Primary Property",
                        }
                    ],
                }
            ],
            "nextPageToken": "token-2",
        },
        "token-2": {
            "accountSummaries": [
                {
                    "displayName": "Secondary Account",
                    "propertySummaries": [
                        {
                            "property": "properties/123456789",
                            "displayName": "Primary Property Duplicate",
                        },
                        {
                            "property": "properties/987654321",
                            "displayName": "Secondary Property",
                        },
                    ],
                }
            ]
        },
    }

    def _fake_get(*args, **kwargs):  # noqa: ANN002, ANN003
        params = kwargs.get("params") or {}
        page_token = params.get("pageToken", "")
        seen_page_tokens.append(page_token)
        return DummyResponse(pages[page_token])

    monkeypatch.setattr("integrations.google_analytics.views.httpx.get", _fake_get)

    response = api_client.get("/api/integrations/google_analytics/properties/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["credential_id"] == str(credential.id)
    assert seen_page_tokens == ["", "token-2"]
    assert payload["properties"] == [
        {
            "property_id": "123456789",
            "property_name": "Primary Property",
            "account_name": "Main Account",
            "property": "properties/123456789",
        },
        {
            "property_id": "987654321",
            "property_name": "Secondary Property",
            "account_name": "Secondary Account",
            "property": "properties/987654321",
        },
    ]


def test_google_analytics_properties_endpoint_accepts_explicit_credential_id(
    api_client: APIClient,
    user,
    monkeypatch,
):
    api_client.force_authenticate(user=user)
    older = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="older@example.com",
    )
    older.set_raw_tokens("older-access-token", "older-refresh-token")
    older.save()
    selected = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="selected@example.com",
    )
    selected.set_raw_tokens("selected-access-token", "selected-refresh-token")
    selected.save()

    captured_authorizations: list[str] = []

    def _fake_get(*args, **kwargs):  # noqa: ANN002, ANN003
        captured_authorizations.append(kwargs["headers"]["Authorization"])
        return DummyResponse(
            {
                "accountSummaries": [
                    {
                        "displayName": "Selected Account",
                        "propertySummaries": [
                            {
                                "property": "properties/222222222",
                                "displayName": "Selected Property",
                            }
                        ],
                    }
                ]
            }
        )

    monkeypatch.setattr("integrations.google_analytics.views.httpx.get", _fake_get)

    response = api_client.get(
        "/api/integrations/google_analytics/properties/",
        {"credential_id": str(selected.id)},
    )

    assert response.status_code == 200
    assert response.json()["credential_id"] == str(selected.id)
    assert captured_authorizations == ["Bearer selected-access-token"]


def test_google_analytics_provision_creates_connection(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="ga4@example.com",
    )
    credential.set_raw_tokens("ga4-access-token", "ga4-refresh-token")
    credential.save()

    response = api_client.post(
        "/api/integrations/google_analytics/provision/",
        {
            "credential_id": str(credential.id),
            "property_id": "123456789",
            "property_name": "Primary Property",
            "sync_frequency": "daily",
        },
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["connection"]["property_id"] == "123456789"
    assert payload["connection"]["credential_id"] == str(credential.id)

    connection = GoogleAnalyticsConnection.objects.get(
        tenant=user.tenant,
        property_id="123456789",
    )
    assert connection.property_name == "Primary Property"
    assert connection.credentials_id == credential.id


def test_google_analytics_provision_deactivates_previous_active_connection(
    api_client: APIClient,
    user,
):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="ga4@example.com",
    )
    credential.set_raw_tokens("ga4-access-token", "ga4-refresh-token")
    credential.save()
    previous = GoogleAnalyticsConnection.objects.create(
        tenant=user.tenant,
        credentials=credential,
        property_id="111111111",
        property_name="Legacy Property",
        is_active=True,
        sync_frequency="daily",
    )

    response = api_client.post(
        "/api/integrations/google_analytics/provision/",
        {
            "credential_id": str(credential.id),
            "property_id": "123456789",
            "property_name": "Primary Property",
            "sync_frequency": "daily",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 201
    previous.refresh_from_db()
    assert previous.is_active is False
    assert (
        GoogleAnalyticsConnection.objects.filter(tenant=user.tenant, is_active=True).count() == 1
    )


def test_google_analytics_status_endpoint_reports_active_connection(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="ga4@example.com",
    )
    credential.set_raw_tokens("ga4-access-token", "ga4-refresh-token")
    credential.save()
    connection = GoogleAnalyticsConnection.objects.create(
        tenant=user.tenant,
        credentials=credential,
        property_id="123456789",
        property_name="Primary Property",
        is_active=True,
        sync_frequency="daily",
        last_synced_at=timezone.now() - timedelta(hours=2),
    )

    response = api_client.get("/api/integrations/google_analytics/status/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_analytics"
    assert payload["status"] == "active"
    assert payload["metadata"] == {
        "has_credential": True,
        "has_connection": True,
    }
    assert payload["last_synced_at"] == connection.last_synced_at.isoformat().replace("+00:00", "Z")


def test_google_analytics_status_prefers_latest_active_connection(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="ga4@example.com",
    )
    credential.set_raw_tokens("ga4-access-token", "ga4-refresh-token")
    credential.save()
    GoogleAnalyticsConnection.objects.create(
        tenant=user.tenant,
        credentials=credential,
        property_id="111111111",
        property_name="Paused Property",
        is_active=False,
        sync_frequency="daily",
        last_synced_at=timezone.now() - timedelta(days=4),
    )
    active_connection = GoogleAnalyticsConnection.objects.create(
        tenant=user.tenant,
        credentials=credential,
        property_id="123456789",
        property_name="Primary Property",
        is_active=True,
        sync_frequency="daily",
        last_synced_at=timezone.now() - timedelta(hours=3),
    )

    response = api_client.get("/api/integrations/google_analytics/status/")

    assert response.status_code == 200
    assert response.json()["last_synced_at"] == active_connection.last_synced_at.isoformat().replace(
        "+00:00",
        "Z",
    )
