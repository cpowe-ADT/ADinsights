#!/usr/bin/env python3
"""Check a local Airbyte destination points at a reachable ADinsights Postgres target."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Mapping


DEFAULT_BASE_URL = "http://localhost:18001/api/v1"
DEFAULT_EXPECTED_HOST = "host.docker.internal"
DEFAULT_EXPECTED_PORT = 5432


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local Airbyte Postgres destination config.")
    parser.add_argument("--base-url", default=os.environ.get("AIRBYTE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--destination-id", default=os.environ.get("AIRBYTE_DESTINATION_ID", ""))
    parser.add_argument("--connection-id", default=os.environ.get("AIRBYTE_CONNECTION_ID", ""))
    parser.add_argument("--expected-host", default=os.environ.get("ADI_AIRBYTE_EXPECTED_HOST", DEFAULT_EXPECTED_HOST))
    parser.add_argument(
        "--expected-port",
        type=int,
        default=int(os.environ.get("ADI_AIRBYTE_EXPECTED_PORT", DEFAULT_EXPECTED_PORT)),
    )
    parser.add_argument("--run-airbyte-check", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    errors: list[str] = []
    warnings: list[str] = []
    destination_id = args.destination_id.strip()
    connection_payload: Mapping[str, Any] | None = None

    if not destination_id and args.connection_id.strip():
        connection_payload = _post_json(
            base_url=args.base_url,
            path="connections/get",
            payload={"connectionId": args.connection_id.strip()},
            errors=errors,
            label="Airbyte connection",
        )
        if connection_payload:
            destination_id = str(connection_payload.get("destinationId") or "")

    if not destination_id:
        errors.append("Provide --destination-id or --connection-id.")
        result = _result(
            valid=False,
            destination_id="",
            expected_host=args.expected_host,
            expected_port=args.expected_port,
            config={},
            errors=errors,
            warnings=warnings,
            airbyte_check=None,
        )
        _print_result(result, args.format)
        return 1

    destination_payload = _post_json(
        base_url=args.base_url,
        path="destinations/get",
        payload={"destinationId": destination_id},
        errors=errors,
        label="Airbyte destination",
    )
    config = (
        destination_payload.get("connectionConfiguration")
        if isinstance(destination_payload, Mapping)
        and isinstance(destination_payload.get("connectionConfiguration"), Mapping)
        else {}
    )
    validation_errors = validate_destination_config(
        config=config,
        expected_host=args.expected_host,
        expected_port=args.expected_port,
    )
    errors.extend(validation_errors)

    airbyte_check = None
    if args.run_airbyte_check and not validation_errors:
        airbyte_check = _post_json(
            base_url=args.base_url,
            path="destinations/check_connection",
            payload={"destinationId": destination_id},
            errors=errors,
            label="Airbyte destination check",
            timeout=90,
        )
        if airbyte_check and airbyte_check.get("status") != "succeeded":
            errors.append("Airbyte destination check did not return status=succeeded.")

    result = _result(
        valid=not errors,
        destination_id=destination_id,
        expected_host=args.expected_host,
        expected_port=args.expected_port,
        config=safe_destination_config(config),
        errors=errors,
        warnings=warnings,
        airbyte_check=safe_airbyte_check(airbyte_check),
    )
    _print_result(result, args.format)
    return 1 if errors else 0


def validate_destination_config(
    *,
    config: Mapping[str, Any],
    expected_host: str,
    expected_port: int,
) -> list[str]:
    errors: list[str] = []
    host = str(config.get("host") or "")
    port = config.get("port")
    if host != expected_host:
        errors.append(f"Airbyte destination host is {host or '<missing>'}; expected {expected_host}.")
    try:
        normalized_port = int(port)
    except (TypeError, ValueError):
        normalized_port = -1
    if normalized_port != expected_port:
        errors.append(f"Airbyte destination port is {port or '<missing>'}; expected {expected_port}.")
    if not str(config.get("database") or ""):
        errors.append("Airbyte destination database is missing.")
    if not str(config.get("schema") or ""):
        errors.append("Airbyte destination schema is missing.")
    if not str(config.get("username") or ""):
        errors.append("Airbyte destination username is missing.")
    return errors


def safe_destination_config(config: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {"host", "port", "database", "schema", "username", "ssl"}
    return {key: config.get(key) for key in sorted(allowed) if key in config}


def safe_airbyte_check(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    job_info = payload.get("jobInfo") if isinstance(payload.get("jobInfo"), Mapping) else {}
    return {
        "status": payload.get("status"),
        "job_id": job_info.get("id"),
        "succeeded": job_info.get("succeeded"),
        "connector_configuration_updated": job_info.get("connectorConfigurationUpdated"),
    }


def _post_json(
    *,
    base_url: str,
    path: str,
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
    timeout: int = 20,
) -> Mapping[str, Any] | None:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        errors.append(f"{label} request failed with HTTP {exc.code}.")
        return None
    except OSError as exc:
        errors.append(f"{label} request failed: {exc.__class__.__name__}.")
        return None
    except json.JSONDecodeError:
        errors.append(f"{label} returned invalid JSON.")
        return None
    if not isinstance(data, Mapping):
        errors.append(f"{label} response must be a JSON object.")
        return None
    return data


def _result(
    *,
    valid: bool,
    destination_id: str,
    expected_host: str,
    expected_port: int,
    config: Mapping[str, Any],
    errors: list[str],
    warnings: list[str],
    airbyte_check: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": "local_airbyte_destination_check.v1",
        "valid": valid,
        "destination_id": destination_id,
        "expected": {"host": expected_host, "port": expected_port},
        "config": dict(config),
        "airbyte_check": dict(airbyte_check) if isinstance(airbyte_check, Mapping) else None,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def _print_result(result: Mapping[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(f"Local Airbyte destination valid: {str(result['valid']).lower()}")
    print(f"Destination ID: {result.get('destination_id') or '<missing>'}")
    config = result.get("config") if isinstance(result.get("config"), Mapping) else {}
    expected = result.get("expected") if isinstance(result.get("expected"), Mapping) else {}
    print(f"Configured target: {config.get('host')}:{config.get('port')}")
    print(f"Expected target: {expected.get('host')}:{expected.get('port')}")
    airbyte_check = result.get("airbyte_check")
    if isinstance(airbyte_check, Mapping) and airbyte_check:
        print(f"Airbyte check status: {airbyte_check.get('status')}")
    for error in result.get("errors", []):
        print(f"- ERROR: {error}")
    for warning in result.get("warnings", []):
        print(f"- WARNING: {warning}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
