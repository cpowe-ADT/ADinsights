from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import path
from django.utils import timezone

from core.metrics import (
    observe_dbt_run,
    observe_task,
    observe_task_queue_start,
    observe_task_retry,
    reset_metrics,
)
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


def _histogram_sum_for_queue(*, body: str, metric_name: str, queue_name: str) -> float:
    pattern = re.compile(
        rf'{metric_name}_sum\{{[^}}]*queue_name="{queue_name}"[^}}]*\}}\s+([0-9.]+)'
    )
    match = pattern.search(body)
    assert match is not None
    return float(match.group(1))


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


@pytest.mark.django_db
def test_airbyte_health_cron_sync_not_stale_outside_window(api_client, tenant, settings, monkeypatch):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    last_sync_time = timezone.make_aware(datetime(2026, 3, 1, 22, 38, 24))
    now = timezone.make_aware(datetime(2026, 3, 2, 1, 0, 0))
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        last_synced_at=last_sync_time,
        last_job_status="succeeded",
        last_job_id="sync-1",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)
    monkeypatch.setattr("core.views.timezone.now", lambda: now)

    response = api_client.get("/api/health/airbyte/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["stale"] is False


@pytest.mark.django_db
def test_airbyte_health_flags_running_job_stale_outside_window(
    api_client, tenant, settings, monkeypatch
):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "token"
    last_sync_time = timezone.make_aware(datetime(2026, 3, 1, 22, 38, 24))
    now = timezone.make_aware(datetime(2026, 3, 2, 1, 30, 0))
    connection = AirbyteConnection.objects.create(
        tenant=tenant,
        name="Meta",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        last_synced_at=last_sync_time,
        last_job_status="running",
        last_job_id="sync-running-1",
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)
    monkeypatch.setattr("core.views.timezone.now", lambda: now)

    response = api_client.get("/api/health/airbyte/")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "running_stale"
    assert payload["stale"] is False
    assert payload["running_age_seconds"] >= 9000


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


def test_dbt_health_uses_container_fallback_path(api_client, monkeypatch, tmp_path):
    from core import views as core_views

    default_path = tmp_path / "missing" / "run_results.json"
    fallback_path = tmp_path / "container" / "run_results.json"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text(
        json.dumps(
            {
                "metadata": {"generated_at": timezone.now().isoformat()},
                "results": [
                    {"status": "success", "unique_id": "model.ads.reporting"},
                ],
            }
        )
    )

    monkeypatch.setattr(core_views, "DEFAULT_RUN_RESULTS_PATH", default_path)
    monkeypatch.setattr(core_views, "RUN_RESULTS_PATH", default_path)
    monkeypatch.setattr(core_views, "CONTAINER_RUN_RESULTS_PATH", fallback_path)

    response = api_client.get("/api/health/dbt/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["run_results_path"] == str(fallback_path)


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
    observe_task_retry(task_name="core.tasks.sync_meta_metrics", reason="airbyte_client_error")
    observe_task_queue_start(
        task_name="integrations.tasks.sync_meta_accounts",
        queue_name="sync",
        queue_wait_seconds=0.75,
    )
    observe_task_queue_start(
        task_name="analytics.sync_metrics_snapshots",
        queue_name="snapshot",
        queue_wait_seconds=1.25,
    )
    observe_task_queue_start(
        task_name="analytics.ai_daily_summary",
        queue_name="summary",
        queue_wait_seconds=2.5,
    )
    observe_dbt_run("success", 1.5)

    response = api_client.get("/metrics/app/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "celery_task_executions_total" in body
    assert "celery_task_retries_total" in body
    assert "celery_task_queue_starts_total" in body
    assert "celery_task_queue_wait_seconds" in body
    assert 'queue_name="sync"' in body
    assert 'queue_name="snapshot"' in body
    assert 'queue_name="summary"' in body
    queue_wait_sync = _histogram_sum_for_queue(
        body=body,
        metric_name="celery_task_queue_wait_seconds",
        queue_name="sync",
    )
    queue_wait_snapshot = _histogram_sum_for_queue(
        body=body,
        metric_name="celery_task_queue_wait_seconds",
        queue_name="snapshot",
    )
    queue_wait_summary = _histogram_sum_for_queue(
        body=body,
        metric_name="celery_task_queue_wait_seconds",
        queue_name="summary",
    )
    assert queue_wait_sync == pytest.approx(0.75)
    assert queue_wait_snapshot == pytest.approx(1.25)
    assert queue_wait_summary == pytest.approx(2.5)
    assert queue_wait_summary > queue_wait_snapshot > queue_wait_sync
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
