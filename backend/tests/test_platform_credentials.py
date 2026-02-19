from __future__ import annotations

from django.urls import reverse

from integrations.models import PlatformCredential


def test_platform_credential_encryption(api_client, user, tenant):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    payload = {
        "provider": PlatformCredential.META,
        "account_id": "123",
        "access_token": "secret-token",
        "refresh_token": "refresh-token",
    }
    response = api_client.post(
        reverse("platformcredential-list"), payload, format="json"
    )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" not in body
    assert body["auth_mode"] == PlatformCredential.AUTH_MODE_USER_OAUTH
    assert body["token_status"] == PlatformCredential.TOKEN_STATUS_VALID
    assert body["granted_scopes"] == []
    assert body["declined_scopes"] == []
    assert PlatformCredential.objects.count() == 1
    credential = PlatformCredential.objects.first()
    assert credential.decrypt_access_token() == "secret-token"
    assert credential.decrypt_refresh_token() == "refresh-token"


def test_platform_credential_update_without_refresh_token(api_client, user, tenant):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    payload = {
        "provider": PlatformCredential.META,
        "account_id": "123",
        "access_token": "secret-token",
        "refresh_token": "refresh-token",
    }
    create_response = api_client.post(
        reverse("platformcredential-list"), payload, format="json"
    )
    assert create_response.status_code == 201
    credential = PlatformCredential.objects.first()

    update_response = api_client.patch(
        reverse("platformcredential-detail", args=[credential.id]),
        {"access_token": "updated-token"},
        format="json",
    )
    assert update_response.status_code == 200
    credential.refresh_from_db()
    assert credential.decrypt_access_token() == "updated-token"
    assert credential.decrypt_refresh_token() == "refresh-token"


def test_platform_credential_refresh_token_can_be_cleared(api_client, user, tenant):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    payload = {
        "provider": PlatformCredential.META,
        "account_id": "123",
        "access_token": "secret-token",
        "refresh_token": "refresh-token",
    }
    create_response = api_client.post(
        reverse("platformcredential-list"), payload, format="json"
    )
    assert create_response.status_code == 201
    credential = PlatformCredential.objects.first()

    update_response = api_client.patch(
        reverse("platformcredential-detail", args=[credential.id]),
        {"refresh_token": None},
        format="json",
    )
    assert update_response.status_code == 200
    credential.refresh_from_db()
    assert credential.decrypt_refresh_token() is None
