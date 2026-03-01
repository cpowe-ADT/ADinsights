#!/usr/bin/env python3
"""Validate release-gates.yaml structure and values."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc


REQUIRED_KEYS = {
    "skill",
    "version",
    "mode",
    "packet_schema_version",
    "gate_statuses",
    "release_statuses",
    "gate_dimensions",
    "scope_control",
    "contract_integrity",
    "required_artifacts",
    "optional_checks",
    "next_action_templates",
}

RELEASE_STATUSES = {"GATE_PASS", "GATE_WARN", "GATE_BLOCK"}

REQUIRED_DIMENSIONS = {
    "scope_control",
    "contract_integrity",
    "test_coverage",
    "observability",
    "security_pii_secrets",
    "runbook_ops_readiness",
    "documentation_completeness",
    "rollout_rollback_plan",
}

REQUIRED_GATE_STATUSES = {"PASS", "INFO", "WARN", "BLOCK"}


def default_rules_path() -> Path:
    root = Path(__file__).resolve().parents[5]
    return (
        root
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-release-readiness"
        / "references"
        / "release-gates.yaml"
    )


def validate_rules(path: Path) -> int:
    errors: list[str] = []

    if not path.exists():
        print(f"[ERROR] Rules file not found: {path}")
        return 1

    rules = yaml.safe_load(path.read_text()) or {}
    if not isinstance(rules, dict):
        print("[ERROR] Rules file must be a YAML mapping.")
        return 1

    missing = sorted(REQUIRED_KEYS - set(rules.keys()))
    if missing:
        errors.append("Missing required key(s): " + ", ".join(missing))

    if rules.get("skill") != "adinsights-release-readiness":
        errors.append("`skill` must equal 'adinsights-release-readiness'.")

    packet_schema_version = str(rules.get("packet_schema_version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", packet_schema_version):
        errors.append("`packet_schema_version` must be semver-like (for example 1.0.0).")

    release_statuses = rules.get("release_statuses")
    if not isinstance(release_statuses, list) or set(release_statuses) != RELEASE_STATUSES:
        errors.append("`release_statuses` must include exactly GATE_PASS/GATE_WARN/GATE_BLOCK.")

    gate_statuses = rules.get("gate_statuses")
    if not isinstance(gate_statuses, list) or set(gate_statuses) != REQUIRED_GATE_STATUSES:
        errors.append("`gate_statuses` must include exactly PASS/INFO/WARN/BLOCK.")

    gate_dimensions = rules.get("gate_dimensions")
    if not isinstance(gate_dimensions, list) or set(gate_dimensions) != REQUIRED_DIMENSIONS:
        errors.append("`gate_dimensions` must match the required gate dimension set.")

    scope_control = rules.get("scope_control", {})
    if not isinstance(scope_control, dict):
        errors.append("`scope_control` must be a mapping.")

    contract_integrity = rules.get("contract_integrity", {})
    if not isinstance(contract_integrity, dict):
        errors.append("`contract_integrity` must be a mapping.")

    required_artifacts = rules.get("required_artifacts")
    if not isinstance(required_artifacts, list) or not required_artifacts:
        errors.append("`required_artifacts` must be a non-empty list.")

    optional_checks = rules.get("optional_checks")
    if not isinstance(optional_checks, list):
        errors.append("`optional_checks` must be a list.")
    else:
        for idx, check in enumerate(optional_checks, start=1):
            if not isinstance(check, dict):
                errors.append(f"optional_checks[{idx}] must be an object.")
                continue
            for key in ("id", "command", "gate_dimension", "block_on_failure"):
                if key not in check:
                    errors.append(f"optional_checks[{idx}] missing key '{key}'.")
            if "gate_dimension" in check and check["gate_dimension"] not in REQUIRED_DIMENSIONS:
                errors.append(
                    f"optional_checks[{idx}].gate_dimension must be one of {sorted(REQUIRED_DIMENSIONS)}."
                )

    next_actions = rules.get("next_action_templates")
    if not isinstance(next_actions, dict):
        errors.append("`next_action_templates` must be a mapping.")
    else:
        for status in RELEASE_STATUSES:
            message = next_actions.get(status)
            if not isinstance(message, str) or not message.strip():
                errors.append(f"next_action_templates.{status} must be a non-empty string.")

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    print("[OK] Release gates config valid and complete.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate release-gates.yaml")
    parser.add_argument("--rules", type=Path, default=default_rules_path())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return validate_rules(args.rules)


if __name__ == "__main__":
    sys.exit(main())
