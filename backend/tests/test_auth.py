from __future__ import annotations

from django.test import override_settings
from django.urls import reverse


def test_token_endpoint_returns_access_and_refresh(api_client, user):
    response = api_client.post(
        reverse("jwt_token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert "refresh" in data


@override_settings(ENABLE_TENANCY=True)
def test_me_endpoint_returns_claims(api_client, user):
    token_resp = api_client.post(
        reverse("jwt_token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    )
    access = token_resp.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = api_client.get(
        reverse("me"),
        HTTP_X_TENANT_ID="tenant-header",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "tenant-header"
    assert payload["user"]["id"] == str(user.id)
