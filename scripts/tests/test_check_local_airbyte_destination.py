from __future__ import annotations

import scripts.check_local_airbyte_destination as cli


def test_validate_destination_config_accepts_expected_postgres_target():
    errors = cli.validate_destination_config(
        config={
            "host": "host.docker.internal",
            "port": 5432,
            "database": "adinsights",
            "schema": "raw",
            "username": "adinsights_user",
            "password": "secret",
        },
        expected_host="host.docker.internal",
        expected_port=5432,
    )

    assert errors == []


def test_validate_destination_config_rejects_wrong_port():
    errors = cli.validate_destination_config(
        config={
            "host": "host.docker.internal",
            "port": 5435,
            "database": "adinsights",
            "schema": "raw",
            "username": "adinsights_user",
        },
        expected_host="host.docker.internal",
        expected_port=5432,
    )

    assert errors == ["Airbyte destination port is 5435; expected 5432."]


def test_safe_destination_config_redacts_secret_fields():
    safe = cli.safe_destination_config(
        {
            "host": "host.docker.internal",
            "port": 5432,
            "database": "adinsights",
            "schema": "raw",
            "username": "adinsights_user",
            "password": "secret",
            "ssl_key": "secret-key",
            "ssl": False,
        }
    )

    assert safe == {
        "database": "adinsights",
        "host": "host.docker.internal",
        "port": 5432,
        "schema": "raw",
        "ssl": False,
        "username": "adinsights_user",
    }
    assert "password" not in safe
    assert "ssl_key" not in safe


def test_safe_airbyte_check_redacts_logs_and_config():
    safe = cli.safe_airbyte_check(
        {
            "status": "succeeded",
            "jobInfo": {
                "id": "job-1",
                "succeeded": True,
                "connectorConfigurationUpdated": False,
                "logs": {"logLines": ["contains internals"]},
            },
        }
    )

    assert safe == {
        "status": "succeeded",
        "job_id": "job-1",
        "succeeded": True,
        "connector_configuration_updated": False,
    }
