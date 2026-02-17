from __future__ import annotations

import uuid

import pytest
from django.core.cache import cache
from django.urls import reverse

from integrations.models import AirbyteConnection, PlatformCredential
from integrations.views import META_OAUTH_SELECTION_CACHE_PREFIX


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_meta_setup_reports_configuration_flags(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    settings.AIRBYTE_SOURCE_DEFINITION_META = "778daa7c-feaf-4db6-96f3-70fd645acc77"

    response = api_client.get(reverse("meta-setup"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["ready_for_oauth"] is True
    assert payload["ready_for_provisioning_defaults"] is True
    assert any(check["key"] == "meta_app_credentials" and check["ok"] for check in payload["checks"])
    assert any(check["key"] == "meta_redirect_uri" and check["ok"] for check in payload["checks"])
    assert payload["missing_env_vars"] == []
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"


@pytest.mark.django_db
def test_meta_oauth_start_returns_authorize_url(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_GRAPH_API_VERSION = "v24.0"

    response = api_client.post(reverse("meta-oauth-start"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"
    assert "facebook.com/v24.0/dialog/oauth" in payload["authorize_url"]


@pytest.mark.django_db
def test_meta_oauth_exchange_returns_pages_and_ad_accounts(api_client, user, monkeypatch, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    start_payload = api_client.post(reverse("meta-oauth-start"), {}, format="json").json()
    state = start_payload["state"]

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def exchange_code(self, *, code: str, redirect_uri: str):
            assert code == "oauth-code"
            assert redirect_uri == "http://localhost:5173/dashboards/data-sources"
            return type("Token", (), {"access_token": "short-token", "expires_in": 3600})()

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            assert short_lived_user_token == "short-token"
            return type("Token", (), {"access_token": "long-token", "expires_in": 7200})()

        def list_pages(self, *, user_access_token: str):
            assert user_access_token == "long-token"
            page = type(
                "MetaPage",
                (),
                {
                    "as_public_dict": lambda self: {
                        "id": "page-1",
                        "name": "Business Page",
                        "category": "Business",
                        "tasks": ["ANALYZE"],
                        "perms": ["ADMINISTER"],
                    }
                },
            )()
            return [page]

        def list_ad_accounts(self, *, user_access_token: str):
            assert user_access_token == "long-token"
            account = type(
                "MetaAdAccount",
                (),
                {
                    "as_public_dict": lambda self: {
                        "id": "act_123",
                        "account_id": "123",
                        "name": "Primary Account",
                        "currency": "USD",
                        "account_status": 1,
                        "business_name": "Business Name",
                    }
                },
            )()
            return [account]

        def list_instagram_accounts(self, *, pages):
            assert len(pages) == 1
            instagram_account = type(
                "MetaInstagramAccount",
                (),
                {
                    "as_public_dict": lambda self: {
                        "id": "ig-1",
                        "username": "brandhandle",
                        "name": "Brand Handle",
                        "profile_picture_url": "https://example.com/pic.jpg",
                        "followers_count": 1200,
                        "media_count": 87,
                        "source_page_id": "page-1",
                        "source_page_name": "Business Page",
                        "source_field": "instagram_business_account",
                    }
                },
            )()
            return [instagram_account]

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())

    response = api_client.post(
        reverse("meta-oauth-exchange"),
        {"code": "oauth-code", "state": state},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_token"]
    assert payload["pages"][0]["id"] == "page-1"
    assert payload["ad_accounts"][0]["id"] == "act_123"
    assert payload["instagram_accounts"][0]["id"] == "ig-1"


@pytest.mark.django_db
def test_meta_page_connect_creates_meta_credential(api_client, user):
    _authenticate(api_client, user)
    selection_token = "selection-token"
    cache.set(
        f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}",
        {
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "user_access_token": "long-user-token",
            "pages": [{"id": "page-1", "name": "Business Page", "tasks": [], "perms": []}],
            "ad_accounts": [{"id": "act_123", "account_id": "123", "name": "Primary Account"}],
            "instagram_accounts": [{"id": "ig-1", "username": "brandhandle", "name": "Brand Handle"}],
        },
        timeout=600,
    )

    response = api_client.post(
        reverse("meta-page-connect"),
        {
            "selection_token": selection_token,
            "page_id": "page-1",
            "ad_account_id": "act_123",
            "instagram_account_id": "ig-1",
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["credential"]["provider"] == PlatformCredential.META
    assert payload["credential"]["account_id"] == "act_123"
    assert payload["instagram_account"]["id"] == "ig-1"
    credential = PlatformCredential.objects.get(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
    )
    assert credential.decrypt_access_token() == "long-user-token"


@pytest.mark.django_db
def test_meta_page_connect_requires_ad_account_selection(api_client, user):
    _authenticate(api_client, user)
    selection_token = "selection-token-no-ad-account"
    cache.set(
        f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}",
        {
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "user_access_token": "long-user-token",
            "pages": [{"id": "page-1", "name": "Business Page", "tasks": [], "perms": []}],
            "ad_accounts": [{"id": "act_123", "account_id": "123", "name": "Primary Account"}],
            "instagram_accounts": [],
        },
        timeout=600,
    )

    response = api_client.post(
        reverse("meta-page-connect"),
        {
            "selection_token": selection_token,
            "page_id": "page-1",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "ad_account_id" in response.json()


@pytest.mark.django_db
def test_meta_provision_creates_airbyte_connection(api_client, user, monkeypatch, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    credential.set_raw_tokens("meta-token", None)
    credential.save()

    class DummyAirbyteClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_sources(self, workspace_id: str):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            return []

        def create_source(self, payload):
            assert payload["connectionConfiguration"]["account_id"] == "123"
            assert payload["connectionConfiguration"]["access_token"] == "meta-token"
            return {"sourceId": "source-1"}

        def check_source(self, source_id: str):
            assert source_id == "source-1"
            return {"jobInfo": {"status": "succeeded"}}

        def discover_source_schema(self, source_id: str):
            assert source_id == "source-1"
            return {
                "catalog": {
                    "streams": [
                        {
                            "name": "ads_insights",
                            "supportedSyncModes": ["incremental"],
                            "supportedDestinationSyncModes": ["append_dedup"],
                            "defaultCursorField": ["date_start"],
                            "sourceDefinedPrimaryKey": [["ad_id"], ["date_start"]],
                        }
                    ]
                }
            }

        def list_connections(self, workspace_id: str):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            return []

        def create_connection(self, payload):
            assert payload["destinationId"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            return {"connectionId": str(uuid.uuid4())}

    monkeypatch.setattr("integrations.views.AirbyteClient.from_settings", lambda: DummyAirbyteClient())

    response = api_client.post(
        reverse("meta-provision"),
        {
            "connection_name": "Meta Insights Connection",
            "schedule_type": "cron",
            "cron_expression": "0 6-22 * * *",
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["connection"]["provider"] == PlatformCredential.META
    assert AirbyteConnection.objects.filter(
        tenant=user.tenant,
        provider=PlatformCredential.META,
    ).exists()


@pytest.mark.django_db
def test_meta_provision_rejects_non_ad_account_ids(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="page-1",
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    credential.set_raw_tokens("meta-token", None)
    credential.save()

    response = api_client.post(
        reverse("meta-provision"),
        {
            "connection_name": "Meta Insights Connection",
            "schedule_type": "cron",
            "cron_expression": "0 6-22 * * *",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "valid ad account" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_meta_sync_triggers_airbyte_job(api_client, user, monkeypatch):
    _authenticate(api_client, user)
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta Connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
    )

    class DummyAirbyteClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def trigger_sync(self, connection_id: str):
            assert connection_id == str(connection.connection_id)
            return {"job": {"id": 77}}

    monkeypatch.setattr("integrations.views.AirbyteClient.from_settings", lambda: DummyAirbyteClient())

    response = api_client.post(reverse("meta-sync"), {}, format="json")

    assert response.status_code == 202
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["job_id"] == "77"
