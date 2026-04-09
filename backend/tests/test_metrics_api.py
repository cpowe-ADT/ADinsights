from __future__ import annotations

import csv
from datetime import date, timedelta
import logging
from pathlib import Path

import pytest
from django.utils import timezone

from django.conf import settings
from django.db import DatabaseError

from adapters.demo import DemoAdapter, clear_demo_seed_cache
from adapters.fake import FakeAdapter
from adapters.meta_direct import MetaDirectAdapter
from adapters.upload import UploadAdapter
from adapters.warehouse import (
    WAREHOUSE_DEFAULT_DETAIL,
    WAREHOUSE_SNAPSHOT_STATUS_DEFAULT,
    WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
    WAREHOUSE_SNAPSHOT_STATUS_KEY,
    WAREHOUSE_STALE_DETAIL,
    WAREHOUSE_UNAVAILABLE_CODE,
    WAREHOUSE_UNAVAILABLE_REASON_DEFAULT,
    WAREHOUSE_UNAVAILABLE_REASON_STALE,
)
from analytics.models import Ad, AdAccount, AdSet, Campaign, RawPerformanceRecord, TenantMetricsSnapshot
from core.metrics import reset_metrics


@pytest.fixture(autouse=True)
def enable_fake_adapter(settings):
    settings.ENABLE_FAKE_ADAPTER = True
    settings.ENABLE_DEMO_ADAPTER = False


@pytest.fixture
def enable_warehouse_adapter(settings):
    settings.ENABLE_WAREHOUSE_ADAPTER = True


@pytest.fixture
def enable_meta_direct_adapter(settings):
    settings.ENABLE_META_DIRECT_ADAPTER = True


def _seed_meta_direct_reporting(*, tenant, account_external_id: str = "act_697812007883214") -> AdAccount:
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id=account_external_id,
        account_id=account_external_id.replace("act_", ""),
        name="JDIC Adtelligent Ad Account",
        currency="USD",
        status="ACTIVE",
    )
    campaign = Campaign.objects.create(
        tenant=tenant,
        ad_account=account,
        external_id="cmp-1",
        name="Deposit Insurance Matters",
        platform="meta",
        account_external_id=account.external_id,
        status="ACTIVE",
        objective="OUTCOME_AWARENESS",
        currency="USD",
    )
    adset = AdSet.objects.create(
        tenant=tenant,
        campaign=campaign,
        external_id="adset-1",
        name="JDIC Awareness Ad Set",
        status="ACTIVE",
        bid_strategy="LOWEST_COST_WITHOUT_CAP",
        daily_budget=120,
    )
    ad = Ad.objects.create(
        tenant=tenant,
        adset=adset,
        external_id="ad-1",
        name="Creative A",
        status="ACTIVE",
        preview_url="https://example.com/preview",
        creative={"thumbnail_url": "https://example.com/thumb.jpg"},
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        campaign=campaign,
        adset=adset,
        ad=ad,
        external_id=ad.external_id,
        source="meta",
        level="ad",
        date=date(2026, 4, 3),
        impressions=1000,
        reach=800,
        clicks=50,
        spend=75,
        cpc=1.5,
        cpm=75,
        conversions=6,
        currency="USD",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        campaign=campaign,
        adset=adset,
        ad=ad,
        external_id=ad.external_id,
        source="meta",
        level="ad",
        date=date(2026, 4, 4),
        impressions=800,
        reach=640,
        clicks=40,
        spend=60,
        cpc=1.5,
        cpm=75,
        conversions=4,
        currency="USD",
    )
    return account


@pytest.mark.django_db
def test_adapters_endpoint_lists_enabled_adapters(api_client, user, enable_meta_direct_adapter):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/adapters/")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        MetaDirectAdapter().metadata(),
        FakeAdapter().metadata(),
        UploadAdapter().metadata(),
    ]


@pytest.fixture
def enable_demo_adapter(settings):
    settings.ENABLE_DEMO_ADAPTER = True


@pytest.mark.django_db
def test_adapters_endpoint_includes_demo_options(api_client, user, enable_demo_adapter, enable_meta_direct_adapter):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/adapters/")

    assert response.status_code == 200
    payload = response.json()
    demo_metadata = DemoAdapter().metadata()
    meta_direct_metadata = MetaDirectAdapter().metadata()
    fake_metadata = FakeAdapter().metadata()
    upload_metadata = UploadAdapter().metadata()
    assert payload == [meta_direct_metadata, demo_metadata, fake_metadata, upload_metadata]
    assert demo_metadata["options"]["demo_tenants"]  # type: ignore[index]


