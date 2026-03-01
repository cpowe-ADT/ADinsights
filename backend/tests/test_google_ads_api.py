from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from rest_framework.test import APIClient

from integrations.models import AirbyteConnection, GoogleAdsSyncState, PlatformCredential

pytestmark = pytest.mark.django_db


def test_google_ads_setup_endpoint(api_client: APIClient, user, settings):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ADS_CLIENT_ID = "google-client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_ADS_DEVELOPER_TOKEN = "google-dev-token"
    settings.GOOGLE_ADS_OAUTH_REDIRECT_URI = "https://app.example.com/oauth/google/callback"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "11111111-2222-3333-4444-555555555555"
    settings.AIRBYTE_SOURCE_DEFINITION_GOOGLE = "0b29e8f7-f64c-4a24-9e97-07c4603f8c04"

    response = api_client.get("/api/integrations/google_ads/setup/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert payload["ready_for_oauth"] is True
    assert payload["ready_for_provisioning_defaults"] is True
    assert payload["source_definition_id"] == "0b29e8f7-f64c-4a24-9e97-07c4603f8c04"
    assert payload["runtime_context"]["redirect_source"] == "explicit_redirect_uri"


def test_google_ads_oauth_start_endpoint(api_client: APIClient, user, settings):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ADS_CLIENT_ID = "google-client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_ADS_OAUTH_REDIRECT_URI = "https://app.example.com/oauth/google/callback"

    response = api_client.post("/api/integrations/google_ads/oauth/start/", {}, format="json")
    assert response.status_code == 200
    payload = response.json()
    assert "authorize_url" in payload
    assert payload["authorize_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert payload["state"]


def test_google_ads_oauth_start_uses_localhost_origin_when_redirect_not_explicit(
    api_client: APIClient,
    user,
    settings,
):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ADS_CLIENT_ID = "google-client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_ADS_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post(
        "/api/integrations/google_ads/oauth/start/",
        {},
        format="json",
        HTTP_ORIGIN="http://localhost:5175",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == "http://localhost:5175/dashboards/data-sources"
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert query["redirect_uri"] == ["http://localhost:5175/dashboards/data-sources"]


def test_google_ads_oauth_start_falls_back_to_frontend_base_without_origin(
    api_client: APIClient,
    user,
    settings,
):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ADS_CLIENT_ID = "google-client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_ADS_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post("/api/integrations/google_ads/oauth/start/", {}, format="json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"


def test_google_ads_oauth_start_ignores_non_local_origin_for_redirect(
    api_client: APIClient,
    user,
    settings,
):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ADS_CLIENT_ID = "google-client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_ADS_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post(
        "/api/integrations/google_ads/oauth/start/",
        {},
        format="json",
        HTTP_ORIGIN="https://app.example.com",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert query["redirect_uri"] == ["http://localhost:5173/dashboards/data-sources"]


def test_google_ads_oauth_exchange_persists_credential(api_client: APIClient, user, settings, monkeypatch):
    api_client.force_authenticate(user=user)
    settings.GOOGLE_ADS_CLIENT_ID = "google-client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_ADS_OAUTH_REDIRECT_URI = "https://app.example.com/oauth/google/callback"

    class DummyResponse:
        def raise_for_status(self):  # noqa: D401
            return None

        def json(self):
            return {
                "access_token": "google-access-token",
                "refresh_token": "google-refresh-token",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/adwords openid",
            }

    monkeypatch.setattr("integrations.google_ads_views.httpx.post", lambda *args, **kwargs: DummyResponse())

    start = api_client.post("/api/integrations/google_ads/oauth/start/", {}, format="json")
    assert start.status_code == 200
    state = start.json()["state"]

    response = api_client.post(
        "/api/integrations/google_ads/oauth/exchange/",
        {
            "code": "oauth-code",
            "state": state,
            "customer_id": "123-456-7890",
            "login_customer_id": "123-456-7890",
        },
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["credential"]["provider"] == PlatformCredential.GOOGLE
    assert payload["credential"]["account_id"] == "1234567890"
    assert payload["refresh_token_received"] is True


def test_google_ads_status_not_connected(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/integrations/google_ads/status/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert payload["status"] == "not_connected"
    assert payload["sync_engine"] == "airbyte"
    assert payload["parity_state"] == "unknown"


def test_google_ads_reference_summary_endpoint(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/integrations/google_ads/reference/summary/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert payload["service_catalog"]["available"] is True
    assert payload["query_reference"]["available"] is True
    assert payload["fields_reference"]["available"] is True
    assert payload["fields_reference"]["counts"]["segments"] >= 1
    assert payload["fields_reference"]["counts"]["metrics"] >= 1


def test_google_ads_sync_triggers_airbyte(api_client: APIClient, user, monkeypatch):
    api_client.force_authenticate(user=user)
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        name="Google Ads Tenant Connection",
        connection_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        is_active=True,
    )

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return None

        def trigger_sync(self, connection_id):  # noqa: ANN001
            return {"job": {"id": 77}}

    monkeypatch.setattr("integrations.google_ads_views.AirbyteClient.from_settings", lambda: DummyClient())

    response = api_client.post("/api/integrations/google_ads/sync/", {}, format="json")
    assert response.status_code == 202
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert payload["sync_engine"] == "airbyte"
    assert payload["job_id"] == "77"
    connection.refresh_from_db()
    assert connection.last_job_id == "77"


def test_google_ads_sync_triggers_sdk_when_state_is_sdk(api_client: APIClient, user, monkeypatch):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    credential.set_raw_tokens("token-access", "token-refresh")
    credential.save()
    GoogleAdsSyncState.objects.create(
        tenant=user.tenant,
        account_id="1234567890",
        desired_engine=GoogleAdsSyncState.ENGINE_SDK,
        effective_engine=GoogleAdsSyncState.ENGINE_SDK,
        fallback_active=False,
    )

    class DummyAsyncResult:
        id = "sdk-task-123"

    monkeypatch.setattr(
        "integrations.google_ads_views.sync_google_ads_sdk_incremental.delay",
        lambda *args, **kwargs: DummyAsyncResult(),
    )

    response = api_client.post("/api/integrations/google_ads/sync/", {}, format="json")
    assert response.status_code == 202
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert payload["sync_engine"] == "sdk"
    assert payload["task_id"] == "sdk-task-123"


def test_google_ads_status_includes_sync_state_metadata(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    credential.set_raw_tokens("token-access", "token-refresh")
    credential.save()
    GoogleAdsSyncState.objects.create(
        tenant=user.tenant,
        account_id="1234567890",
        desired_engine=GoogleAdsSyncState.ENGINE_SDK,
        effective_engine=GoogleAdsSyncState.ENGINE_SDK,
        fallback_active=True,
        parity_state=GoogleAdsSyncState.PARITY_FAIL,
        consecutive_sdk_failures=3,
        consecutive_parity_failures=2,
        last_sync_error="boom",
    )

    response = api_client.get("/api/integrations/google_ads/status/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sync_engine"] == "sdk"
    assert payload["fallback_active"] is True
    assert payload["parity_state"] == "fail"
    assert payload["metadata"]["consecutive_sdk_failures"] == 3
    assert payload["metadata"]["consecutive_parity_failures"] == 2


def test_google_ads_disconnect_pauses_connections_and_removes_credentials(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    credential.set_raw_tokens("token-access", "token-refresh")
    credential.save()

    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        name="Google Ads Tenant Connection",
        connection_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        is_active=True,
    )

    response = api_client.post("/api/integrations/google_ads/disconnect/", {}, format="json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert payload["paused_connections"] == 1
    assert payload["deleted_credentials"] == 1

    connection.refresh_from_db()
    assert connection.is_active is False
    assert PlatformCredential.objects.filter(id=credential.id).exists() is False
