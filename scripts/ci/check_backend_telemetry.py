from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from jsonschema import Draft7Validator
from rest_framework.test import APIClient

# Ensure the backend package is importable before configuring Django.
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from accounts.models import Tenant

SCHEMA_FILES = {
    "aggregate": "dashboard_aggregate_snapshot.schema.json",
    "airbyte": "airbyte_health.schema.json",
    "dbt": "dbt_health.schema.json",
}

FIXTURE_FILE = BACKEND_ROOT / "tests" / "schemas" / "fixtures" / "telemetry.json"
DBT_RUN_RESULTS_TEMPLATE = (
    BACKEND_ROOT / "tests" / "schemas" / "fixtures" / "dbt_run_results.json"
)
SCHEMA_DIRECTORY = BACKEND_ROOT / "tests" / "schemas"
TELEMETRY_TENANT_ID = "11111111-2222-3333-4444-555555555555"
AIRBYTE_CONNECTION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TASK_ID = "backend.telemetry.schema_guard"


@dataclass
class EndpointResult:
    name: str
    status_code: int
    payload: dict[str, Any]

    def ensure_success(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"{self.name} endpoint returned {self.status_code}")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate backend telemetry responses against schema baselines."
    )
    parser.add_argument(
        "--schema-dir",
        default=str(SCHEMA_DIRECTORY),
        help="Directory containing canonical JSON schemas.",
    )
    parser.add_argument(
        "--fixture",
        default=str(FIXTURE_FILE),
        help="Django fixture file used to seed telemetry state.",
    )
    parser.add_argument(
        "--dbt-template",
        default=str(DBT_RUN_RESULTS_TEMPLATE),
        help="Template run_results.json used to prime dbt health checks.",
    )
    parser.add_argument(
        "--markdown-output",
        default="backend-telemetry-summary.md",
        help="Filename for the human-readable summary artifact.",
    )
    parser.add_argument(
        "--json-output",
        default="backend-telemetry-summary.json",
        help="Filename for the structured telemetry summary.",
    )
    return parser.parse_args(list(argv))


def configure_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    os.environ.setdefault("DJANGO_SECRET_KEY", "telemetry-ci-secret")
    os.environ.setdefault("CELERY_BROKER_URL", "memory://")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
    os.environ.setdefault("SECRETS_PROVIDER", "env")
    os.environ.setdefault("KMS_PROVIDER", "local")
    os.environ.setdefault("KMS_KEY_ID", "ci-telemetry")
    os.environ.setdefault("AWS_REGION", "us-east-1")
    os.environ.setdefault("AIRBYTE_API_URL", "http://airbyte.local")
    os.environ.setdefault("AIRBYTE_API_TOKEN", "ci-token")
    os.environ.setdefault("API_VERSION", "telemetry-ci")
    django.setup()


def apply_fixtures(fixture_path: Path, dbt_template: Path) -> "Tenant":
    from accounts.models import Tenant
    from integrations.models import (
        AirbyteConnection,
        AirbyteJobTelemetry,
        TenantAirbyteSyncStatus,
    )

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture file not found: {fixture_path}")
    call_command("migrate", run_syncdb=True, interactive=False, verbosity=0)
    call_command("loaddata", str(fixture_path), verbosity=0)

    settings.ENABLE_FAKE_ADAPTER = True

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

    run_results_template = json.loads(dbt_template.read_text())
    run_results_template["metadata"]["generated_at"] = timezone.now().isoformat()
    run_results_path = Path(settings.BASE_DIR).parent / "dbt" / "target" / "run_results.json"
    run_results_path.parent.mkdir(parents=True, exist_ok=True)
    run_results_path.write_text(json.dumps(run_results_template, indent=2))

    return tenant


def create_authenticated_user(tenant: "Tenant"):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="telemetry-ci@example.com",
        email="telemetry-ci@example.com",
        tenant=tenant,
        password="telemetry-pass-123",
    )


def fetch_endpoints(user) -> dict[str, EndpointResult]:
    authed_client = APIClient()
    authed_client.force_authenticate(user=user)
    aggregate = authed_client.get("/api/dashboards/aggregate-snapshot/")

    anon_client = APIClient()
    airbyte = anon_client.get("/api/health/airbyte/")
    dbt = anon_client.get("/api/health/dbt/")

    results = {
        "aggregate": EndpointResult(
            name="aggregate snapshot",
            status_code=aggregate.status_code,
            payload=aggregate.json(),
        ),
        "airbyte": EndpointResult(
            name="airbyte health",
            status_code=airbyte.status_code,
            payload=airbyte.json(),
        ),
        "dbt": EndpointResult(
            name="dbt health",
            status_code=dbt.status_code,
            payload=dbt.json(),
        ),
    }

    for result in results.values():
        result.ensure_success()

    return results


def load_schemas(schema_dir: Path) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for key, filename in SCHEMA_FILES.items():
        path = schema_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")
        schemas[key] = json.loads(path.read_text())
    return schemas