@pytest.mark.django_db
def test_adapters_endpoint_requires_authentication(api_client):
    response = api_client.get("/api/adapters/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_dataset_status_requires_authentication(api_client):
    response = api_client.get("/api/datasets/status/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_dataset_status_reports_adapter_disabled(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/datasets/status/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live"]["enabled"] is False
    assert payload["live"]["reason"] == "adapter_disabled"
    assert payload["warehouse_adapter_enabled"] is False
    assert payload["demo"]["enabled"] is True
    assert payload["demo"]["source"] == "fake"


@pytest.mark.django_db
def test_dataset_status_reports_missing_snapshot(api_client, user, enable_warehouse_adapter):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/datasets/status/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live"]["enabled"] is False
    assert payload["live"]["reason"] == "missing_snapshot"
    assert payload["warehouse_adapter_enabled"] is True


@pytest.mark.django_db
def test_dataset_status_reports_stale_snapshot(api_client, user, enable_warehouse_adapter, settings):
    api_client.force_authenticate(user=user)
    settings.METRICS_SNAPSHOT_STALE_TTL_SECONDS = 60
    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {"summary": {"currency": "USD"}},
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
        },
        generated_at=timezone.now() - timedelta(minutes=5),
    )

    response = api_client.get("/api/datasets/status/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live"]["enabled"] is False
    assert payload["live"]["reason"] == "stale_snapshot"
    assert payload["live"]["snapshot_generated_at"] is not None


@pytest.mark.django_db
def test_dataset_status_reports_default_snapshot(api_client, user, enable_warehouse_adapter):
    api_client.force_authenticate(user=user)
    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {"summary": {"currency": "USD"}},
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_DEFAULT,
            "_warehouse_snapshot_status_detail": "Warehouse aggregate view is missing locally.",
        },
        generated_at=timezone.now(),
    )

    response = api_client.get("/api/datasets/status/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live"]["enabled"] is False
    assert payload["live"]["reason"] == "default_snapshot"
    assert payload["live"]["detail"] == "Warehouse aggregate view is missing locally."


