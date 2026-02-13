from __future__ import annotations

import uuid
from datetime import timedelta

from django.core import signing
from django.urls import reverse
from django.utils import timezone

from integrations.google_oauth import GoogleOAuthToken
from integrations.models import AirbyteConnection, AirbyteJobTelemetry, PlatformCredential
from integrations.views import INTEGRATION_OAUTH_STATE_SALT


def _auth(api_client, user) -> None:
    api_client.force_authenticate(user=user)


def test_google_oauth_start_returns_authorize_url(api_client, user, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "google-client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.GOOGLE_OAUTH_SCOPES_GOOGLE_ADS = ["https://www.googleapis.com/auth/adwords"]
    _auth(api_client, user)

    response = api_client.post(
        reverse("integration-oauth-start", args=["google_ads"]),
        {},
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert "accounts.google.com" in payload["authorize_url"]
    state_payload = signing.loads(payload["state"], salt=INTEGRATION_OAUTH_STATE_SALT)
    assert state_payload["tenant_id"] == str(user.tenant_id)
    assert state_payload["provider"] == "google_ads"


def test_google_oauth_callback_creates_credential(api_client, user, monkeypatch, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "google-client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.GOOGLE_OAUTH_SCOPES_GOOGLE_ADS = ["https://www.googleapis.com/auth/adwords"]
    _auth(api_client, user)

    start_response = api_client.post(
        reverse("integration-oauth-start", args=["google_ads"]),
        {},
        format="json",
    )
    state = start_response.json()["state"]

    def _fake_exchange(self, *, code):  # noqa: ANN001
        assert code == "oauth-code"
        return GoogleOAuthToken(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
            token_type="Bearer",
            scope="scope",
        )

    monkeypatch.setattr("integrations.google_oauth.GoogleOAuthClient.exchange_code", _fake_exchange)

    callback_response = api_client.post(
        reverse("integration-oauth-callback", args=["google_ads"]),
        {
            "code": "oauth-code",
            "state": state,
            "external_account_id": "1234567890",
        },
        format="json",
    )
    assert callback_response.status_code == 200
    payload = callback_response.json()
    assert payload["status"] == "connected"
    assert payload["credential"]["provider"] == PlatformCredential.GOOGLE
    assert payload["credential"]["account_id"] == "1234567890"

    credential = PlatformCredential.objects.get(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    assert credential.decrypt_access_token() == "access-token"
    assert credential.decrypt_refresh_token() == "refresh-token"
    assert credential.expires_at is not None


def test_integration_status_not_connected(api_client, user):
    _auth(api_client, user)
    response = api_client.get(reverse("integration-status", args=["ga4"]))
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ga4"
    assert payload["state"] == "not_connected"


def test_integration_status_needs_reauth_when_token_expired(api_client, user):
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    credential.set_raw_tokens("access-token", "refresh-token")
    credential.save()

    _auth(api_client, user)
    response = api_client.get(reverse("integration-status", args=["google_ads"]))
    assert response.status_code == 200
    assert response.json()["state"] == "needs_reauth"


def test_integration_sync_uses_latest_provider_connection(api_client, user, monkeypatch):
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        name="Google Ads Metrics",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        is_active=True,
    )

    class DummyClient:
        def __enter__(self):  # noqa: D401
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, D401
            return None

        def trigger_sync(self, connection_id: str):  # noqa: D401
            assert connection_id == str(connection.connection_id)
            return {"job": {"id": 91}}

    monkeypatch.setattr("integrations.views.AirbyteClient.from_settings", lambda: DummyClient())
    _auth(api_client, user)

    response = api_client.post(reverse("integration-sync", args=["google_ads"]), {}, format="json")
    assert response.status_code == 202
    assert response.json()["job_id"] == "91"


def test_integration_disconnect_pauses_connections_and_deletes_credentials(api_client, user):
    credential = PlatformCredential(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    credential.set_raw_tokens("access-token", "refresh-token")
    credential.save()
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        name="Google Ads Metrics",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        is_active=True,
    )

    _auth(api_client, user)
    response = api_client.post(reverse("integration-disconnect", args=["google_ads"]), {}, format="json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "disconnected"
    assert payload["credentials_deleted"] == 1
    assert payload["connections_paused"] == 1

    assert not PlatformCredential.objects.filter(pk=credential.pk).exists()
    connection.refresh_from_db()
    assert connection.is_active is False
    assert connection.last_job_status == "disconnected"


def test_integration_reconnect_reuses_oauth_start(api_client, user, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "google-client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.GOOGLE_OAUTH_SCOPES_GOOGLE_ADS = ["https://www.googleapis.com/auth/adwords"]
    _auth(api_client, user)

    response = api_client.post(reverse("integration-reconnect", args=["google_ads"]), {}, format="json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert "accounts.google.com" in payload["authorize_url"]


def test_integration_jobs_returns_recent_provider_rows(api_client, user, tenant):
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.GOOGLE,
        name="Google Ads Metrics",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        is_active=True,
    )
    AirbyteJobTelemetry.objects.create(
        tenant=user.tenant,
        connection=connection,
        job_id="1001",
        status="succeeded",
        started_at=timezone.now(),
        duration_seconds=40,
        records_synced=500,
    )
    other_connection = AirbyteConnection.objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        name="Meta Metrics",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=60,
        is_active=True,
    )
    AirbyteJobTelemetry.objects.create(
        tenant=tenant,
        connection=other_connection,
        job_id="2001",
        status="failed",
        started_at=timezone.now(),
        duration_seconds=10,
    )

    _auth(api_client, user)
    response = api_client.get(f"{reverse('integration-jobs', args=['google_ads'])}?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_ads"
    assert payload["count"] == 1
    assert payload["jobs"][0]["job_id"] == "1001"


def test_integration_provision_creates_airbyte_connection(api_client, user, monkeypatch):
    credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.SEARCH_CONSOLE,
        account_id="sc-domain:example.com",
        access_token_enc=b"token",
        access_token_nonce=b"nonce",
        access_token_tag=b"tag",
    )
    credential.set_raw_tokens("access-token", "refresh-token")
    credential.save()

    workspace_id = uuid.uuid4()
    destination_id = uuid.uuid4()
    source_id = str(uuid.uuid4())
    connection_id = str(uuid.uuid4())

    class DummyClient:
        def __enter__(self):  # noqa: D401
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, D401
            return None

        def list_sources(self, _workspace):  # noqa: D401, ANN001
            return []

        def create_source(self, payload):  # noqa: D401, ANN001
            return {"sourceId": source_id, "name": payload["name"]}

        def discover_source_schema(self, _source_id):  # noqa: D401, ANN001
            return {
                "catalog": {
                    "streams": [
                        {
                            "name": "search_analytics",
                            "supportedSyncModes": ["incremental"],
                            "supportedDestinationSyncModes": ["append", "append_dedup"],
                            "defaultCursorField": ["date"],
                            "sourceDefinedPrimaryKey": [["site_url"], ["date"]],
                        }
                    ]
                }
            }

        def list_connections(self, _workspace):  # noqa: D401, ANN001
            return []

        def create_connection(self, payload):  # noqa: D401, ANN001
            assert payload["sourceId"] == source_id
            return {"connectionId": connection_id, "name": payload["name"]}

    monkeypatch.setattr("integrations.views.AirbyteClient.from_settings", lambda: DummyClient())
    _auth(api_client, user)

    response = api_client.post(
        reverse("integration-provision", args=["search_console"]),
        {
            "external_account_id": "sc-domain:example.com",
            "workspace_id": str(workspace_id),
            "destination_id": str(destination_id),
            "source_definition_id": str(uuid.uuid4()),
            "source_configuration": {"site_url": "sc-domain:example.com"},
            "schedule_type": "cron",
            "cron_expression": "0 6-22 * * *",
        },
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["provider"] == "search_console"
    assert payload["connection"]["provider"] == PlatformCredential.SEARCH_CONSOLE
    assert AirbyteConnection.objects.filter(
        tenant=user.tenant,
        provider=PlatformCredential.SEARCH_CONSOLE,
        connection_id=uuid.UUID(connection_id),
    ).exists()
