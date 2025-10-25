from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from jsonschema import validate
from rest_framework.test import APIClient

from accounts.models import Tenant
from integrations.models import AirbyteConnection, AirbyteJobTelemetry, TenantAirbyteSyncStatus

SCHEMA_DIR = Path(__file__).parent / "schemas"
FIXTURES_DIR = SCHEMA_DIR / "fixtures"
TELEMETRY_FIXTURE = FIXTURES_DIR / "telemetry.json"
DBT_RUN_RESULTS_FIXTURE = FIXTURES_DIR / "dbt_run_results.json"
TELEMETRY_TENANT_ID = "11111111-2222-3333-4444-555555555555"
AIRBYTE_CONNECTION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

pytestmark = pytest.mark.django_db


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


@pytest.fixture
def telemetry_setup(settings):
    settings.ENABLE_FAKE_ADAPTER = True
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = "ci-token"
    call_command("loaddata", str(TELEMETRY_FIXTURE))

    tenant = Tenant.objects.get(pk=TELEMETRY_TENANT_ID)
    connection = AirbyteConnection.all_objects.get(pk=AIRBYTE_CONNECTION_ID)

    now = timezone.now()
    connection.last_synced_at = now
    connection.last_job_created_at = now
    connection.last_job_status = "succeeded"
    connection.last_job_id = "2001"
    connection.save(
        update_fields=[
            "last_synced_at",
            "last_job_created_at",
            "last_job_status",
            "last_job_id",
            "updated_at",
        ]
    )
    TenantAirbyteSyncStatus.update_for_connection(connection)

    jobs = list(
        AirbyteJobTelemetry.all_objects.filter(connection=connection).order_by("-started_at")
    )
    for index, job in enumerate(jobs):
        job.started_at = now - timedelta(minutes=5 + index * 5)
        job.duration_seconds = 75 + index * 15
        job.records_synced = 150 + index * 25
        job.bytes_synced = 4096 + index * 1024
        job.api_cost = Decimal("3.25") + Decimal(index) * Decimal("0.75")
        job.save(
            update_fields=[
                "started_at",
                "duration_seconds",
                "records_synced",
                "bytes_synced",
                "api_cost",
            ]
        )

    return tenant


@pytest.fixture
def dbt_run_results(settings):
    target_path = Path(settings.BASE_DIR).parent / "dbt" / "target" / "run_results.json"
    template = json.loads(DBT_RUN_RESULTS_FIXTURE.read_text())
    template["metadata"]["generated_at"] = timezone.now().isoformat()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(template, indent=2))
    yield target_path
    try:
        target_path.unlink()
    except FileNotFoundError:
        pass


def test_dashboard_snapshot_schema(telemetry_setup, dbt_run_results):
    tenant = telemetry_setup
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="telemetry-schema@example.com",
        email="telemetry-schema@example.com",
        tenant=tenant,
        password="schema-pass-123",
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/dashboards/aggregate-snapshot/")
    assert response.status_code == 200
    payload = response.json()

    validate(instance=payload, schema=load_schema("dashboard_aggregate_snapshot.schema.json"))
    assert payload["tenant_id"] == TELEMETRY_TENANT_ID
    assert payload["generated_at"]
    metrics = payload["metrics"]
    assert set(metrics.keys()) == {"campaign_metrics", "creative_metrics", "budget_metrics", "parish_metrics"}
    assert metrics["campaign_metrics"]["summary"]["currency"]
    assert metrics["parish_metrics"], "Expected parish aggregates to be populated"


def test_airbyte_health_schema(telemetry_setup, dbt_run_results):
    client = APIClient()
    response = client.get("/api/health/airbyte/")
    assert response.status_code == 200
    payload = response.json()

    validate(instance=payload, schema=load_schema("airbyte_health.schema.json"))
    assert payload["last_sync"]["tenant_id"] == TELEMETRY_TENANT_ID
    assert payload["job_summary"]["job_count"] >= 1


def test_dbt_health_schema(telemetry_setup, dbt_run_results):
    client = APIClient()
    response = client.get("/api/health/dbt/")
    assert response.status_code == 200
    payload = response.json()

    validate(instance=payload, schema=load_schema("dbt_health.schema.json"))
    assert payload["status"] == "ok"
    assert payload["generated_at"], "Generated timestamp should be populated"
