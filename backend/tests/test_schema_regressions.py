from __future__ import annotations

from collections import Counter
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
import yaml

from accounts.models import Tenant
from analytics.models import TenantMetricsSnapshot
from analytics.uploads import build_combined_payload
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


def test_combined_metrics_schema(telemetry_setup, dbt_run_results):
    tenant = telemetry_setup
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="metrics-schema@example.com",
        email="metrics-schema@example.com",
        tenant=tenant,
        password="schema-pass-123",
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/metrics/combined/")
    assert response.status_code == 200
    payload = response.json()

    validate(instance=payload, schema=load_schema("combined_metrics.schema.json"))
    assert payload["campaign"]["summary"]["currency"]


def test_upload_metrics_status_schema(telemetry_setup, dbt_run_results):
    tenant = telemetry_setup
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="upload-schema@example.com",
        email="upload-schema@example.com",
        tenant=tenant,
        password="schema-pass-123",
    )

    payload = build_combined_payload(
        campaign_rows=[
            {
                "date": "2024-10-01",
                "campaign_id": "cmp-1",
                "campaign_name": "Launch",
                "platform": "Meta",
                "parish": "Kingston",
                "spend": 120.0,
                "impressions": 12000.0,
                "clicks": 420.0,
                "conversions": 33.0,
            }
        ],
        parish_rows=[],
        budget_rows=[],
    )
    TenantMetricsSnapshot.objects.update_or_create(
        tenant=tenant,
        source="upload",
        defaults={"payload": payload, "generated_at": timezone.now()},
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/uploads/metrics/")
    assert response.status_code == 200
    status_payload = response.json()

    validate(instance=status_payload, schema=load_schema("upload_metrics_status.schema.json"))
    assert status_payload["has_upload"] is True


def test_dbt_health_schema(telemetry_setup, dbt_run_results):
    client = APIClient()
    response = client.get("/api/health/dbt/")
    assert response.status_code == 200
    payload = response.json()

    validate(instance=payload, schema=load_schema("dbt_health.schema.json"))
    assert payload["status"] == "ok"
    assert payload["generated_at"], "Generated timestamp should be populated"


@pytest.mark.django_db
def test_openapi_schema_includes_airbyte_connection_summary():
    client = APIClient()
    response = client.get("/api/schema/")
    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload.get("paths", {})
    assert "/api/airbyte/connections/summary/" in paths


@pytest.mark.django_db
def test_openapi_schema_includes_airbyte_telemetry():
    client = APIClient()
    response = client.get("/api/schema/")
    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload.get("paths", {})
    assert "/api/airbyte/telemetry/" in paths


@pytest.mark.django_db
def test_openapi_schema_includes_metrics_upload():
    client = APIClient()
    response = client.get("/api/schema/")
    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload.get("paths", {})
    assert "/api/uploads/metrics/" in paths


@pytest.mark.django_db
def test_openapi_schema_includes_social_connection_status():
    client = APIClient()
    response = client.get("/api/schema/")
    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload.get("paths", {})
    assert "/api/integrations/social/status/" in paths


@pytest.mark.django_db
def test_openapi_schema_includes_google_ads_paths():
    client = APIClient()
    response = client.get("/api/schema/")
    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload.get("paths", {})
    assert "/api/integrations/google_ads/setup/" in paths
    assert "/api/integrations/google_ads/oauth/start/" in paths
    assert "/api/integrations/google_ads/oauth/exchange/" in paths
    assert "/api/integrations/google_ads/status/" in paths
    assert "/api/integrations/google_ads/reference/summary/" in paths
    assert "/api/integrations/google_ads/provision/" in paths
    assert "/api/integrations/google_ads/sync/" in paths
    assert "/api/integrations/google_ads/disconnect/" in paths


@pytest.mark.django_db
def test_openapi_schema_includes_meta_page_insights_paths():
    client = APIClient()
    response = client.get("/api/schema/")
    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload.get("paths", {})
    assert "/api/integrations/meta/oauth/callback/" in paths
    assert "/api/integrations/meta/pages/" in paths
    assert "/api/integrations/meta/pages/{page_id}/select/" in paths
    assert "/api/metrics/meta/pages/{page_id}/overview/" in paths
    assert "/api/metrics/meta/pages/{page_id}/timeseries/" in paths
    assert "/api/metrics/meta/pages/{page_id}/posts/" in paths
    assert "/api/metrics/meta/posts/{post_id}/timeseries/" in paths
    assert "/api/metrics/meta/pages/{page_id}/refresh/" in paths


@pytest.mark.django_db
def test_openapi_schema_operation_ids_are_unique():
    client = APIClient()
    response = client.get("/api/schema/")
    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload.get("paths", {})

    operation_ids: list[str] = []
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            if isinstance(operation, dict):
                operation_id = operation.get("operationId")
                if isinstance(operation_id, str) and operation_id:
                    operation_ids.append(operation_id)

    duplicate_ids = sorted([operation_id for operation_id, count in Counter(operation_ids).items() if count > 1])
    assert not duplicate_ids, f"Duplicate operationIds found: {duplicate_ids}"
