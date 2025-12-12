from __future__ import annotations

import json
import logging
import uuid
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import path
from django.utils import timezone

from core.metrics import observe_task, observe_dbt_run, reset_metrics
from integrations.models import (
    AirbyteConnection,
    AirbyteJobTelemetry,
    PlatformCredential,
    TenantAirbyteSyncStatus,
)


def _failing_view(request):  # noqa: ANN001 - test helper signature
    raise RuntimeError("boom")


urlpatterns = [
    path("boom/", _failing_view),
]

handler500 = "core.views.server_error"


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
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=now,
        last_job_status="succeeded",
        last_job_id="99",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)
    AirbyteJobTelemetry.all_objects.create(
        tenant=tenant,
        connection=connection,
        job_id="99",
        status="succeeded",
        started_at=now - timedelta(minutes=5),
        duration_seconds=70,
        records_synced=150,
        bytes_synced=4096,
        api_cost="3.25",
    )

    response = api_client.get("/api/health/airbyte/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["last_sync"]["last_job_status"] == "succeeded"
    assert payload["recent_jobs"][0]["job_id"] == "99"
    assert payload["recent_jobs"][0]["records_synced"] == 150
    assert payload["job_summary"]["average_records_synced"] == 150.0
    assert payload["job_summary"]["latest_job"]["duration_seconds"] == 70


@pytest.mark.django_db
def test_airbyte_health_reports_failed_sync(api_client, tenant, settings):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=now,
        last_job_status="failed",
        last_job_id="100",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)
    AirbyteJobTelemetry.all_objects.create(
        tenant=tenant,
        connection=connection,
        job_id="100",
        status="failed",
        started_at=now - timedelta(minutes=10),
        duration_seconds=120,
        records_synced=0,
        bytes_synced=0,
    )

    response = api_client.get("/api/health/airbyte/")
    assert response.status_code == 502
    payload = response.json()
    assert payload["status"] == "sync_failed"
    assert "failed" in payload["detail"].lower()


@pytest.mark.django_db
def test_airbyte_health_reports_pending_sync(api_client, tenant, settings):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    now = timezone.now()
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=now,
        last_job_status="running",
        last_job_id="101",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)
    AirbyteJobTelemetry.all_objects.create(
        tenant=tenant,
        connection=connection,
        job_id="101",
        status="running",
        started_at=now - timedelta(minutes=2),
    )

    response = api_client.get("/api/health/airbyte/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert "running" in payload["detail"].lower()


@pytest.mark.django_db
def test_airbyte_health_flags_stale_sync(api_client, tenant, settings):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    stale_time = timezone.now() - timedelta(hours=2)
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Google",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.GOOGLE,
        schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
        interval_minutes=30,
        last_synced_at=stale_time,
        last_job_status="succeeded",
        last_job_id="1",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)
    AirbyteJobTelemetry.all_objects.create(
        tenant=tenant,
        connection=connection,
        job_id="1",
        status="succeeded",
        started_at=stale_time - timedelta(minutes=5),
        duration_seconds=90,
        records_synced=200,
        bytes_synced=8192,
    )

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
    assert payload["failing_models_detail"] == []


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
    assert payload["failing_models_detail"] == []


def test_dbt_health_reports_failing_models(api_client, monkeypatch, tmp_path):
    from core import views as core_views

    run_results_path = tmp_path / "run_results.json"
    run_results_path.write_text(
        json.dumps(
            {
                "metadata": {"generated_at": timezone.now().isoformat()},
                "results": [
                    {
                        "unique_id": "model.analytics.bad_model",
                        "status": "error",
                        "message": "Compilation error",
                        "adapter_response": {"error": "invalid syntax"},
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(core_views, "RUN_RESULTS_PATH", run_results_path)

    response = api_client.get("/api/health/dbt/")
    assert response.status_code == 502
    payload = response.json()
    assert payload["status"] == "failing"
    assert payload["failing_models"] == ["model.analytics.bad_model"]
    assert payload["failing_models_detail"] == [
        {
            "unique_id": "model.analytics.bad_model",
            "status": "error",
            "message": "Compilation error",
            "adapter_response": {"error": "invalid syntax"},
        }
    ]


def test_prometheus_metrics_endpoint(api_client):
    reset_metrics()
    observe_task("core.tasks.rotate_deks", "SUCCESS", 0.42)
    observe_dbt_run("success", 1.5)

    response = api_client.get("/metrics/app/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "celery_task_executions_total" in body
    assert "celery_task_duration_seconds" in body
    assert "dbt_run_duration_seconds" in body


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


def test_health_version_endpoint(api_client, settings):
    settings.APP_VERSION = "1.2.3"

    response = api_client.get("/api/health/version/")

    assert response.status_code == 200
    assert response.json() == {"version": "1.2.3"}


def test_not_found_returns_json(api_client, settings):
    settings.DEBUG = False

    response = api_client.get("/api/does-not-exist/")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["path"] == "/api/does-not-exist/"


@override_settings(ROOT_URLCONF="backend.tests.test_health_endpoints", DEBUG=False)
def test_server_error_returns_json():
    client = Client(raise_request_exception=False)
    response = client.get("/boom/")

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "server_error"
    assert "unexpected error" in payload["error"]["message"].lower()
    assert payload["error"]["path"] == "/boom/"