@pytest.mark.django_db
def test_dataset_status_reports_ready_snapshot(api_client, user, enable_warehouse_adapter):
    api_client.force_authenticate(user=user)
    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {"summary": {"currency": "USD"}},
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
        },
        generated_at=timezone.now(),
    )

    response = api_client.get("/api/datasets/status/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live"]["enabled"] is True
    assert payload["live"]["reason"] == "ready"


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
def test_metrics_meta_direct_adapter_returns_aggregated_payload(
    api_client,
    user,
    enable_meta_direct_adapter,
):
    api_client.force_authenticate(user=user)
    account = _seed_meta_direct_reporting(tenant=user.tenant)
    records = list(
        RawPerformanceRecord.objects.filter(tenant=user.tenant, ad_account=account).order_by("pk")
    )

    response = api_client.get(
        "/api/metrics/",
        {
            "source": "meta_direct",
            "account_id": account.external_id,
            "start_date": "2026-04-03",
            "end_date": "2026-04-04",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"]["summary"]["totalSpend"] == pytest.approx(135.0)
    assert payload["campaign"]["summary"]["totalClicks"] == 90
    assert payload["campaign"]["rows"][0]["name"] == "Deposit Insurance Matters"
    assert payload["creative"][0]["name"] == "Creative A"
    assert payload["budget"][0]["monthlyBudget"] == pytest.approx(3600.0)
    assert payload["availability"]["budget"]["status"] == "available"
    assert payload["availability"]["parish_map"]["reason"] == "geo_unavailable"
    assert payload["snapshot_generated_at"] == max(
        (record.ingested_at or record.updated_at).isoformat() for record in records
    )


@pytest.mark.django_db
def test_combined_metrics_meta_direct_source_returns_live_meta_payload(
    api_client,
    user,
    enable_meta_direct_adapter,
):
    api_client.force_authenticate(user=user)
    _seed_meta_direct_reporting(tenant=user.tenant)
    expected_snapshot_generated_at = max(
        (record.ingested_at or record.updated_at).isoformat()
        for record in RawPerformanceRecord.objects.filter(tenant=user.tenant, source="meta")
    )

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": MetaDirectAdapter.key,
            "start_date": "2026-04-03",
            "end_date": "2026-04-04",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"]["summary"]["totalConversions"] == 10
    assert payload["campaign"]["trend"][0]["date"] == "2026-04-03"
    assert payload["availability"]["campaign"]["status"] == "available"
    assert payload["availability"]["parish_map"]["status"] == "unavailable"
    assert payload["snapshot_generated_at"] == expected_snapshot_generated_at


@pytest.mark.django_db
def test_meta_direct_adapter_accepts_list_channel_filters(user, enable_meta_direct_adapter):
    _seed_meta_direct_reporting(tenant=user.tenant)

    payload = MetaDirectAdapter().fetch_metrics(
        tenant_id=str(user.tenant_id),
        options={
            "start_date": "2026-04-03",
            "end_date": "2026-04-04",
            "channels": ["meta"],
        },
    )

    assert payload["campaign"]["summary"]["totalSpend"] == pytest.approx(135.0)
    assert payload["availability"]["campaign"]["status"] == "available"


@pytest.mark.django_db
def test_combined_metrics_meta_direct_empty_account_preserves_null_snapshot_generated_at(
    api_client,
    user,
    enable_meta_direct_adapter,
):
    api_client.force_authenticate(user=user)
    AdAccount.objects.create(
        tenant=user.tenant,
        external_id="act_791712443035541",
        account_id="791712443035541",
        name="Students' Loan Bureau (SLB)",
        currency="USD",
        status="ACTIVE",
    )

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": MetaDirectAdapter.key,
            "account_id": "act_791712443035541",
            "start_date": "2026-03-30",
            "end_date": "2026-04-05",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["campaign"]["reason"] == "no_recent_data"
    assert payload["snapshot_generated_at"] is None


@pytest.mark.django_db
def test_combined_metrics_snapshot_hit_preserves_explicit_null_snapshot_generated_at(
    api_client,
    user,
    enable_meta_direct_adapter,
    settings,
):
    settings.METRICS_SNAPSHOT_TTL = 600
    api_client.force_authenticate(user=user)

    snapshot = TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source=MetaDirectAdapter.key,
        payload={
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
            "snapshot_generated_at": None,
        },
        generated_at=timezone.now(),
    )

    response = api_client.get("/api/metrics/combined/", {"source": MetaDirectAdapter.key})

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_generated_at"] is None
    snapshot.refresh_from_db()
    assert snapshot.payload["snapshot_generated_at"] is None


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

    response = api_client.get("/api/metrics/combined/", {"source": "fake"})

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
def test_combined_metrics_requires_explicit_source_without_warehouse(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/metrics/combined/")

    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "Explicit source is required when the warehouse adapter is unavailable."
    )


@pytest.mark.django_db
def test_demo_seed_requires_feature_flag(api_client, user, settings):
    api_client.force_authenticate(user=user)
    settings.ENABLE_DEMO_GENERATION = False

    response = api_client.post("/api/demo/seed/")

    assert response.status_code == 403


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

    response = api_client.get("/api/metrics/combined/", {"source": "fake"})
    assert response.status_code == 200
    first_payload = response.json()
    assert first_payload["campaign"]["summary"]["currency"] == "JMD"
    assert "snapshot_generated_at" in first_payload

    def fail_fetch(*args, **kwargs):  # noqa: D401 - test helper
        raise AssertionError("adapter should not be invoked when cache is valid")

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", fail_fetch, raising=False)

    response = api_client.get("/api/metrics/combined/", {"source": "fake"})
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

    response = api_client.get("/api/metrics/combined/", {"source": "fake"})
    assert response.json()["campaign"]["summary"]["currency"] == "USD"

    response = api_client.get("/api/metrics/combined/", {"source": "fake", "cache": "false"})
    assert response.json()["campaign"]["summary"]["currency"] == "CAD"


@pytest.mark.django_db
def test_combined_metrics_stale_snapshot_refreshes(monkeypatch, api_client, user, settings):
    settings.METRICS_SNAPSHOT_TTL = 10
    api_client.force_authenticate(user=user)

    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="fake",
        payload={
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
            "snapshot_generated_at": (timezone.now() - timedelta(minutes=5)).isoformat(),
        },
        generated_at=timezone.now() - timedelta(minutes=5),
    )

    def refreshed_payload(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return {
            "campaign": {"summary": {"currency": "CAD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", refreshed_payload, raising=False)

    response = api_client.get("/api/metrics/combined/", {"source": "fake"})
    assert response.status_code == 200
    assert response.json()["campaign"]["summary"]["currency"] == "CAD"

    snapshot = TenantMetricsSnapshot.objects.get(tenant=user.tenant, source="fake")
    assert snapshot.payload["campaign"]["summary"]["currency"] == "CAD"


@pytest.mark.django_db
def test_combined_metrics_stale_snapshot_noop_write_when_payload_unchanged(
    monkeypatch, api_client, user, settings
):
    settings.METRICS_SNAPSHOT_TTL = 10
    api_client.force_authenticate(user=user)

    generated_at = timezone.now() - timedelta(minutes=5)
    payload = {
        "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
        "creative": [],
        "budget": [],
        "parish": [],
        "snapshot_generated_at": generated_at.isoformat(),
    }
    snapshot = TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="fake",
        payload=payload,
        generated_at=generated_at,
    )
    initial_updated_at = snapshot.updated_at

    def unchanged_payload(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return payload

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", unchanged_payload, raising=False)

    captured_records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - standard handler hook
            captured_records.append(record)

    handler = CaptureHandler()
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    try:
        response = api_client.get("/api/metrics/combined/", {"source": "fake"})
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    snapshot.refresh_from_db()
    assert snapshot.updated_at == initial_updated_at
    assert snapshot.generated_at == generated_at
    assert captured_records
    runtime_metrics = captured_records[-1].runtime["metrics"]
    assert runtime_metrics["cache_outcome"] == "miss"
    assert runtime_metrics["snapshot_written"] is False


@pytest.mark.django_db
def test_combined_metrics_emits_runtime_metrics_context(monkeypatch, api_client, user):
    api_client.force_authenticate(user=user)

    def payload(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return {
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", payload, raising=False)

    captured_records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - standard handler hook
            captured_records.append(record)

    handler = CaptureHandler()
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    try:
        response = api_client.get("/api/metrics/combined/", {"source": "fake", "cache": "false"})
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    assert captured_records
    latest = captured_records[-1]
    runtime_metrics = latest.runtime["metrics"]
    assert runtime_metrics["source"] == "fake"
    assert runtime_metrics["cache_outcome"] == "disabled"
    assert runtime_metrics["status"] == "success"
    assert runtime_metrics["has_filters"] is False
    assert runtime_metrics["snapshot_written"] is True
    assert runtime_metrics["query_count"] >= 1


@pytest.mark.django_db
def test_combined_metrics_cache_miss_without_snapshot_limits_query_count(
    monkeypatch, api_client, user
):
    api_client.force_authenticate(user=user)

    def payload(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return {
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", payload, raising=False)

    captured_records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - standard handler hook
            captured_records.append(record)

    handler = CaptureHandler()
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    try:
        response = api_client.get("/api/metrics/combined/", {"source": "fake"})
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    assert captured_records
    runtime_metrics = captured_records[-1].runtime["metrics"]
    assert runtime_metrics["cache_outcome"] == "miss"
    assert runtime_metrics["query_count"] <= 2


@pytest.mark.django_db
def test_combined_metrics_cache_disabled_updates_existing_snapshot_with_single_write_query(
    monkeypatch, api_client, user
):
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

    def payload(self, *, tenant_id, options=None):  # noqa: D401 - test helper
        return {
            "campaign": {"summary": {"currency": "CAD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", payload, raising=False)

    captured_records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - standard handler hook
            captured_records.append(record)

    handler = CaptureHandler()
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    try:
        response = api_client.get("/api/metrics/combined/", {"source": "fake", "cache": "false"})
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    assert captured_records
    runtime_metrics = captured_records[-1].runtime["metrics"]
    assert runtime_metrics["cache_outcome"] == "disabled"
    assert runtime_metrics["query_count"] == 1


@pytest.mark.django_db
def test_combined_metrics_exports_observability_metrics(api_client, user):
    reset_metrics()
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/metrics/combined/", {"source": "fake"})
    assert response.status_code == 200

    metrics_response = api_client.get("/metrics/app/")
    assert metrics_response.status_code == 200
    body = metrics_response.content.decode("utf-8")
    assert "combined_metrics_requests_total" in body
    assert "combined_metrics_request_duration_seconds" in body
    assert "combined_metrics_query_count" in body
    assert "combined_metrics_snapshot_writes_total" in body


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
        {
            "source": "fake",
            "start_date": "2024-09-01",
            "end_date": "2024-09-03",
            "parish": "Kingston",
        },
    )

    assert response.status_code == 200
    options = captured["options"]
    assert options["start_date"] == date(2024, 9, 1)
    assert options["end_date"] == date(2024, 9, 3)
    assert options["parish"] == ["Kingston"]


@pytest.mark.django_db
def test_combined_metrics_accepts_channel_and_campaign_search_filters(
    monkeypatch, api_client, user
):
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
        {
            "source": "fake",
            "channels": ["meta", "google_ads"],
            "campaign_search": "Kingston launch",
        },
    )

    assert response.status_code == 200
    options = captured["options"]
    assert options["channels"] == ["meta", "google_ads"]
    assert options["campaign_search"] == "Kingston launch"


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
        {"source": "fake", "parish": ["Kingston", "St James"]},
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

    response = api_client.get("/api/metrics/combined/", {"source": "fake", "parish": "Kingston"})
    assert response.status_code == 200
    assert response.json()["campaign"]["summary"]["currency"] == "CAD"

    snapshot = TenantMetricsSnapshot.objects.get(tenant=user.tenant, source="fake")
    assert snapshot.payload["campaign"]["summary"]["currency"] == "USD"


@pytest.mark.django_db
def test_combined_metrics_account_filter_bypasses_cache(monkeypatch, api_client, user):
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
        assert options["account_id"] == "act_791712443035541"
        return {
            "campaign": {"summary": {"currency": "CAD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
        }

    monkeypatch.setattr(FakeAdapter, "fetch_metrics", filtered_payload, raising=False)

    response = api_client.get(
        "/api/metrics/combined/",
        {"source": "fake", "account_id": "act_791712443035541"},
    )
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
        WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
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
    assert payload["campaign"]["summary"]["currency"] == "JMD"
    assert payload["creative"] == snapshot_payload["creative"]
    assert payload["budget"] == snapshot_payload["budget"]
    assert payload["parish"] == snapshot_payload["parish"]
    assert payload["coverage"] == {"startDate": None, "endDate": None}
    assert payload["availability"]["campaign"]["reason"] == "no_recent_data"
    assert "snapshot_generated_at" in payload


@pytest.mark.django_db
def test_combined_metrics_warehouse_filtered_query_supports_channels_and_campaign_search(
    monkeypatch, api_client, user, settings, enable_warehouse_adapter
):
    settings.ENABLE_FAKE_ADAPTER = False
    api_client.force_authenticate(user=user)

    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
            "snapshot_generated_at": timezone.now().isoformat(),
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
        },
        generated_at=timezone.now(),
    )

    captured: dict[str, object] = {}

    def filtered_payload(*, tenant, tenant_id, options, ttl_seconds):  # noqa: D401
        captured["tenant_id"] = tenant_id
        captured["options"] = options
        captured["ttl_seconds"] = ttl_seconds
        return {
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
            "coverage": {"startDate": "2026-02-01", "endDate": "2026-02-28"},
            "availability": {
                "campaign": {"status": "empty", "reason": "no_matching_filters"},
                "creative": {"status": "empty", "reason": "no_matching_filters"},
                "budget": {"status": "empty", "reason": "no_matching_filters"},
                "parish_map": {
                    "status": "unavailable",
                    "reason": "geo_unavailable",
                    "coverage_percent": 0.45,
                },
            },
            "snapshot_generated_at": timezone.now().isoformat(),
        }

    monkeypatch.setattr(
        "analytics.combined_metrics_service.load_filtered_warehouse_metrics",
        filtered_payload,
    )

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": "warehouse",
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
            "account_id": "act_791712443035541",
            "channels": ["meta", "google_ads"],
            "campaign_search": "Debt Reset",
            "parish": "Kingston",
        },
    )

    assert response.status_code == 200
    assert captured["tenant_id"] == str(user.tenant_id)
    options = captured["options"]
    assert options["start_date"] == date(2026, 2, 1)
    assert options["end_date"] == date(2026, 2, 28)
    assert options["account_id"] == "act_791712443035541"
    assert options["channels"] == ["meta", "google_ads"]
    assert options["campaign_search"] == "Debt Reset"
    assert options["parish"] == ["Kingston"]
    assert response.json()["coverage"]["startDate"] == "2026-02-01"
    assert response.json()["availability"]["parish_map"]["coverage_percent"] == 0.45


@pytest.mark.django_db
def test_combined_metrics_warehouse_filtered_query_falls_back_to_snapshot_on_sqlite_error(
    monkeypatch, api_client, user, settings, enable_warehouse_adapter
):
    settings.ENABLE_FAKE_ADAPTER = False
    api_client.force_authenticate(user=user)

    generated_at = timezone.now()
    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {
                "summary": {
                    "currency": "JMD",
                    "totalSpend": 1200,
                    "totalImpressions": 1000,
                    "totalClicks": 50,
                    "totalConversions": 5,
                    "averageRoas": 0.1,
                },
                "trend": [],
                "rows": [],
            },
            "creative": [],
            "budget": [],
            "parish": [],
            "coverage": {"startDate": "2026-03-01", "endDate": "2026-03-30"},
            "availability": {
                "campaign": {"status": "empty", "reason": "no_matching_filters"},
                "creative": {"status": "empty", "reason": "no_matching_filters"},
                "budget": {"status": "empty", "reason": "no_matching_filters"},
                "parish_map": {
                    "status": "empty",
                    "reason": "no_matching_filters",
                    "coverage_percent": 0.0,
                },
            },
            "snapshot_generated_at": generated_at.isoformat(),
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
        },
        generated_at=generated_at,
    )

    def explode(*args, **kwargs):  # noqa: ANN002, ANN003
        raise DatabaseError("sqlite fallback")

    monkeypatch.setattr(
        "analytics.combined_metrics_service.load_filtered_warehouse_metrics",
        explode,
    )

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": "warehouse",
            "start_date": "2026-03-01",
            "end_date": "2026-03-30",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"]["summary"]["currency"] == "JMD"
    assert payload["coverage"] == {"startDate": "2026-03-01", "endDate": "2026-03-30"}
    assert payload["snapshot_generated_at"] == generated_at.isoformat()


@pytest.mark.django_db
def test_combined_metrics_rejects_default_warehouse_snapshot(
    api_client, user, settings, enable_warehouse_adapter
):
    settings.ENABLE_FAKE_ADAPTER = False
    api_client.force_authenticate(user=user)

    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
            "snapshot_generated_at": timezone.now().isoformat(),
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_DEFAULT,
        },
        generated_at=timezone.now(),
    )

    response = api_client.get("/api/metrics/combined/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": WAREHOUSE_DEFAULT_DETAIL,
        "code": WAREHOUSE_UNAVAILABLE_CODE,
        "reason": WAREHOUSE_UNAVAILABLE_REASON_DEFAULT,
    }


@pytest.mark.django_db
def test_combined_metrics_rejects_stale_warehouse_snapshot(
    api_client, user, settings, enable_warehouse_adapter
):
    settings.ENABLE_FAKE_ADAPTER = False
    settings.METRICS_SNAPSHOT_STALE_TTL_SECONDS = 3600
    api_client.force_authenticate(user=user)

    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {"summary": {"currency": "USD"}, "trend": [], "rows": []},
            "creative": [],
            "budget": [],
            "parish": [],
            "snapshot_generated_at": (timezone.now() - timedelta(hours=2)).isoformat(),
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
        },
        generated_at=timezone.now() - timedelta(hours=2),
    )

    response = api_client.get("/api/metrics/combined/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": WAREHOUSE_STALE_DETAIL,
        "code": WAREHOUSE_UNAVAILABLE_CODE,
        "reason": WAREHOUSE_UNAVAILABLE_REASON_STALE,
    }


@pytest.mark.django_db
def test_fake_adapter_requires_flag(api_client, user, settings):
    settings.ENABLE_FAKE_ADAPTER = False
    settings.ENABLE_DEMO_ADAPTER = False
    settings.ENABLE_META_DIRECT_ADAPTER = False
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
