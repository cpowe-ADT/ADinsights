#!/usr/bin/env python3
"""Golden test runner for ADinsights persona router v2."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc

import persona_router


def here() -> Path:
    return Path(__file__).resolve().parent


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def check_type(value: Any, schema_type: str) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "null":
        return value is None
    return True


def validate_schema(packet: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    required = schema.get("required", [])
    for key in required:
        if key not in packet:
            errors.append(f"Missing required top-level key: {key}")

    properties = schema.get("properties", {})
    for key, rules in properties.items():
        if key not in packet:
            continue
        value = packet[key]

        allowed_types = rules.get("type")
        if isinstance(allowed_types, str):
            allowed_types = [allowed_types]
        if isinstance(allowed_types, list):
            if not any(check_type(value, t) for t in allowed_types):
                errors.append(
                    f"Key '{key}' expected type {allowed_types}, got {type(value).__name__}"
                )

        enum_values = rules.get("enum")
        if isinstance(enum_values, list) and value is not None and value not in enum_values:
            errors.append(f"Key '{key}' value '{value}' not in enum {enum_values}")

        if isinstance(value, dict) and isinstance(rules.get("required"), list):
            for nested_key in rules["required"]:
                if nested_key not in value:
                    errors.append(f"Key '{key}' missing nested required field '{nested_key}'")

    return errors


def check_expectations(packet: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if "action" in expect and packet.get("action") != expect["action"]:
        errors.append(f"Expected action={expect['action']}, got {packet.get('action')}")

    if "resolved_by" in expect and packet.get("resolved_by") != expect["resolved_by"]:
        errors.append(
            f"Expected resolved_by={expect['resolved_by']}, got {packet.get('resolved_by')}"
        )

    if "selected_persona_id" in expect:
        expected_id = expect["selected_persona_id"]
        selected = packet.get("selected_persona")
        actual_id = selected.get("id") if isinstance(selected, dict) else None
        if actual_id != expected_id:
            errors.append(f"Expected selected_persona.id={expected_id}, got {actual_id}")

    if "backup_persona_id" in expect:
        expected_backup = expect["backup_persona_id"]
        backup = packet.get("backup_persona")
        actual_backup = backup.get("id") if isinstance(backup, dict) else None
        if actual_backup != expected_backup:
            errors.append(f"Expected backup_persona.id={expected_backup}, got {actual_backup}")

    if "cross_stream" in expect:
        actual_cross = packet.get("conflict_flags", {}).get("cross_stream")
        if actual_cross != expect["cross_stream"]:
            errors.append(f"Expected cross_stream={expect['cross_stream']}, got {actual_cross}")

    if "invoke_scope_gatekeeper" in expect:
        actual = packet.get("downstream_recommendations", {}).get("invoke_scope_gatekeeper")
        if actual != expect["invoke_scope_gatekeeper"]:
            errors.append(
                "Expected invoke_scope_gatekeeper="
                f"{expect['invoke_scope_gatekeeper']}, got {actual}"
            )

    if "invoke_contract_guard" in expect:
        actual = packet.get("downstream_recommendations", {}).get("invoke_contract_guard")
        if actual != expect["invoke_contract_guard"]:
            errors.append(
                "Expected invoke_contract_guard="
                f"{expect['invoke_contract_guard']}, got {actual}"
            )

    if "invoke_release_readiness" in expect:
        actual = packet.get("downstream_recommendations", {}).get("invoke_release_readiness")
        if actual != expect["invoke_release_readiness"]:
            errors.append(
                "Expected invoke_release_readiness="
                f"{expect['invoke_release_readiness']}, got {actual}"
            )

    if "touched_streams_exact" in expect:
        expected_streams = expect["touched_streams_exact"]
        actual_streams = packet.get("touched_streams")
        if actual_streams != expected_streams:
            errors.append(f"Expected touched_streams={expected_streams}, got {actual_streams}")

    if "recommended_report_template" in expect:
        expected_template = expect["recommended_report_template"]
        actual_template = packet.get("recommended_report_template")
        if actual_template != expected_template:
            errors.append(
                f"Expected recommended_report_template={expected_template}, got {actual_template}"
            )

    if "escalation_contains" in expect:
        expected_reviewers = set(expect["escalation_contains"])
        actual_reviewers = set(packet.get("escalation_decision", {}).get("required_reviewers", []))
        if not expected_reviewers.issubset(actual_reviewers):
            errors.append(
                f"Expected escalation reviewers {sorted(expected_reviewers)} to be subset of {sorted(actual_reviewers)}"
            )

    schema_version = packet.get("schema_version")
    if schema_version != "2.1.0":
        errors.append(f"Expected schema_version=2.1.0, got {schema_version}")

    if not isinstance(packet.get("evidence"), list):
        errors.append("Expected evidence to be a list.")

    if not isinstance(packet.get("decision_trace"), str) or not packet.get("decision_trace"):
        errors.append("Expected decision_trace to be a non-empty string.")

    return errors


def main() -> int:
    base = here().parent
    cases_path = base / "references" / "router-golden-cases.yaml"
    schema_path = base / "references" / "decision-packet.schema.json"
    catalog_path = base / "references" / "persona-catalog.yaml"

    cases_doc = load_yaml(cases_path)
    schema = json.loads(schema_path.read_text())
    cases = cases_doc.get("cases", [])

    if not isinstance(cases, list) or not cases:
        print("[ERROR] No cases found in router-golden-cases.yaml")
        return 1

    failures = 0

    for case in cases:
        name = case.get("name", "unnamed")
        input_data = case.get("input", {})
        expect = case.get("expect", {})

        prompt = str(input_data.get("prompt", "")).strip()
        mode = str(input_data.get("mode", "resolve"))
        paths = [str(p) for p in input_data.get("paths", [])]
        changed_files = [str(p) for p in input_data.get("changed_files", [])]

        packet = persona_router.build_decision_packet(
            prompt=prompt,
            mode=mode,
            explicit_paths=paths,
            changed_files=changed_files,
            use_git_changed_files=False,
            catalog_path=catalog_path,
        )

        errors = []
        errors.extend(validate_schema(packet, schema))
        errors.extend(check_expectations(packet, expect))

        if errors:
            failures += 1
            print(f"[FAIL] {name}")
            for err in errors:
                print(f"  - {err}")
            print("  Packet:")
            print(json.dumps(packet, indent=2))
        else:
            print(f"[PASS] {name}")

    if failures:
        print(f"\n[ERROR] {failures} case(s) failed.")
        return 1

    print(f"\n[OK] {len(cases)} router golden cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
