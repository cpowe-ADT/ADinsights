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
    assert PlatformCredential.objects.count() == 1
    credential = PlatformCredential.objects.first()
    assert credential.decrypt_access_token() == "secret-token"
    assert credential.decrypt_refresh_token() == "refresh-token"
