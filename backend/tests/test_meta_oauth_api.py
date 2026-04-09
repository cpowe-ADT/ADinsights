from __future__ import annotations

from datetime import timedelta
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache
from django.utils import timezone
from django.urls import reverse

from accounts.models import AuditLog
from analytics.models import AdAccount
from integrations.models import (
    AirbyteConnection,
    MetaAccountSyncState,
    MetaConnection,
    MetaPage,
    PlatformCredential,
)
from integrations.tasks import META_DIRECT_SYNC_LOOKBACK_DAYS
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
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_LOGIN_CONFIG_REQUIRED = True
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    settings.AIRBYTE_SOURCE_DEFINITION_META = "e7778cfc-e97c-4458-9ecb-b4f2bba8946c"

    response = api_client.get(reverse("meta-setup"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["ready_for_oauth"] is True
    assert payload["ready_for_provisioning_defaults"] is True
    assert any(check["key"] == "meta_app_credentials" and check["ok"] for check in payload["checks"])
    assert any(check["key"] == "meta_redirect_uri" and check["ok"] for check in payload["checks"])
    assert any(check["key"] == "meta_login_configuration_id" and check["ok"] for check in payload["checks"])
    assert payload["missing_env_vars"] == []
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"
    assert payload["login_configuration_id_configured"] is True
    assert payload["login_configuration_id"] == "2323589144820085"
    assert payload["login_configuration_required"] is True
    assert payload["login_mode"] == "facebook_login_for_business"
    assert payload["runtime_context"]["redirect_source"] == "explicit_redirect_uri"
    assert payload["runtime_context"]["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"


@pytest.mark.django_db
def test_meta_setup_blocks_ready_for_oauth_when_runtime_origin_mismatches_redirect(
    api_client, user, settings
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_LOGIN_CONFIG_REQUIRED = True
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    response = api_client.get(
        reverse("meta-setup"),
        HTTP_ORIGIN="http://localhost:5175",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready_for_oauth"] is False
    assert payload["runtime_context"]["redirect_origin_matches_runtime"] is False
    runtime_check = next(check for check in payload["checks"] if check["key"] == "meta_runtime_redirect_origin")
    assert runtime_check["ok"] is False
    assert "does not match the configured OAuth redirect origin" in runtime_check["details"]


@pytest.mark.django_db
def test_meta_setup_reports_ignored_non_login_scopes(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_LOGIN_CONFIG_REQUIRED = True
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_OAUTH_SCOPES = [
        "ads_read",
        "business_management",
        "pages_show_list",
        "read_insights",
        "instagram_basic",
        "instagram_manage_insights",
    ]

    response = api_client.get(reverse("meta-setup"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["oauth_scopes"] == ["ads_read", "business_management", "pages_show_list"]
    assert sorted(payload["oauth_ignored_scopes"]) == [
        "instagram_basic",
        "instagram_manage_insights",
        "read_insights",
    ]


@pytest.mark.django_db
def test_meta_oauth_start_returns_authorize_url(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = True
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_GRAPH_API_VERSION = "v24.0"

    response = api_client.post(reverse("meta-oauth-start"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"
    assert "facebook.com/v24.0/dialog/oauth" in payload["authorize_url"]
    assert payload["login_configuration_id"] == "2323589144820085"

    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert query["response_type"] == ["code"]
    assert query["override_default_response_type"] == ["true"]
    assert query["config_id"] == ["2323589144820085"]
    assert "instagram_basic" not in query["scope"][0]
    assert "instagram_manage_insights" not in query["scope"][0]


@pytest.mark.django_db
def test_meta_oauth_start_uses_localhost_origin_when_redirect_not_explicit(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post(
        reverse("meta-oauth-start"),
        {},
        format="json",
        HTTP_ORIGIN="http://localhost:5175",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == "http://localhost:5175/dashboards/data-sources"
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert query["redirect_uri"] == ["http://localhost:5175/dashboards/data-sources"]


@pytest.mark.django_db
def test_meta_oauth_start_falls_back_to_frontend_base_without_origin(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post(
        reverse("meta-oauth-start"),
        {},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"


@pytest.mark.django_db
def test_meta_oauth_start_ignores_non_local_origin_for_redirect(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post(
        reverse("meta-oauth-start"),
        {},
        format="json",
        HTTP_ORIGIN="https://app.example.com",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == "http://localhost:5173/dashboards/data-sources"
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert query["redirect_uri"] == ["http://localhost:5173/dashboards/data-sources"]


@pytest.mark.django_db
def test_meta_connect_start_uses_runtime_context_origin_when_request_origin_missing(
    api_client,
    user,
    settings,
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post(
        reverse("meta-connect-start"),
        {"runtime_context": {"client_origin": "http://localhost:5175", "client_port": 5175}},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == "http://localhost:5175/dashboards/data-sources"
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert query["redirect_uri"] == ["http://localhost:5175/dashboards/data-sources"]


@pytest.mark.django_db
def test_meta_connect_start_rejects_runtime_origin_mismatch_when_redirect_is_explicit(
    api_client, user, settings
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    response = api_client.post(
        reverse("meta-connect-start"),
        {"runtime_context": {"client_origin": "http://localhost:5175", "client_port": 5175}},
        format="json",
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["detail"].startswith("Open the app on http://localhost:5173")
    assert payload["runtime_context"]["redirect_origin_matches_runtime"] is False


@pytest.mark.django_db
def test_meta_oauth_start_ignores_non_login_scopes_in_authorize_query(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_OAUTH_SCOPES = [
        "ads_read",
        "business_management",
        "pages_show_list",
        "read_insights",
        "instagram_basic",
        "instagram_manage_insights",
    ]

    response = api_client.post(reverse("meta-oauth-start"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert sorted(payload["ignored_scopes"]) == [
        "instagram_basic",
        "instagram_manage_insights",
        "read_insights",
    ]
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    requested_scopes = set(query["scope"][0].split(","))
    assert "ads_read" in requested_scopes
    assert "business_management" in requested_scopes
    assert "pages_show_list" in requested_scopes
    assert "read_insights" not in requested_scopes
    assert "instagram_basic" not in requested_scopes
    assert "instagram_manage_insights" not in requested_scopes


@pytest.mark.django_db
def test_meta_oauth_start_supports_auth_type_rerequest(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    response = api_client.post(reverse("meta-oauth-start"), {"auth_type": "rerequest"}, format="json")

    assert response.status_code == 200
    payload = response.json()
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert query["auth_type"] == ["rerequest"]


@pytest.mark.django_db
def test_meta_connect_start_uses_page_insights_scopes_only(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_OAUTH_SCOPES = ["ads_read", "ads_management", "business_management"]
    settings.META_PAGE_INSIGHTS_OAUTH_SCOPES = [
        "pages_show_list",
        "pages_read_engagement",
        "read_insights",
        "instagram_basic",
    ]

    response = api_client.post(reverse("meta-connect-start"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["oauth_flow"] == "page_insights"
    assert sorted(payload["ignored_scopes"]) == ["instagram_basic", "read_insights"]
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    requested_scopes = set(query["scope"][0].split(","))
    assert requested_scopes == {"pages_show_list", "pages_read_engagement"}
    assert "ads_read" not in requested_scopes
    assert "ads_management" not in requested_scopes
    assert "business_management" not in requested_scopes


@pytest.mark.django_db
def test_meta_connect_start_adds_required_page_insights_scopes_when_env_is_stale(
    api_client, user, settings
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_PAGE_INSIGHTS_OAUTH_SCOPES = [
        "pages_show_list",
        "pages_manage_metadata",
    ]

    response = api_client.post(reverse("meta-connect-start"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    requested_scopes = set(query["scope"][0].split(","))
    assert requested_scopes == {
        "pages_show_list",
        "pages_manage_metadata",
        "pages_read_engagement",
    }


@pytest.mark.django_db
def test_meta_oauth_start_requires_login_configuration_id_when_enabled(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_LOGIN_CONFIG_REQUIRED = True
    settings.META_LOGIN_CONFIG_ID = ""

    response = api_client.post(reverse("meta-oauth-start"), {}, format="json")

    assert response.status_code == 503
    assert "META_LOGIN_CONFIG_ID" in response.json()["detail"]


@pytest.mark.django_db
def test_meta_oauth_start_does_not_send_config_id_when_not_required(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    response = api_client.post(reverse("meta-oauth-start"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    query = parse_qs(urlparse(payload["authorize_url"]).query)
    assert "config_id" not in query
    assert payload["login_configuration_id"] is None


@pytest.mark.django_db
def test_meta_oauth_exchange_rejects_page_insights_flow_state(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    start_payload = api_client.post(reverse("meta-connect-start"), {}, format="json").json()
    state = start_payload["state"]

    response = api_client.post(
        reverse("meta-oauth-exchange"),
        {"code": "oauth-code", "state": state},
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "wrong_oauth_flow"


@pytest.mark.django_db
def test_meta_oauth_exchange_returns_pages_and_ad_accounts(api_client, user, monkeypatch, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
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

        def debug_token(self, *, input_token: str):
            assert input_token == "long-token"
            return {"is_valid": True, "app_id": "meta-app-id", "type": "USER", "user_id": "user-1"}

        def list_permissions(self, *, user_access_token: str):
            assert user_access_token == "long-token"
            return [
                {"permission": "ads_read", "status": "granted"},
                {"permission": "business_management", "status": "granted"},
                {"permission": "pages_show_list", "status": "declined"},
            ]

        def list_pages(self, *, user_access_token: str):
            assert user_access_token == "long-token"
            page = type(
                "MetaPage",
                (),
                {
                    "id": "page-1",
                    "name": "Business Page",
                    "category": "Business",
                    "tasks": ["ANALYZE"],
                    "perms": ["ADMINISTER"],
                    "access_token": "page-token-1",
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
    assert payload["token_debug_valid"] is True
    assert payload["granted_permissions"] == ["ads_read", "business_management"]
    assert "pages_show_list" in payload["declined_permissions"]
    assert "pages_show_list" in payload["missing_required_permissions"]
    assert payload["oauth_connected_but_missing_permissions"] is True


@pytest.mark.django_db
def test_meta_oauth_exchange_uses_runtime_context_origin_for_redirect_uri(
    api_client,
    user,
    monkeypatch,
    settings,
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_REQUIRED = False
    settings.META_OAUTH_REDIRECT_URI = ""
    settings.FRONTEND_BASE_URL = "http://localhost:5173"

    start_payload = api_client.post(
        reverse("meta-oauth-start"),
        {"runtime_context": {"client_origin": "http://localhost:5175", "client_port": 5175}},
        format="json",
    ).json()
    state = start_payload["state"]

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def exchange_code(self, *, code: str, redirect_uri: str):
            assert code == "oauth-code"
            assert redirect_uri == "http://localhost:5175/dashboards/data-sources"
            return type("Token", (), {"access_token": "short-token", "expires_in": 3600})()

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            return type("Token", (), {"access_token": "long-token", "expires_in": 7200})()

        def debug_token(self, *, input_token: str):
            return {"is_valid": True, "app_id": "meta-app-id", "type": "USER", "user_id": "user-1"}

        def list_permissions(self, *, user_access_token: str):
            return [
                {"permission": "ads_read", "status": "granted"},
                {"permission": "business_management", "status": "granted"},
                {"permission": "pages_show_list", "status": "granted"},
            ]

        def list_pages(self, *, user_access_token: str):
            page = type(
                "MetaPage",
                (),
                {
                    "id": "page-1",
                    "name": "Business Page",
                    "category": "",
                    "tasks": [],
                    "perms": [],
                    "access_token": "page-token-1",
                    "as_public_dict": lambda self: {
                        "id": "page-1",
                        "name": "Business Page",
                        "tasks": [],
                        "perms": [],
                    },
                },
            )()
            return [page]

        def list_ad_accounts(self, *, user_access_token: str):
            account = type(
                "MetaAdAccount",
                (),
                {"as_public_dict": lambda self: {"id": "act_123", "account_id": "123", "name": "Primary"}},
            )()
            return [account]

        def list_instagram_accounts(self, *, pages):  # noqa: ARG002
            return []

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())

    response = api_client.post(
        reverse("meta-oauth-exchange"),
        {
            "code": "oauth-code",
            "state": state,
            "runtime_context": {"client_origin": "http://localhost:5175", "client_port": 5175},
        },
        format="json",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_meta_oauth_exchange_scope_gate_allows_ads_management_without_ads_read(
    api_client, user, monkeypatch, settings
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    start_payload = api_client.post(reverse("meta-oauth-start"), {}, format="json").json()
    state = start_payload["state"]

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def exchange_code(self, *, code: str, redirect_uri: str):
            return type("Token", (), {"access_token": "short-token", "expires_in": 3600})()

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            return type("Token", (), {"access_token": "long-token", "expires_in": 7200})()

        def debug_token(self, *, input_token: str):
            return {"is_valid": True, "app_id": "meta-app-id", "type": "USER", "user_id": "user-1"}

        def list_permissions(self, *, user_access_token: str):
            return [
                {"permission": "ads_management", "status": "granted"},
                {"permission": "business_management", "status": "granted"},
                {"permission": "pages_show_list", "status": "granted"},
                {"permission": "pages_read_engagement", "status": "granted"},
            ]

        def list_pages(self, *, user_access_token: str):
            page = type(
                "MetaPage",
                (),
                {
                    "id": "page-1",
                    "name": "Business Page",
                    "category": "",
                    "tasks": [],
                    "perms": [],
                    "access_token": "page-token-1",
                    "as_public_dict": lambda self: {
                        "id": "page-1",
                        "name": "Business Page",
                        "tasks": [],
                        "perms": [],
                    },
                },
            )()
            return [page]

        def list_ad_accounts(self, *, user_access_token: str):
            account = type(
                "MetaAdAccount",
                (),
                {"as_public_dict": lambda self: {"id": "act_123", "account_id": "123", "name": "Primary"}},
            )()
            return [account]

        def list_instagram_accounts(self, *, pages):
            return []

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())
    response = api_client.post(
        reverse("meta-oauth-exchange"),
        {"code": "oauth-code", "state": state},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["missing_required_permissions"] == []
    assert payload["oauth_connected_but_missing_permissions"] is False


@pytest.mark.django_db
def test_meta_oauth_exchange_rejects_invalid_debug_token(api_client, user, monkeypatch, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    start_payload = api_client.post(reverse("meta-oauth-start"), {}, format="json").json()
    state = start_payload["state"]

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def exchange_code(self, *, code: str, redirect_uri: str):
            return type("Token", (), {"access_token": "short-token", "expires_in": 3600})()

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            return type("Token", (), {"access_token": "long-token", "expires_in": 7200})()

        def debug_token(self, *, input_token: str):
            return {"is_valid": False, "app_id": "meta-app-id"}

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())

    response = api_client.post(
        reverse("meta-oauth-exchange"),
        {"code": "oauth-code", "state": state},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Unable to complete Meta OAuth with the returned account data. "
        "Reconnect Meta with Facebook and try again."
    )


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
            "granted_permissions": ["ads_read", "business_management"],
            "declined_permissions": [],
            "missing_required_permissions": [],
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
    assert payload["granted_permissions"] == ["ads_read", "business_management"]
    assert payload["missing_required_permissions"] == []
    assert payload["page_insights_connected"] is True
    credential = PlatformCredential.objects.get(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
    )
    assert credential.decrypt_access_token() == "long-user-token"
    page_connection = MetaConnection.objects.get(tenant=user.tenant, user=user, is_active=True)
    assert page_connection.decrypt_token() == "long-user-token"
    assert page_connection.scopes == ["ads_read", "business_management"]
    page = MetaPage.objects.get(tenant=user.tenant, page_id="page-1")
    assert page.connection_id == page_connection.id
    assert page.is_default is True
    assert page.can_analyze is True
    assert page.decrypt_page_token() == "long-user-token"
    account = AdAccount.objects.get(tenant=user.tenant, external_id="act_123")
    assert account.account_id == "123"
    assert account.name == "Primary Account"


@pytest.mark.django_db
def test_meta_recovery_preview_uses_existing_meta_connection_token(api_client, user, monkeypatch):
    _authenticate(api_client, user)
    page_connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="app-user-123",
        scopes=["ads_read", "business_management", "pages_show_list", "pages_read_engagement"],
        is_active=True,
    )
    page_connection.set_raw_token("recovery-token")
    page_connection.save()
    page = MetaPage(
        tenant=user.tenant,
        connection=page_connection,
        page_id="page-1",
        name="Existing Page",
        can_analyze=True,
        is_default=True,
        tasks=["ANALYZE"],
    )
    page.set_raw_page_token("page-token")
    page.save()
    AuditLog.objects.create(
        tenant=user.tenant,
        user=user,
        action="meta_oauth_connected",
        resource_type="platform_credential",
        resource_id=str(uuid.uuid4()),
        metadata={"ad_account_id": "act_123", "instagram_account_id": "ig-1"},
    )

    class DummyPage:
        id = "page-1"
        name = "Existing Page"
        category = "Business"
        tasks = ["ANALYZE"]
        perms = []
        access_token = "page-token"

        def as_public_dict(self):
            return {
                "id": self.id,
                "name": self.name,
                "category": self.category,
                "tasks": self.tasks,
                "perms": self.perms,
            }

    class DummyAccount:
        def __init__(self, account_id: str, name: str):
            self.id = account_id
            self.account_id = account_id.replace("act_", "")
            self.name = name

        def as_public_dict(self):
            return {
                "id": self.id,
                "account_id": self.account_id,
                "name": self.name,
                "currency": "JMD",
                "business_name": "Adtelligent",
                "account_status": 1,
            }

    class DummyInstagram:
        id = "ig-1"
        username = "brandhandle"

        def as_public_dict(self):
            return {"id": self.id, "username": self.username}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def debug_token(self, *, input_token: str):
            assert input_token == "recovery-token"
            return {"is_valid": True, "app_id": "", "user_id": "app-user-123"}

        def list_permissions(self, *, user_access_token: str):
            assert user_access_token == "recovery-token"
            return [
                {"permission": "ads_read", "status": "granted"},
                {"permission": "business_management", "status": "granted"},
                {"permission": "pages_show_list", "status": "granted"},
                {"permission": "pages_read_engagement", "status": "granted"},
            ]

        def list_pages(self, *, user_access_token: str):
            assert user_access_token == "recovery-token"
            return [DummyPage()]

        def list_ad_accounts(self, *, user_access_token: str):
            assert user_access_token == "recovery-token"
            return [DummyAccount("act_123", "Students' Loan Bureau (SLB)")]

        def list_instagram_accounts(self, *, pages):
            assert pages
            return [DummyInstagram()]

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())

    response = api_client.post(reverse("meta-recovery-preview"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recovered_from_existing_token"] is True
    assert payload["source"] == "existing_meta_connection"
    assert payload["default_page_id"] == "page-1"
    assert payload["default_ad_account_id"] == "act_123"
    assert payload["default_instagram_account_id"] == "ig-1"
    assert payload["ad_accounts"][0]["id"] == "act_123"
    assert payload["selection_token"]


@pytest.mark.django_db
def test_meta_recovery_preview_rejects_missing_marketing_permissions(api_client, user, monkeypatch):
    _authenticate(api_client, user)
    page_connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="app-user-123",
        scopes=["pages_show_list", "pages_read_engagement"],
        is_active=True,
    )
    page_connection.set_raw_token("recovery-token")
    page_connection.save()

    class DummyPage:
        id = "page-1"
        name = "Existing Page"
        category = "Business"
        tasks = ["ANALYZE"]
        perms = []
        access_token = "page-token"

        def as_public_dict(self):
            return {"id": self.id, "name": self.name, "tasks": self.tasks, "perms": self.perms}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def debug_token(self, *, input_token: str):
            return {"is_valid": True, "app_id": "", "user_id": "app-user-123"}

        def list_permissions(self, *, user_access_token: str):
            return [
                {"permission": "pages_show_list", "status": "granted"},
                {"permission": "pages_read_engagement", "status": "granted"},
            ]

        def list_pages(self, *, user_access_token: str):
            return [DummyPage()]

        def list_ad_accounts(self, *, user_access_token: str):
            return []

        def list_instagram_accounts(self, *, pages):
            return []

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())

    response = api_client.post(reverse("meta-recovery-preview"), {}, format="json")

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "marketing_permissions_missing"
    assert "business_management" in payload["missing_required_permissions"]


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
            "granted_permissions": ["ads_read", "business_management"],
            "declined_permissions": [],
            "missing_required_permissions": [],
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
def test_meta_page_connect_rejects_when_required_permissions_missing(api_client, user):
    _authenticate(api_client, user)
    selection_token = "selection-token-missing-permissions"
    cache.set(
        f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}",
        {
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "user_access_token": "long-user-token",
            "granted_permissions": ["ads_read"],
            "declined_permissions": ["business_management"],
            "missing_required_permissions": ["business_management"],
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
            "ad_account_id": "act_123",
        },
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert "missing_required_permissions" in payload
    assert "business_management" in payload["missing_required_permissions"]


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
            assert payload["connectionConfiguration"]["account_ids"] == ["123"]
            credentials = payload["connectionConfiguration"]["credentials"]
            assert credentials["auth_type"] == "Service"
            assert credentials["access_token"] == "meta-token"
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
                        },
                        {
                            "name": "campaigns",
                            "supportedSyncModes": ["incremental"],
                            "supportedDestinationSyncModes": ["append"],
                            "defaultCursorField": ["updated_time"],
                            "sourceDefinedPrimaryKey": [["id"]],
                        }
                    ]
                }
            }

        def list_connections(self, workspace_id: str):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            return []

        def create_connection(self, payload):
            assert payload["destinationId"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            configured_streams = payload["syncCatalog"]["streams"]
            assert [stream["stream"]["name"] for stream in configured_streams] == ["ads_insights"]
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
def test_meta_provision_accepts_omitted_schedule_fields(api_client, user, monkeypatch, settings):
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
    credential.set_raw_tokens("token-current", None)
    credential.save()

    observed: dict[str, object] = {}

    class DummyAirbyteClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_sources(self, workspace_id: str):
            return []

        def create_source(self, payload):
            return {"sourceId": "source-new"}

        def check_source(self, source_id: str):
            return {"jobInfo": {"status": "succeeded"}}

        def discover_source_schema(self, source_id: str):
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
            return []

        def create_connection(self, payload):
            observed["connection_payload"] = payload
            return {"connectionId": str(uuid.uuid4())}

    monkeypatch.setattr("integrations.views.AirbyteClient.from_settings", lambda: DummyAirbyteClient())

    response = api_client.post(
        reverse("meta-provision"),
        {
            "connection_name": "Meta Insights Connection",
        },
        format="json",
    )

    assert response.status_code == 201
    connection_payload = observed["connection_payload"]
    assert connection_payload["scheduleType"] == "cron"
    assert connection_payload["scheduleData"]["cron"]["cronExpression"] == "0 0 6-22 * * ?"


@pytest.mark.django_db
def test_meta_provision_updates_existing_source_with_latest_credentials(api_client, user, monkeypatch, settings):
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
    credential.set_raw_tokens("rotated-token", None)
    credential.save()

    observed: dict[str, object] = {}
    existing_connection_id = str(uuid.uuid4())

    class DummyAirbyteClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_sources(self, workspace_id: str):
            return [
                {
                    "name": "Meta Source act_123",
                    "sourceId": "source-existing",
                    "sourceDefinitionId": "e7778cfc-e97c-4458-9ecb-b4f2bba8946c",
                }
            ]

        def update_source(self, payload):
            observed["updated_source"] = payload
            return {"sourceId": "source-existing"}

        def create_source(self, payload):
            raise AssertionError("create_source should not be called for an existing source")

        def check_source(self, source_id: str):
            return {"jobInfo": {"status": "succeeded"}}

        def discover_source_schema(self, source_id: str):
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
            return [
                {
                    "name": "Meta Insights act_123",
                    "connectionId": existing_connection_id,
                    "destinationId": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "operationIds": [],
                }
            ]

        def update_connection(self, payload):
            observed["updated_connection"] = payload
            return {"connectionId": existing_connection_id}

        def create_connection(self, payload):
            raise AssertionError("create_connection should not be called for an existing connection")

    monkeypatch.setattr("integrations.views.AirbyteClient.from_settings", lambda: DummyAirbyteClient())

    response = api_client.post(
        reverse("meta-provision"),
        {
            "connection_name": "Meta Insights act_123",
            "schedule_type": "cron",
            "cron_expression": "0 6-22 * * *",
        },
        format="json",
    )

    assert response.status_code == 201
    assert observed["updated_source"]["sourceId"] == "source-existing"
    updated_credentials = observed["updated_source"]["connectionConfiguration"]["credentials"]
    assert updated_credentials["auth_type"] == "Service"
    assert updated_credentials["access_token"] == "rotated-token"
    assert observed["updated_connection"]["connectionId"] == existing_connection_id
    assert observed["updated_connection"]["destinationId"] == settings.AIRBYTE_DEFAULT_DESTINATION_ID
    assert response.json()["source_reused"] is True
    assert response.json()["connection_reused"] is True


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
def test_meta_provision_accepts_explicit_uuid_workspace_and_destination_ids(
    api_client, user, monkeypatch, settings
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = ""
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = ""

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

    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    destination_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    observed: dict[str, object] = {}

    class DummyAirbyteClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_sources(self, incoming_workspace_id: str):
            observed["workspace_id"] = incoming_workspace_id
            return []

        def create_source(self, payload):
            return {"sourceId": "source-1"}

        def check_source(self, source_id: str):
            return {"jobInfo": {"status": "succeeded"}}

        def discover_source_schema(self, source_id: str):
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

        def list_connections(self, incoming_workspace_id: str):
            assert incoming_workspace_id == workspace_id
            return []

        def create_connection(self, payload):
            observed["destination_id"] = payload["destinationId"]
            return {"connectionId": str(uuid.uuid4())}

    monkeypatch.setattr("integrations.views.AirbyteClient.from_settings", lambda: DummyAirbyteClient())

    response = api_client.post(
        reverse("meta-provision"),
        {
            "workspace_id": workspace_id,
            "destination_id": destination_id,
            "connection_name": "Meta Insights Connection",
            "schedule_type": "cron",
            "cron_expression": "0 6-22 * * *",
        },
        format="json",
    )

    assert response.status_code == 201
    assert observed["workspace_id"] == workspace_id
    assert observed["destination_id"] == destination_id


@pytest.mark.django_db
def test_meta_sync_queues_direct_reporting_task(api_client, user, monkeypatch):
    _authenticate(api_client, user)
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
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta Connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
    )
    observed: dict[str, object] = {}

    def fake_apply_async(*, kwargs=None, task_id=None, **_extra):  # noqa: ANN001
        observed["kwargs"] = kwargs or {}
        observed["task_id"] = task_id
        return None

    monkeypatch.setattr("integrations.tasks.sync_meta_reporting_slice.apply_async", fake_apply_async)

    response = api_client.post(reverse("meta-sync"), {}, format="json")

    assert response.status_code == 202
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["job_id"]
    assert observed["task_id"] == payload["job_id"]
    assert observed["kwargs"]["tenant_id"] == str(user.tenant.id)
    assert observed["kwargs"]["account_id"] == "act_123"
    assert observed["kwargs"]["job_id"] == payload["job_id"]
    assert observed["kwargs"]["connection_pk"] == str(connection.id)
    window_end = timezone.localdate() - timedelta(days=1)
    window_start = window_end - timedelta(days=META_DIRECT_SYNC_LOOKBACK_DAYS - 1)
    assert observed["kwargs"]["since"] == window_start.isoformat()
    assert observed["kwargs"]["until"] == window_end.isoformat()
    state = MetaAccountSyncState.objects.get(tenant=user.tenant, account_id="act_123")
    assert state.last_job_id == payload["job_id"]
    assert state.last_job_status == "pending"
    assert state.last_sync_engine == MetaAccountSyncState.SYNC_ENGINE_DIRECT


@pytest.mark.django_db
def test_meta_sync_reuses_existing_direct_job(api_client, user, monkeypatch):
    _authenticate(api_client, user)
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
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta Connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-existing",
        last_job_status="running",
        last_sync_started_at=timezone.now() - timedelta(minutes=10),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
    )

    def fake_apply_async(*args, **kwargs):  # noqa: ANN001, ARG001
        raise AssertionError("apply_async should not be called when a direct sync is already running")

    monkeypatch.setattr("integrations.tasks.sync_meta_reporting_slice.apply_async", fake_apply_async)

    response = api_client.post(reverse("meta-sync"), {}, format="json")

    assert response.status_code == 202
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["job_id"] == "job-existing"
    assert payload["reused_existing_job"] is True
    assert payload["sync_status"] == "already_running"
    state = MetaAccountSyncState.objects.get(tenant=user.tenant, account_id="act_123")
    assert state.last_job_id == "job-existing"


@pytest.mark.django_db
def test_meta_sync_falls_back_to_inline_when_broker_unavailable(api_client, user, monkeypatch):
    _authenticate(api_client, user)
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
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta Connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
    )
    observed: dict[str, object] = {}

    def fake_apply_async(*args, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("Redis connection refused")

    def fake_run(**kwargs):  # noqa: ANN001
        observed["kwargs"] = kwargs
        return {"insights_synced": 0}

    monkeypatch.setattr("integrations.tasks.sync_meta_reporting_slice.apply_async", fake_apply_async)
    monkeypatch.setattr("integrations.tasks.sync_meta_reporting_slice.run", fake_run)

    response = api_client.post(reverse("meta-sync"), {}, format="json")

    assert response.status_code == 202
    payload = response.json()
    assert payload["task_dispatch_mode"] == "inline"
    assert observed["kwargs"]["tenant_id"] == str(user.tenant.id)
    assert observed["kwargs"]["account_id"] == "act_123"
    assert observed["kwargs"]["connection_pk"] == str(connection.id)
    state = MetaAccountSyncState.objects.get(tenant=user.tenant, account_id="act_123")
    assert state.last_job_status == "pending"


@pytest.mark.django_db
def test_meta_sync_prefers_valid_credential_when_connection_linked_state_points_to_reauth_record(
    api_client, user, monkeypatch
):
    _authenticate(api_client, user)
    valid_credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_335732240",
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    valid_credential.set_raw_tokens("meta-token-valid", None)
    valid_credential.save()

    reauth_credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_1023646075020889",
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
        token_status=PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
        token_status_reason="Meta credential needs to be re-authorized.",
    )
    reauth_credential.set_raw_tokens("meta-token-expired", None)
    reauth_credential.save()

    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta Connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        is_active=True,
        last_job_status="failed",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id=reauth_credential.account_id,
        connection=connection,
        last_job_id="old-airbyte-job",
        last_job_status="failed",
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_AIRBYTE,
    )

    observed: dict[str, object] = {}

    def fake_apply_async(*, kwargs=None, task_id=None, **_extra):  # noqa: ANN001
        observed["kwargs"] = kwargs or {}
        observed["task_id"] = task_id
        return None

    monkeypatch.setattr("integrations.tasks.sync_meta_reporting_slice.apply_async", fake_apply_async)

    response = api_client.post(reverse("meta-sync"), {}, format="json")

    assert response.status_code == 202
    assert observed["kwargs"]["account_id"] == valid_credential.account_id


@pytest.mark.django_db
def test_meta_sync_returns_accepted_when_eager_task_fails(api_client, user, monkeypatch, settings):
    _authenticate(api_client, user)
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
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta Connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
    )
    settings.CELERY_TASK_ALWAYS_EAGER = True

    def fake_apply_async(*args, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("task blew up in eager mode")

    monkeypatch.setattr("integrations.tasks.sync_meta_reporting_slice.apply_async", fake_apply_async)

    response = api_client.post(reverse("meta-sync"), {}, format="json")

    assert response.status_code == 202
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["connection_id"] == str(connection.connection_id)


@pytest.mark.django_db
def test_meta_system_token_endpoint_stores_lifecycle_fields(api_client, user, monkeypatch, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def debug_token(self, *, input_token: str):
            assert input_token == "system-token"
            return {
                "is_valid": True,
                "app_id": "meta-app-id",
                "issued_at": 1700000000,
                "expires_at": 4102444800,
                "scopes": ["ads_read", "ads_management"],
            }

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())
    response = api_client.post(
        reverse("meta-system-token"),
        {
            "account_id": "123",
            "access_token": "system-token",
        },
        format="json",
    )

    assert response.status_code == 201
    credential = PlatformCredential.objects.get(tenant=user.tenant, provider=PlatformCredential.META)
    assert credential.account_id == "act_123"
    assert credential.auth_mode == PlatformCredential.AUTH_MODE_SYSTEM_USER
    assert credential.token_status == PlatformCredential.TOKEN_STATUS_VALID
    assert credential.decrypt_access_token() == "system-token"
    assert sorted(credential.granted_scopes) == ["ads_management", "ads_read"]


@pytest.mark.django_db
def test_meta_system_token_endpoint_rejects_invalid_token(api_client, user, monkeypatch, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def debug_token(self, *, input_token: str):
            return {"is_valid": False, "app_id": "meta-app-id"}

    monkeypatch.setattr("integrations.views.MetaGraphClient.from_settings", lambda: DummyClient())
    response = api_client.post(
        reverse("meta-system-token"),
        {
            "account_id": "123",
            "access_token": "system-token",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "validation" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_meta_sync_state_endpoint_returns_tenant_rows(api_client, user):
    _authenticate(api_client, user)
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        last_job_id="99",
        last_job_status="succeeded",
    )

    response = api_client.get(reverse("meta-sync-state"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["account_id"] == "act_123"
    assert payload["results"][0]["last_job_id"] == "99"


@pytest.mark.django_db
def test_meta_logout_deletes_meta_credentials(api_client, user):
    _authenticate(api_client, user)
    first = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    first.set_raw_tokens("meta-token-1", None)
    first.save()
    second = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_456",
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    second.set_raw_tokens("meta-token-2", None)
    second.save()
    page_connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="meta-page-user",
        scopes=["ads_read", "business_management", "pages_show_list", "pages_read_engagement"],
        is_active=True,
    )
    page_connection.set_raw_token("page-token")
    page_connection.save()
    page = MetaPage(
        tenant=user.tenant,
        connection=page_connection,
        page_id="page-1",
        name="Business Page",
        can_analyze=True,
        is_default=True,
        tasks=["ANALYZE"],
    )
    page.set_raw_page_token("page-token")
    page.save()
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        last_job_status="failed",
    )
    connection = AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta Connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        is_active=True,
    )

    response = api_client.post(reverse("meta-logout"), {}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "meta_ads"
    assert payload["disconnected"] is True
    assert payload["deleted_credentials"] == 2
    assert payload["deleted_page_connections"] == 1
    assert payload["deleted_pages"] == 1
    assert payload["deleted_sync_states"] == 1
    assert payload["disabled_airbyte_connections"] == 1
    assert (
        PlatformCredential.objects.filter(
            tenant=user.tenant,
            provider=PlatformCredential.META,
        ).count()
        == 0
    )
    assert MetaConnection.objects.filter(tenant=user.tenant).count() == 0
    assert MetaPage.objects.filter(tenant=user.tenant).count() == 0
    assert MetaAccountSyncState.objects.filter(tenant=user.tenant).count() == 0
    connection.refresh_from_db()
    assert connection.is_active is False
