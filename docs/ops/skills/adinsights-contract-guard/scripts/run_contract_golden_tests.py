#!/usr/bin/env python3
"""Golden tests for ADinsights contract guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc

import evaluate_contract


def base_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def check_case(packet: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if "contract_status" in expect and packet.get("contract_status") != expect["contract_status"]:
        errors.append(
            f"Expected contract_status={expect['contract_status']}, got {packet.get('contract_status')}"
        )

    if "breaking_change_detected" in expect:
        actual = packet.get("breaking_change_detected")
        if actual != expect["breaking_change_detected"]:
            errors.append(
                f"Expected breaking_change_detected={expect['breaking_change_detected']}, got {actual}"
            )

    if "required_reviewers_contains" in expect:
        required = set(expect["required_reviewers_contains"])
        actual = set(packet.get("required_reviewers", []))
        if not required.issubset(actual):
            errors.append(
                f"Expected reviewers {sorted(required)} to be subset of {sorted(actual)}"
            )

    if "required_docs_updates_contains" in expect:
        required = set(expect["required_docs_updates_contains"])
        actual = set(packet.get("required_docs_updates", []))
        if not required.issubset(actual):
            errors.append(
                f"Expected docs {sorted(required)} to be subset of {sorted(actual)}"
            )

    if "required_tests_contains" in expect:
        required = set(expect["required_tests_contains"])
        actual = set(packet.get("required_tests", []))
        if not required.issubset(actual):
            errors.append(
                f"Expected tests {sorted(required)} to be subset of {sorted(actual)}"
            )

    if "ci_strict_would_fail" in expect:
        actual = packet.get("ci_strict_evaluation", {}).get("would_fail_ci")
        if actual != expect["ci_strict_would_fail"]:
            errors.append(
                f"Expected ci_strict_would_fail={expect['ci_strict_would_fail']}, got {actual}"
            )

    if "ci_strict_level" in expect:
        actual = packet.get("ci_strict_evaluation", {}).get("strict_level")
        if actual != expect["ci_strict_level"]:
            errors.append(
                f"Expected ci_strict_level={expect['ci_strict_level']}, got {actual}"
            )

    if packet.get("schema_version") != "1.0.0":
        errors.append(f"Expected schema_version=1.0.0, got {packet.get('schema_version')}")

    if not isinstance(packet.get("evidence"), list):
        errors.append("Expected evidence to be a list.")

    return errors


def main() -> int:
    rules_path = base_dir() / "references" / "contract-rules.yaml"
    cases_path = base_dir() / "references" / "contract-golden-cases.yaml"
    schema_path = base_dir() / "references" / "contract-decision.schema.json"

    cases_doc = load_yaml(cases_path)
    cases = cases_doc.get("cases", [])

    if not isinstance(cases, list) or not cases:
        print("[ERROR] No cases found in contract-golden-cases.yaml")
        return 1

    schema = json.loads(schema_path.read_text())
    required_keys = set(schema.get("required", []))

    failures = 0

    for case in cases:
        name = case.get("name", "unnamed")
        input_data = case.get("input", {})
        expect = case.get("expect", {})

        packet = evaluate_contract.evaluate_contract(
            prompt=str(input_data.get("prompt", "")),
            explicit_paths=[str(p) for p in input_data.get("paths", [])],
            changed_files=[str(p) for p in input_data.get("changed_files", [])],
            use_git_changed_files=False,
            rules_path=rules_path,
            router_packet=input_data.get("router_packet") if isinstance(input_data.get("router_packet"), dict) else {},
            scope_packet=input_data.get("scope_packet") if isinstance(input_data.get("scope_packet"), dict) else {},
            ci_strict_enabled=bool(input_data.get("ci_strict_enabled", False)),
            ci_strict_level=str(input_data.get("ci_strict_level", "breaking_only")),
        )

        errors = check_case(packet, expect)

        missing_required = sorted(required_keys - set(packet.keys()))
        if missing_required:
            errors.append("Missing required keys: " + ", ".join(missing_required))

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
        print(f"\n[ERROR] {failures} contract golden case(s) failed.")
        return 1

    print(f"\n[OK] {len(cases)} contract golden cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
