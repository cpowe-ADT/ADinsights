from __future__ import annotations

import json
import logging
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from integrations.models import AirbyteConnection, TenantAirbyteSyncStatus


@pytest.mark.django_db
def test_airbyte_health_requires_configuration(api_client, settings):
    settings.AIRBYTE_API_URL = ""
    settings.AIRBYTE_API_TOKEN = ""
    settings.AIRBYTE_USERNAME = ""
    settings.AIRBYTE_PASSWORD = ""

    response = api_client.get("/api/health/airbyte/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "misconfigured"
    assert payload["configured"] is False


@pytest.mark.django_db
def test_airbyte_health_reports_missing_sync(api_client, settings):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    response = api_client.get("/api/health/airbyte/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "no_recent_sync"


@pytest.mark.django_db
def test_airbyte_health_ok_with_recent_sync(api_client, tenant, settings):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=now,
        last_job_status="succeeded",
        last_job_id="99",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)

    response = api_client.get("/api/health/airbyte/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["last_sync"]["last_job_status"] == "succeeded"


@pytest.mark.django_db
def test_airbyte_health_flags_stale_sync(api_client, tenant, settings):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    stale_time = timezone.now() - timedelta(hours=2)
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Google",
        connection_id=uuid.uuid4(),
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=stale_time,
        last_job_status="succeeded",
        last_job_id="1",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)

    response = api_client.get("/api/health/airbyte/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "stale"
    assert payload["stale"] is True


def test_dbt_health_missing_run_results(api_client, monkeypatch, tmp_path):
    from core import views as core_views

    run_results_path = tmp_path / "run_results.json"
    monkeypatch.setattr(core_views, "RUN_RESULTS_PATH", run_results_path)

    response = api_client.get("/api/health/dbt/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "missing_run_results"


def test_dbt_health_ok(api_client, monkeypatch, tmp_path):
    from core import views as core_views

    run_results_path = tmp_path / "run_results.json"
    run_results_path.write_text(
        json.dumps(
            {
                "metadata": {"generated_at": timezone.now().isoformat()},
                "results": [
                    {"status": "success", "unique_id": "model.ads.reporting"},
                ],
            }
        )
    )
    monkeypatch.setattr(core_views, "RUN_RESULTS_PATH", run_results_path)

    response = api_client.get("/api/health/dbt/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["failing_models"] == []


def test_dbt_health_flags_stale(api_client, monkeypatch, tmp_path):
    from core import views as core_views

    run_results_path = tmp_path / "run_results.json"
    stale_timestamp = (timezone.now() - timedelta(days=2)).isoformat()
    run_results_path.write_text(
        json.dumps(
            {
                "metadata": {"generated_at": stale_timestamp},
                "results": [
                    {"status": "success", "unique_id": "model.ads.reporting"},
                ],
            }
        )
    )
    monkeypatch.setattr(core_views, "RUN_RESULTS_PATH", run_results_path)

    response = api_client.get("/api/health/dbt/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "stale"
    assert payload["stale"] is True


def test_api_logging_middleware_emits_structured_context(api_client):
    captured_records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - standard handler hook
            captured_records.append(record)

    handler = CaptureHandler()
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    try:
        response = api_client.get("/api/health/")
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    assert captured_records, "Expected a request log entry"
    latest = captured_records[-1]
    assert latest.http["path"] == "/api/health/"
    assert latest.duration_ms >= 0


def test_version_endpoint_reports_api_version(api_client, settings):
    settings.API_VERSION = "1.2.3-test"

    response = api_client.get("/api/version/")

    assert response.status_code == 200
    assert response.json() == {"version": "1.2.3-test"}
