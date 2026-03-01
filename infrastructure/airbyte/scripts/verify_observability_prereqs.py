#!/usr/bin/env python3
"""Validate observability closeout documentation prerequisites."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _check_required_files(errors: list[str]) -> None:
    required = (
        "docs/runbooks/external-actions-aws.md",
        "docs/runbooks/observability-alert-simulations.md",
        "docs/runbooks/release-checklist.md",
        "docs/runbooks/operations.md",
        "docs/runbooks/deployment.md",
        "docs/project/phase1-execution-backlog.md",
        "backend/core/tests/test_observability.py",
    )
    for rel_path in required:
        if not (ROOT / rel_path).exists():
            errors.append(f"Missing required file: {rel_path}.")


def _check_health_endpoints(errors: list[str]) -> None:
    required_endpoints = (
        "/api/health/",
        "/api/health/airbyte/",
        "/api/health/dbt/",
        "/api/timezone/",
    )
    release = _read_text("docs/runbooks/release-checklist.md")
    operations = _read_text("docs/runbooks/operations.md")

    for endpoint in required_endpoints:
        if endpoint not in release and endpoint not in operations:
            errors.append(
                f"Health endpoint '{endpoint}' is not documented in release/operations runbooks."
            )


def _check_structured_log_fields(errors: list[str]) -> None:
    required_fields = ("tenant_id", "task_id", "correlation_id")
    operations = _read_text("docs/runbooks/operations.md")
    observability_test = _read_text("backend/core/tests/test_observability.py")

    for field in required_fields:
        if field not in operations:
            errors.append(f"docs/runbooks/operations.md: missing structured log field '{field}'.")
        if field not in observability_test:
            errors.append(
                f"backend/core/tests/test_observability.py: missing structured log field '{field}'."
            )


def _check_required_links(errors: list[str]) -> None:
    external_actions = "docs/runbooks/external-actions-aws.md"
    simulation_runbook = "docs/runbooks/observability-alert-simulations.md"

    release = _read_text("docs/runbooks/release-checklist.md")
    operations = _read_text("docs/runbooks/operations.md")
    deployment = _read_text("docs/runbooks/deployment.md")
    backlog = _read_text("docs/project/phase1-execution-backlog.md")

    if simulation_runbook not in release:
        errors.append(
            "docs/runbooks/release-checklist.md: missing observability simulation runbook link."
        )

    for rel_path, content in (
        ("docs/runbooks/release-checklist.md", release),
        ("docs/runbooks/operations.md", operations),
        ("docs/runbooks/deployment.md", deployment),
        ("docs/project/phase1-execution-backlog.md", backlog),
    ):
        if external_actions not in content:
            errors.append(f"{rel_path}: missing external actions register link.")


def main() -> int:
    errors: list[str] = []
    _check_required_files(errors)
    _check_health_endpoints(errors)
    _check_structured_log_fields(errors)
    _check_required_links(errors)

    if errors:
        print("Observability prerequisite validation failed:")
        for message in errors:
            print(f"- {message}")
        return 1

    print("Observability prerequisite validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
