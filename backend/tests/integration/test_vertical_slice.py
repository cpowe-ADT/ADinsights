from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command

from accounts.models import User


DEFAULT_TENANT_ID = "7f9b2f19-edb9-4888-852e-81d59af0e4a0"
DEFAULT_ADMIN_USERNAME = "devadmin@local.test"


def run_dbt(project_dir: Path) -> None:
    if shutil.which("dbt") is None:
        pytest.skip("dbt CLI is required for dbt-backed integration tests.")
    profiles_source = project_dir / "profiles-ci.yml"
    if not profiles_source.exists():
        raise FileNotFoundError(f"Missing dbt CI profile: {profiles_source}")

    with tempfile.TemporaryDirectory() as temp_profiles:
        profiles_dir = Path(temp_profiles)
        shutil.copyfile(profiles_source, profiles_dir / "profiles.yml")

        env = os.environ.copy()
        env.update(
            {
                "DBT_PROJECT_DIR": str(project_dir),
                "DBT_PROFILES_DIR": str(profiles_dir),
                "DBT_PROFILE": "adinsights_duckdb",
                "DBT_DUCKDB_PATH": str(project_dir / "target" / "warehouse_ci.duckdb"),
                "DBT_SCHEMA": "analytics",
                "CI_USE_SEEDS": "true",
            }
        )

        base_args = [
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(profiles_dir),
            "--profile",
            "adinsights_duckdb",
        ]

        subprocess.run(
            [
                "dbt",
                "seed",
                "--full-refresh",
                "--exclude",
                "path:seeds/raw/*",
                "path:seeds/raw_meta/*",
                "path:seeds/raw_google_ads/*",
                *base_args,
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            ["dbt", "run", "--select", "staging_ci", *base_args], check=True, env=env
        )
        subprocess.run(
            ["dbt", "test", "--select", "staging_ci", *base_args], check=True, env=env
        )


@pytest.mark.django_db
@pytest.mark.integration
def test_vertical_slice_combined_metrics(api_client, settings, monkeypatch):
    monkeypatch.setenv("DJANGO_DEFAULT_TENANT_ID", DEFAULT_TENANT_ID)
    monkeypatch.setenv("DJANGO_DEFAULT_TENANT_NAME", "Default Tenant")
    monkeypatch.setenv("DJANGO_DEFAULT_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
    monkeypatch.setenv("DJANGO_DEFAULT_ADMIN_EMAIL", DEFAULT_ADMIN_USERNAME)
    monkeypatch.setenv("DJANGO_DEFAULT_ADMIN_PASSWORD", "devadmin1")
    monkeypatch.setenv("ALLOW_DEFAULT_ADMIN", "1")

    settings.ENABLE_WAREHOUSE_ADAPTER = True
    settings.ENABLE_FAKE_ADAPTER = False
    settings.ENABLE_DEMO_ADAPTER = False

    dbt_project_dir = Path(settings.BASE_DIR).parent / "dbt"
    run_dbt(dbt_project_dir)

    fixture_path = Path(settings.BASE_DIR) / "fixtures" / "dev_seed.json"
    call_command("seed_dev_data", fixture=str(fixture_path))

    user = User.objects.get(username=DEFAULT_ADMIN_USERNAME)
    api_client.force_authenticate(user=user)

    dbt_health = api_client.get("/api/health/dbt/")
    assert dbt_health.status_code == 200
    assert dbt_health.json()["status"] == "ok"

    response = api_client.get("/api/metrics/combined/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign"]["summary"]["currency"] == "JMD"
    assert payload["campaign"]["rows"]
    assert any(row["id"] == "boj_fx_awareness" for row in payload["campaign"]["rows"])
    assert payload["parish"][0]["currency"] == "JMD"
    assert "snapshot_generated_at" in payload

    campaigns_response = api_client.get("/api/analytics/campaigns/")
    assert campaigns_response.status_code == 200
    body = campaigns_response.json()
    campaigns = body if isinstance(body, list) else body.get("results", [])
    assert len(campaigns) == 3