def validate_payloads(
    payloads: dict[str, EndpointResult], schemas: dict[str, dict[str, Any]]
) -> None:
    for key, result in payloads.items():
        schema = schemas.get(key)
        if not schema:
            raise KeyError(f"Schema not provided for key '{key}'")
        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(result.payload), key=lambda e: e.path)
        if errors:
            messages = [
                f"{key} validation error at {'/'.join(str(p) for p in error.path)}: {error.message}"
                for error in errors
            ]
            raise RuntimeError("; ".join(messages))


def build_markdown(
    tenant: "Tenant",
    payloads: dict[str, EndpointResult],
    markdown_path: Path,
) -> None:
    aggregate = payloads["aggregate"].payload
    airbyte = payloads["airbyte"].payload
    dbt = payloads["dbt"].payload

    lines = ["# Backend Telemetry Schema Guard", ""]
    generated = timezone.now().isoformat()
    lines.append(f"- Generated at: {generated}")
    lines.append(f"- Tenant: {tenant.name} ({tenant.id})")
    lines.append("")

    lines.append("## Snapshot Highlights")
    lines.append(
        f"- Aggregate snapshot sections: campaign={len(aggregate['campaign'].get('rows', []))} rows, "
        f"creative={len(aggregate['creative'])} creatives, budget={len(aggregate['budget'])} budgets, "
        f"parish={len(aggregate['parish'])} parishes"
    )
    lines.append(
        "- Campaign currency: " + aggregate["campaign"]["summary"].get("currency", "unknown")
    )
    lines.append(
        f"- Airbyte status: {airbyte['status']} (job {airbyte['last_sync']['last_job_id']})"
    )
    lines.append(
        f"- dbt status: {dbt['status']} (generated_at {dbt['generated_at']})"
    )
    lines.append("")

    lines.append("### Recent Airbyte Jobs")
    lines.append("| Job ID | Status | Started At | Duration (s) | Records | Bytes | API Cost |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for job in airbyte["recent_jobs"]:
        lines.append(
            "| {job_id} | {status} | {started} | {duration} | {records} | {bytes_synced} | {api_cost} |".format(
                job_id=job.get("job_id", ""),
                status=job.get("status", ""),
                started=job.get("started_at", ""),
                duration=job.get("duration_seconds", ""),
                records=job.get("records_synced", ""),
                bytes_synced=job.get("bytes_synced", ""),
                api_cost=job.get("api_cost", ""),
            )
        )
    lines.append("")

    lines.append("### Tenant Isolation Notes")
    lines.append(
        "All telemetry payloads are scoped to tenant {tenant_id} and omit cross-tenant identifiers.".format(
            tenant_id=tenant.id
        )
    )

    markdown_path.write_text("\n".join(lines))


def build_json_summary(
    tenant: "Tenant",
    payloads: dict[str, EndpointResult],
    schema_dir: Path,
    json_path: Path,
) -> None:
    aggregate = payloads["aggregate"].payload
    airbyte = payloads["airbyte"].payload
    dbt = payloads["dbt"].payload

    correlation_id = str(uuid.uuid4())
    timestamp = timezone.now().isoformat()

    summary = {
        "tenant_id": str(tenant.id),
        "task_id": TASK_ID,
        "correlation_id": correlation_id,
        "timestamp": timestamp,
        "aggregate_snapshot": {
            "campaign_rows": len(aggregate["campaign"].get("rows", [])),
            "creative_count": len(aggregate["creative"]),
            "budget_count": len(aggregate["budget"]),
            "parish_count": len(aggregate["parish"]),
            "currency": aggregate["campaign"]["summary"].get("currency"),
        },
        "airbyte_health": {
            "status": airbyte["status"],
            "last_job_id": airbyte["last_sync"]["last_job_id"],
            "last_synced_at": airbyte["last_sync"]["last_synced_at"],
            "job_count": airbyte["job_summary"]["job_count"],
            "average_records_synced": airbyte["job_summary"].get("average_records_synced"),
        },
        "dbt_health": {
            "status": dbt["status"],
            "generated_at": dbt["generated_at"],
            "failing_models": dbt.get("failing_models", []),
        },
        "schema_sources": {
            key: str((schema_dir / filename).resolve())
            for key, filename in SCHEMA_FILES.items()
        },
    }

    json_path.write_text(json.dumps(summary, indent=2))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    configure_django()

    tenant = apply_fixtures(Path(args.fixture), Path(args.dbt_template))
    user = create_authenticated_user(tenant)
    payloads = fetch_endpoints(user)

    schemas = load_schemas(Path(args.schema_dir))
    validate_payloads(payloads, schemas)

    build_markdown(tenant, payloads, Path(args.markdown_output))
    build_json_summary(tenant, payloads, Path(args.schema_dir), Path(args.json_output))

    print("Telemetry schema guard completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    raise SystemExit(main(sys.argv[1:]))
