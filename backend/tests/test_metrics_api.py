from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from django.utils import timezone

from django.conf import settings

from adapters.demo import DemoAdapter, clear_demo_seed_cache
from adapters.fake import FakeAdapter
from analytics.models import TenantMetricsSnapshot


@pytest.fixture(autouse=True)
def enable_fake_adapter(settings):
    settings.ENABLE_FAKE_ADAPTER = True
    settings.ENABLE_DEMO_ADAPTER = False


@pytest.fixture
def enable_warehouse_adapter(settings):
    settings.ENABLE_WAREHOUSE_ADAPTER = True


@pytest.mark.django_db
def test_adapters_endpoint_lists_enabled_adapters(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/adapters/")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [FakeAdapter().metadata()]


@pytest.fixture
def enable_demo_adapter(settings):
    settings.ENABLE_DEMO_ADAPTER = True


@pytest.mark.django_db
def test_adapters_endpoint_includes_demo_options(api_client, user, enable_demo_adapter):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/adapters/")

    assert response.status_code == 200
    payload = response.json()
    demo_metadata = DemoAdapter().metadata()
    fake_metadata = FakeAdapter().metadata()
    assert payload == [demo_metadata, fake_metadata]
    assert demo_metadata["options"]["demo_tenants"]  # type: ignore[index]


@pytest.mark.django_db
def test_adapters_endpoint_requires_authentication(api_client):
    response = api_client.get("/api/adapters/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_metrics_fake_adapter_returns_static_payload(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/metrics/", {"source": "fake"})

    assert response.status_code == 200
    payload = response.json()
    expected = FakeAdapter().fetch_metrics(tenant_id=str(user.tenant_id))
    assert payload["campaign"] == expected["campaign"]
    assert payload["creative"] == expected["creative"]
    assert payload["budget"] == expected["budget"]
    assert payload["parish"] == expected["parish"]
    assert "snapshot_generated_at" in payload


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
    assert "snapshot_generated_at" in payload


@pytest.mark.django_db
def test_combined_metrics_requires_auth(api_client):
    response = api_client.get("/api/metrics/combined/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_combined_metrics_uses_snapshot(monkeypatch, api_client, user, settings):
    settings.METRICS_SNAPSHOT_TTL = 600
    api_client.force_authenticate(user=user)

    base_payload = {
        "campaign": {"summary": {"currency": "JMD"}},
        "creative": [],
        "budget": [],
        "parish": [],
    }

    def fake_fetch(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return base_payload

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", fake_fetch, raising=False)

    response = api_client.get("/api/metrics/combined/")
    assert response.status_code == 200
    first_payload = response.json()
    assert first_payload["campaign"]["summary"]["currency"] == "JMD"
    assert "snapshot_generated_at" in first_payload

    def fail_fetch(*args, **kwargs):  # noqa: D401 - test helper
        raise AssertionError("adapter should not be invoked when cache is valid")

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", fail_fetch, raising=False)

    response = api_client.get("/api/metrics/combined/")
    assert response.status_code == 200
    cached_payload = response.json()
    assert cached_payload == first_payload
    snapshot = TenantMetricsSnapshot.objects.get(tenant=user.tenant, source="fake")
    assert snapshot.payload == first_payload


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
def test_combined_metrics_accepts_filter_params(monkeypatch, api_client, user):
    api_client.force_authenticate(user=user)
    captured: dict[str, object] = {}

    def fake_fetch(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        captured["options"] = options or {}
        return {
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", fake_fetch, raising=False)

    response = api_client.get(
        "/api/metrics/combined/",
        {"start_date": "2024-09-01", "end_date": "2024-09-03", "parish": "Kingston"},
    )

    assert response.status_code == 200
    options = captured["options"]
    assert options["start_date"] == date(2024, 9, 1)
    assert options["end_date"] == date(2024, 9, 3)
    assert options["parish"] == ["Kingston"]


@pytest.mark.django_db
def test_combined_metrics_accepts_repeated_parish_params(monkeypatch, api_client, user):
    api_client.force_authenticate(user=user)
    captured: dict[str, object] = {}

    def fake_fetch(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        captured["options"] = options or {}
        return {
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", fake_fetch, raising=False)

    response = api_client.get(
        "/api/metrics/combined/",
        {"parish": ["Kingston", "St James"]},
    )

    assert response.status_code == 200
    options = captured["options"]
    assert options["parish"] == ["Kingston", "St James"]


@pytest.mark.django_db
def test_combined_metrics_filters_do_not_update_cache(monkeypatch, api_client, user):
    api_client.force_authenticate(user=user)

    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="fake",
        payload={
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
            "snapshot_generated_at": timezone.now().isoformat(),
        },
        generated_at=timezone.now(),
    )

    def filtered_payload(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return {
            "campaign": {"summary": {"currency": "CAD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", filtered_payload, raising=False)

    response = api_client.get("/api/metrics/combined/", {"parish": "Kingston"})
    assert response.status_code == 200
    assert response.json()["campaign"]["summary"]["currency"] == "CAD"

    snapshot = TenantMetricsSnapshot.objects.get(tenant=user.tenant, source="fake")
    assert snapshot.payload["campaign"]["summary"]["currency"] == "USD"

@pytest.mark.django_db
def test_combined_metrics_defaults_to_warehouse(api_client, user, settings, enable_warehouse_adapter):
    settings.ENABLE_FAKE_ADAPTER = False
    api_client.force_authenticate(user=user)

    snapshot_payload = {
        "campaign": {"summary": {"currency": "JMD"}, "trend": [], "rows": []},
        "creative": [],
        "budget": [],
        "parish": [],
        "snapshot_generated_at": timezone.now().isoformat(),
    }

    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload=snapshot_payload,
        generated_at=timezone.now(),
    )

    response = api_client.get("/api/metrics/combined/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"] == snapshot_payload["campaign"]
    assert payload["creative"] == snapshot_payload["creative"]
    assert payload["budget"] == snapshot_payload["budget"]
    assert payload["parish"] == snapshot_payload["parish"]
    assert "snapshot_generated_at" in payload


@pytest.mark.django_db
def test_fake_adapter_requires_flag(api_client, user, settings):
    settings.ENABLE_FAKE_ADAPTER = False
    settings.ENABLE_DEMO_ADAPTER = False
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/metrics/", {"source": "fake"})

    assert response.status_code == 503
    assert response.json()["detail"] == "No analytics adapters are enabled."


@pytest.mark.django_db
def test_demo_adapter_returns_curated_payload(api_client, user, enable_demo_adapter):
    settings.ENABLE_FAKE_ADAPTER = False
    api_client.force_authenticate(user=user)

    response = api_client.get(
        "/api/metrics/",
        {"source": "demo", "demo_tenant": "grace-kennedy"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "grace-kennedy"
    assert payload["campaign"]["summary"]["currency"] == "USD"


def _write_demo_seed_csvs(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)

    def write_csv(name: str, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path = base_dir / name
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    snapshot = "2024-09-05T00:00:00Z"
    write_csv(
        "dim_tenants.csv",
        ["tenant_id", "tenant_name", "currency", "timezone", "snapshot_generated_at"],
        [
            {
                "tenant_id": "bank-of-jamaica",
                "tenant_name": "Bank of Jamaica",
                "currency": "JMD",
                "timezone": "America/Jamaica",
                "snapshot_generated_at": snapshot,
            },
            {
                "tenant_id": "grace-kennedy",
                "tenant_name": "GraceKennedy",
                "currency": "USD",
                "timezone": "America/Jamaica",
                "snapshot_generated_at": snapshot,
            },
        ],
    )

    write_csv(
        "dim_campaigns.csv",
        [
            "tenant_id",
            "campaign_id",
            "channel",
            "campaign_name",
            "objective",
            "status",
            "start_date",
            "end_date",
            "parish",
        ],
        [
            {
                "tenant_id": "bank-of-jamaica",
                "campaign_id": "BOJ-001",
                "channel": "Meta",
                "campaign_name": "BOJ Awareness",
                "objective": "Awareness",
                "status": "ACTIVE",
                "start_date": "2024-08-01",
                "end_date": "",
                "parish": "Kingston",
            },
            {
                "tenant_id": "grace-kennedy",
                "campaign_id": "GK-001",
                "channel": "Google Ads",
                "campaign_name": "GK Leads",
                "objective": "Leads",
                "status": "ACTIVE",
                "start_date": "2024-08-10",
                "end_date": "",
                "parish": "St James",
            },
        ],
    )

    write_csv(
        "dim_creatives.csv",
        [
            "tenant_id",
            "campaign_id",
            "channel",
            "creative_id",
            "creative_name",
            "creative_type",
        ],
        [
            {
                "tenant_id": "bank-of-jamaica",
                "campaign_id": "BOJ-001",
                "channel": "Meta",
                "creative_id": "CR-BOJ-001",
                "creative_name": "BOJ Video",
                "creative_type": "video",
            },
            {
                "tenant_id": "grace-kennedy",
                "campaign_id": "GK-001",
                "channel": "Google Ads",
                "creative_id": "CR-GK-001",
                "creative_name": "GK Search",
                "creative_type": "image",
            },
        ],
    )

    write_csv(
        "fact_daily_campaign_metrics.csv",
        [
            "date",
            "tenant_id",
            "channel",
            "campaign_id",
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "revenue",
            "roas",
            "snapshot_generated_at",
        ],
        [
            {
                "date": "2024-09-01",
                "tenant_id": "bank-of-jamaica",
                "channel": "Meta",
                "campaign_id": "BOJ-001",
                "spend": 1000,
                "impressions": 10000,
                "clicks": 200,
                "conversions": 10,
                "revenue": 5000,
                "roas": 5.0,
                "snapshot_generated_at": snapshot,
            },
            {
                "date": "2024-09-02",
                "tenant_id": "bank-of-jamaica",
                "channel": "Meta",
                "campaign_id": "BOJ-001",
                "spend": 800,
                "impressions": 9000,
                "clicks": 180,
                "conversions": 8,
                "revenue": 3600,
                "roas": 4.5,
                "snapshot_generated_at": snapshot,
            },
            {
                "date": "2024-09-01",
                "tenant_id": "grace-kennedy",
                "channel": "Google Ads",
                "campaign_id": "GK-001",
                "spend": 200,
                "impressions": 8000,
                "clicks": 160,
                "conversions": 20,
                "revenue": 1000,
                "roas": 5.0,
                "snapshot_generated_at": snapshot,
            },
            {
                "date": "2024-09-02",
                "tenant_id": "grace-kennedy",
                "channel": "Google Ads",
                "campaign_id": "GK-001",
                "spend": 220,
                "impressions": 8500,
                "clicks": 170,
                "conversions": 18,
                "revenue": 900,
                "roas": 4.09,
                "snapshot_generated_at": snapshot,
            },
        ],
    )

    write_csv(
        "fact_daily_parish_metrics.csv",
        [
            "date",
            "tenant_id",
            "channel",
            "parish",
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "revenue",
            "roas",
        ],
        [
            {
                "date": "2024-09-01",
                "tenant_id": "bank-of-jamaica",
                "channel": "Meta",
                "parish": "Kingston",
                "spend": 1000,
                "impressions": 10000,
                "clicks": 200,
                "conversions": 10,
                "revenue": 5000,
                "roas": 5.0,
            },
            {
                "date": "2024-09-01",
                "tenant_id": "grace-kennedy",
                "channel": "Google Ads",
                "parish": "St James",
                "spend": 200,
                "impressions": 8000,
                "clicks": 160,
                "conversions": 20,
                "revenue": 1000,
                "roas": 5.0,
            },
        ],
    )

    write_csv(
        "fact_daily_creative_metrics.csv",
        [
            "date",
            "tenant_id",
            "channel",
            "campaign_id",
            "creative_id",
            "creative_type",
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "revenue",
            "roas",
        ],
        [
            {
                "date": "2024-09-01",
                "tenant_id": "bank-of-jamaica",
                "channel": "Meta",
                "campaign_id": "BOJ-001",
                "creative_id": "CR-BOJ-001",
                "creative_type": "video",
                "spend": 400,
                "impressions": 4000,
                "clicks": 80,
                "conversions": 4,
                "revenue": 2000,
                "roas": 5.0,
            },
            {
                "date": "2024-09-01",
                "tenant_id": "grace-kennedy",
                "channel": "Google Ads",
                "campaign_id": "GK-001",
                "creative_id": "CR-GK-001",
                "creative_type": "image",
                "spend": 90,
                "impressions": 3600,
                "clicks": 70,
                "conversions": 9,
                "revenue": 450,
                "roas": 5.0,
            },
        ],
    )

    write_csv(
        "plan_monthly_budgets.csv",
        ["month", "tenant_id", "channel", "campaign_id", "planned_budget"],
        [
            {
                "month": "2024-09-01",
                "tenant_id": "bank-of-jamaica",
                "channel": "Meta",
                "campaign_id": "BOJ-001",
                "planned_budget": 5000,
            },
            {
                "month": "2024-09-01",
                "tenant_id": "grace-kennedy",
                "channel": "Google Ads",
                "campaign_id": "GK-001",
                "planned_budget": 1200,
            },
        ],
    )


@pytest.fixture
def demo_seed_dir(tmp_path, settings):
    seed_dir = tmp_path / "demo"
    _write_demo_seed_csvs(seed_dir)
    settings.DEMO_SEED_DIR = str(seed_dir)
    clear_demo_seed_cache()
    yield seed_dir
    clear_demo_seed_cache()


@pytest.mark.django_db
def test_demo_adapter_reads_seeded_payload(api_client, user, settings, demo_seed_dir):
    settings.ENABLE_FAKE_ADAPTER = False
    settings.ENABLE_DEMO_ADAPTER = True
    api_client.force_authenticate(user=user)

    response = api_client.get(
        "/api/metrics/combined/",
        {"source": "demo", "demo_tenant": "grace-kennedy"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "grace-kennedy"
    assert payload["campaign"]["summary"]["currency"] == "USD"
    assert payload["campaign"]["trend"]
    assert payload["budget"]
    assert payload["snapshot_generated_at"].startswith("2024-09-05")

    adapters_response = api_client.get("/api/adapters/")
    assert adapters_response.status_code == 200
    demo_adapter = next(
        item for item in adapters_response.json() if item["key"] == "demo"
    )
    tenant_ids = {tenant["id"] for tenant in demo_adapter["options"]["demo_tenants"]}
    assert tenant_ids == {"bank-of-jamaica", "grace-kennedy"}
