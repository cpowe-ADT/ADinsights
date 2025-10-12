from __future__ import annotations

from django.urls import reverse


def test_login_returns_tenant_id(api_client, user):
    response = api_client.post(
        reverse("token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert data["tenant_id"] == str(user.tenant_id)


def test_me_endpoint(api_client, user):
    token_resp = api_client.post(
        reverse("token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    )
    access = token_resp.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = api_client.get(reverse("me"))
    assert response.status_code == 200
    assert response.json()["tenant"] == str(user.tenant_id)
