from __future__ import annotations

import pytest

from adapters.fake import FakeAdapter


@pytest.fixture(autouse=True)
def enable_fake_adapter(settings):
    settings.ENABLE_FAKE_ADAPTER = True


@pytest.mark.django_db
def test_adapters_endpoint_lists_fake_adapter(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/adapters/")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [FakeAdapter().metadata()]


@pytest.mark.django_db
def test_adapters_endpoint_requires_authentication(api_client):
    response = api_client.get("/api/adapters/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_metrics_fake_adapter_returns_static_payload(api_client, user):
    api_client.force_authenticate(user=user)
    adapter = FakeAdapter()

    response = api_client.get("/api/metrics/", {"source": "fake"})

    assert response.status_code == 200
    assert response.json() == adapter.fetch_metrics(tenant_id=str(user.tenant_id))


@pytest.mark.django_db
def test_metrics_defaults_to_fake_adapter(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/metrics/")

    assert response.status_code == 200
    assert response.json()["campaign"]["summary"]["currency"] == "USD"


@pytest.mark.django_db
def test_metrics_unknown_adapter_returns_400(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/metrics/", {"source": "missing"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown adapter 'missing'."


@pytest.mark.django_db
def test_metrics_requires_authentication(api_client):
    response = api_client.get("/api/metrics/", {"source": "fake"})

    assert response.status_code == 401
