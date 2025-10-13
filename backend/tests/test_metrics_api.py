from __future__ import annotations

import pytest
from django.utils import timezone

from adapters.fake import FakeAdapter
from analytics.models import TenantMetricsSnapshot


@pytest.fixture(autouse=True)
def enable_fake_adapter(settings):
    settings.ENABLE_FAKE_ADAPTER = True


@pytest.fixture
def enable_warehouse_adapter(settings):
    settings.ENABLE_WAREHOUSE_ADAPTER = True


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


@pytest.mark.django_db
def test_combined_metrics_endpoint_returns_sections(api_client, user):
    api_client.force_authenticate(user=user)
    adapter_payload = FakeAdapter().fetch_metrics(tenant_id=str(user.tenant_id))

    response = api_client.get("/api/metrics/combined/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"] == adapter_payload["campaign"]
    assert payload["creative"] == adapter_payload["creative"]
    assert payload["budget"] == adapter_payload["budget"]
    assert payload["parish"] == adapter_payload["parish"]


@pytest.mark.django_db
def test_combined_metrics_requires_auth(api_client):
    response = api_client.get("/api/metrics/combined/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_combined_metrics_uses_snapshot(monkeypatch, api_client, user, settings):
    settings.METRICS_SNAPSHOT_TTL = 600
    api_client.force_authenticate(user=user)

    expected = {
        "campaign": {"summary": {"currency": "JMD"}},
        "creative": [],
        "budget": [],
        "parish": [],
    }

    def fake_fetch(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return expected

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", fake_fetch, raising=False)

    response = api_client.get("/api/metrics/combined/")
    assert response.status_code == 200
    assert response.json() == expected

    def fail_fetch(*args, **kwargs):  # noqa: D401 - test helper
        raise AssertionError("adapter should not be invoked when cache is valid")

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", fail_fetch, raising=False)

    response = api_client.get("/api/metrics/combined/")
    assert response.status_code == 200
    assert response.json() == expected
    snapshot = TenantMetricsSnapshot.all_objects.get(tenant=user.tenant, source="fake")
    assert snapshot.payload == expected


@pytest.mark.django_db
def test_combined_metrics_cache_bypass(monkeypatch, api_client, user):
    api_client.force_authenticate(user=user)

    first_payload = {
        "campaign": {"summary": {"currency": "USD"}},
        "creative": [],
        "budget": [],
        "parish": [],
    }
    second_payload = {
        "campaign": {"summary": {"currency": "CAD"}},
        "creative": [],
        "budget": [],
        "parish": [],
    }

    responses = [first_payload, second_payload]

    def rotating_fetch(self, *, tenant_id, options=None):  # noqa: D401
        return responses.pop(0)

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", rotating_fetch, raising=False)

    response = api_client.get("/api/metrics/combined/")
    assert response.json()["campaign"]["summary"]["currency"] == "USD"

    response = api_client.get("/api/metrics/combined/", {"cache": "false"})
    assert response.json()["campaign"]["summary"]["currency"] == "CAD"


@pytest.mark.django_db
def test_combined_metrics_defaults_to_warehouse(api_client, user, settings, enable_warehouse_adapter):
    settings.ENABLE_FAKE_ADAPTER = False
    api_client.force_authenticate(user=user)

    snapshot_payload = {
        "campaign": {"summary": {"currency": "JMD"}, "trend": [], "rows": []},
        "creative": [],
        "budget": [],
        "parish": [],
    }

    TenantMetricsSnapshot.all_objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload=snapshot_payload,
        generated_at=timezone.now(),
    )

    response = api_client.get("/api/metrics/combined/")
    assert response.status_code == 200
    assert response.json() == snapshot_payload


@pytest.mark.django_db
def test_fake_adapter_requires_flag(api_client, user, settings):
    settings.ENABLE_FAKE_ADAPTER = False
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/metrics/", {"source": "fake"})

    assert response.status_code == 503
    assert response.json()["detail"] == "No analytics adapters are enabled."
