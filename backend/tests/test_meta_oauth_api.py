from __future__ import annotations

from django.core import signing
from django.core.cache import cache
from django.urls import reverse
import pytest

from accounts.models import AuditLog, User
from integrations.meta_graph import MetaPage
from integrations.models import PlatformCredential
from integrations.views import (
    META_OAUTH_SELECTION_CACHE_PREFIX,
    META_OAUTH_STATE_SALT,
)


@pytest.fixture(autouse=True)
def _meta_settings(settings):
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.META_OAUTH_SCOPES = [
        "pages_show_list",
        "pages_read_engagement",
    ]
    settings.META_GRAPH_API_VERSION = "v20.0"
    yield


@pytest.mark.django_db
def test_meta_oauth_start_returns_authorize_url(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.post(reverse("meta-oauth-start"), {}, format="json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["authorize_url"].startswith("https://www.facebook.com/v20.0/dialog/oauth?")
    assert "client_id=meta-app-id" in payload["authorize_url"]
    assert "scope=pages_show_list%2Cpages_read_engagement" in payload["authorize_url"]
    state_payload = signing.loads(payload["state"], salt=META_OAUTH_STATE_SALT)
    assert state_payload["tenant_id"] == str(user.tenant_id)
    assert state_payload["user_id"] == str(user.id)


@pytest.mark.django_db
def test_meta_oauth_exchange_returns_page_selection_token(api_client, user, monkeypatch):
    from integrations.meta_graph import MetaGraphClient

    api_client.force_authenticate(user=user)
    start_response = api_client.post(reverse("meta-oauth-start"), {}, format="json")
    state = start_response.json()["state"]

    monkeypatch.setattr(
        MetaGraphClient,
        "exchange_code",
        lambda self, *, code, redirect_uri: "user-token",  # noqa: ARG005
    )
    monkeypatch.setattr(
        MetaGraphClient,
        "list_pages",
        lambda self, *, user_access_token: [  # noqa: ARG005
            MetaPage(
                id="page-1",
                name="Primary Page",
                access_token="page-token-1",
                category="Business",
                tasks=["CREATE_CONTENT"],
                perms=["ADMINISTER"],
            )
        ],
    )

    response = api_client.post(
        reverse("meta-oauth-exchange"),
        {"code": "oauth-code", "state": state},
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_token"]
    assert payload["pages"] == [
        {
            "id": "page-1",
            "name": "Primary Page",
            "category": "Business",
            "tasks": ["CREATE_CONTENT"],
            "perms": ["ADMINISTER"],
        }
    ]
    cached = cache.get(f"{META_OAUTH_SELECTION_CACHE_PREFIX}{payload['selection_token']}")
    assert isinstance(cached, dict)
    assert cached["tenant_id"] == str(user.tenant_id)
    assert cached["pages"][0]["access_token"] == "page-token-1"


@pytest.mark.django_db
def test_meta_page_connect_creates_encrypted_credential(api_client, user, monkeypatch):
    from integrations.meta_graph import MetaGraphClient

    api_client.force_authenticate(user=user)
    start_response = api_client.post(reverse("meta-oauth-start"), {}, format="json")
    state = start_response.json()["state"]

    monkeypatch.setattr(
        MetaGraphClient,
        "exchange_code",
        lambda self, *, code, redirect_uri: "user-token",  # noqa: ARG005
    )
    monkeypatch.setattr(
        MetaGraphClient,
        "list_pages",
        lambda self, *, user_access_token: [  # noqa: ARG005
            MetaPage(
                id="page-1",
                name="Primary Page",
                access_token="page-token-1",
                category="Business",
                tasks=["CREATE_CONTENT"],
                perms=["ADMINISTER"],
            )
        ],
    )

    exchange_response = api_client.post(
        reverse("meta-oauth-exchange"),
        {"code": "oauth-code", "state": state},
        format="json",
    )
    selection_token = exchange_response.json()["selection_token"]

    connect_response = api_client.post(
        reverse("meta-page-connect"),
        {"selection_token": selection_token, "page_id": "page-1"},
        format="json",
    )
    assert connect_response.status_code == 200
    payload = connect_response.json()
    assert payload["credential"]["provider"] == PlatformCredential.META
    assert payload["credential"]["account_id"] == "page-1"
    assert payload["page"]["name"] == "Primary Page"

    credential = PlatformCredential.objects.get(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="page-1",
    )
    assert credential.decrypt_access_token() == "page-token-1"
    assert cache.get(f"{META_OAUTH_SELECTION_CACHE_PREFIX}{selection_token}") is None
    assert AuditLog.all_objects.filter(
        action="meta_page_connected",
        resource_id=str(credential.id),
    ).exists()


@pytest.mark.django_db
def test_meta_oauth_exchange_rejects_state_for_other_user(
    api_client, user, tenant, monkeypatch
):
    from integrations.meta_graph import MetaGraphClient

    other_user = User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=tenant,
        password="password123",
    )

    state = signing.dumps(
        {
            "tenant_id": str(tenant.id),
            "user_id": str(other_user.id),
            "nonce": "abc",
        },
        salt=META_OAUTH_STATE_SALT,
    )

    api_client.force_authenticate(user=user)
    monkeypatch.setattr(
        MetaGraphClient,
        "exchange_code",
        lambda self, *, code, redirect_uri: "user-token",  # noqa: ARG005
    )
    monkeypatch.setattr(
        MetaGraphClient,
        "list_pages",
        lambda self, *, user_access_token: [],
    )

    response = api_client.post(
        reverse("meta-oauth-exchange"),
        {"code": "oauth-code", "state": state},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_meta_oauth_start_returns_503_when_not_configured(api_client, user, settings):
    settings.META_APP_ID = ""
    settings.META_APP_SECRET = ""
    api_client.force_authenticate(user=user)
    response = api_client.post(reverse("meta-oauth-start"), {}, format="json")
    assert response.status_code == 503
